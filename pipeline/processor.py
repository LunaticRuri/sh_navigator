# processor.py
import sqlite3
from sentence_transformers import SentenceTransformer
from datetime import datetime
import torch
import os
import logging
from config import EMBEDDING_MODEL


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

embedding_model = SentenceTransformer(EMBEDDING_MODEL, device='cuda' if torch.cuda.is_available() else 'cpu')

def process_and_embed(pipeline_db_path: str):

    if not os.path.exists(pipeline_db_path):
        logging.error("Pipeline database does not exist.")
        raise FileNotFoundError("Pipeline database does not exist.")

    logging.info("Processing and embedding books...")
    logging.info(f"Using embedding model: {EMBEDDING_MODEL}")
    logging.info(f"Using device: {'cuda' if torch.cuda.is_available() else 'cpu'}")
    
    conn = sqlite3.connect(pipeline_db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, isbn, title, intro, toc FROM book_pipeline WHERE status = 'enriched'")
    books_to_process = cursor.fetchall()
    logging.info(f"Found {len(books_to_process)} books to process and embed.")

    for record_id, isbn, title, intro, toc in books_to_process:
        intro = intro or ""
        toc = toc or ""
        
        summary = f"{title}\n{intro}\n{toc}"
        
        vector = embedding_model.encode(summary, show_progress_bar=False)
        
        vector_blob = vector.tobytes()
        
        cursor.execute("""
            UPDATE book_pipeline 
            SET embedding = ?, status = ?, last_updated = ?
            WHERE isbn = ?
        """, (vector_blob, 'processed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), isbn))
        logging.info(f"{record_id} - {isbn} processed and embedded successfully.")
        conn.commit()
    
    conn.close()
    logging.info("Processing and embedding completed.")