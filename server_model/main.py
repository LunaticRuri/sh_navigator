# model_server/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import torch
import os
import logging
import time
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = "nlpai-lab/KURE-v1"
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'

print("Loading Sentence Transformer model...")
model = SentenceTransformer(MODEL_NAME, device=DEVICE)
print(f"Model loaded on {DEVICE}.")


DATA_DIR = "/home/namu101/msga/data"

# FAISS Index Paths
BOOKS_FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss/book_faiss_index.faiss')
ISBN_MAP_PATH = os.path.join(DATA_DIR, 'faiss/book_isbn_map.pkl')
SUBJECTS_FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss/subject_faiss_index.faiss')
NODE_ID_MAP_PATH = os.path.join(DATA_DIR, 'faiss/subject_node_id_map.pkl')

print("Loading Faiss index...")
try:
    books_faiss_index = faiss.read_index(BOOKS_FAISS_INDEX_PATH)
    with open(ISBN_MAP_PATH, 'rb') as f:
        isbn_map = pickle.load(f)
    print("Books faiss index loaded.")

    subjects_faiss_index = faiss.read_index(SUBJECTS_FAISS_INDEX_PATH)
    with open(NODE_ID_MAP_PATH, 'rb') as f:
        node_id_map = pickle.load(f)
    print("Subjects faiss index loaded.")
except Exception as e:
    print(f"Failed to load Faiss index: {e}")
    books_faiss_index = None
    subjects_faiss_index = None

app = FastAPI(
    title="Embedding & FAISS Server",
    description="임베딩과 벡터 검색을 처리하는 FastAPI 서버",
    version="1.0.0"
    )


class EmbedRequest(BaseModel):
    text: str = Field(..., description="임베딩할 텍스트")

class EmbedResponse(BaseModel):
    vector: list[float] = Field(..., description="임베딩 벡터")

class SearchRequest(BaseModel):
    query: str = Field(..., description="검색 쿼리")
    limit: int = Field(10, gt=0, le=100, description="검색 결과의 최대 개수 (1~100 사이의 값)")

class BookSearchResult(BaseModel):
    distances: list[float] = Field(..., description="검색된 도서와의 거리")
    retrieved_isbns: list[str] = Field(..., description="검색된 도서의 ISBN 목록")

class SubjectSearchResult(BaseModel):
    distances: list[float] = Field(..., description="검색된 주제와의 거리")
    retrieved_node_ids: list[str] = Field(..., description="검색된 주제의 노드 ID 목록")



@app.post("/embed", response_model=EmbedResponse)
def get_embedding(request: EmbedRequest):
    """텍스트를 입력받아 임베딩 벡터를 반환합니다."""
    start_time = time.time()
    vector = model.encode(request.text, convert_to_tensor=False, show_progress_bar=False).tolist()
    logger.info(f"Embedding generated in {time.time() - start_time:.2f} seconds")
    return EmbedResponse(vector=vector)

@app.post("/search/books", response_model=BookSearchResult)
def search_similar(request: SearchRequest):
    """
    쿼리 텍스트를 받아 임베딩하고 FAISS에서 유사한 도서를 검색합니다.
    """
    if books_faiss_index is None:
        raise HTTPException(status_code=503, detail="FAISS 인덱스를 사용할 수 없습니다.")

    try:
        query_vector = model.encode(
            [request.query], 
            convert_to_tensor=False, 
            show_progress_bar=False
        )
        query_vector_np = np.array(query_vector, dtype=np.float32)
        
        distances, indices = books_faiss_index.search(query_vector_np, request.limit)
        
        faiss_ids = indices[0]

        retrieved_isbns = [
            isbn_map[i] for i in faiss_ids
            if i in isbn_map
        ]
        
        return BookSearchResult(
            distances=distances[0].tolist(),
            retrieved_isbns=retrieved_isbns
        )
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="내부 서버 오류")

@app.post("/search/subjects", response_model=SubjectSearchResult)
def search_similar(request: SearchRequest):
    """
    쿼리 텍스트를 받아 임베딩하고 FAISS에서 유사한 주제를 검색합니다.
    """
    if subjects_faiss_index is None:
        raise HTTPException(status_code=503, detail="FAISS 인덱스를 사용할 수 없습니다.")
    try:
        query_vector = model.encode(
            [request.query], 
            convert_to_tensor=False, 
            show_progress_bar=False
        )
        query_vector_np = np.array(query_vector, dtype=np.float32)
        
        distances, indices = subjects_faiss_index.search(query_vector_np, request.limit)
        
        faiss_ids = indices[0]

        retrieved_node_ids = [
            node_id_map[i] for i in faiss_ids
            if i in node_id_map
        ]
        
        return SubjectSearchResult(
            distances=distances[0].tolist(),
            retrieved_node_ids=retrieved_node_ids
        )
    except Exception as e:
        logger.error(f"검색 중 오류 발생: {e}")
        raise HTTPException(status_code=500, detail="내부 서버 오류")

@app.get("/health")
def health_check():
    if not model or not books_faiss_index or not subjects_faiss_index:
        return {"status": "unhealthy", "reason": "Model or FAISS index not loaded"}
    return {"status": "healthy", "model": MODEL_NAME, "device": DEVICE}