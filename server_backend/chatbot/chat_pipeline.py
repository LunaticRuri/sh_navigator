from core.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_QUERY_LENGTH, MODEL_SERVER_URL, NETWORK_SERVER_URL
from schemas.search import BookResponse, SubjectResponse
from schemas.chat import UserNeeds,UserNeedsAnalysis, ResourcesFromNeeds
from core.utils import truncate_string
from database.database_manager import get_database_manager
import httpx
import json
from typing import List
import logging
import google.generativeai as genai
from google.generativeai.protos import Schema, Type

logger = logging.getLogger(__name__)


genai.configure(api_key=GEMINI_API_KEY)

user_needs_analysis_config = genai.GenerationConfig(
    response_mime_type="application/json",
    response_schema=Schema(
        type = Type.OBJECT,
        required = ["needs_exist"],
        properties = {
            "needs_exist": Schema(
                type = Type.BOOLEAN,
            ),
            "needs": Schema(
                type = Type.ARRAY,
                items = Schema(
                    type = Type.OBJECT,
                    required = ["subject", "predicate", "object", "keywords"],
                    properties = {
                        "subject": Schema(
                            type = Type.STRING,
                        ),
                        "predicate": Schema(
                            type = Type.STRING,
                        ),
                        "object": Schema(
                            type = Type.STRING,
                        ),
                        "keywords": Schema(
                            type = Type.ARRAY,
                            items = Schema(
                                type = Type.STRING,
                            ),
                            min_items=4  # Ensure at least 4 keywords are provided
                        ),
                    },
                ),
            ),
        },
    ),
)

user_needs_analysis_system_instruction = (
        "너는 이용자의 입력을 받아 정보 요구를 추출하는 일을 한다.\n"
        "일은 다음의 순서에 따라 처리하자.\n"
        "1. 우선 입력에 명시적, 암시적으로 드러나는 정보요구가 있으면 needs_exist가 true, 없으면 false이다.\n"
        "2. 만약 needs_exist가 False이면, 여기서 일을 종료하면 됨. (즉 needs 는 비워둬야 함)\n"
        "3. 만약 needs_exist가 true이면, 사용자의 입력에서 알 수 있는 모든 정보 요구를 파악하자. 정보요구는 여러개 있을 수 있음.\n"
        "4. 파악된 정보요구들을 RDF 트리플(subject, predicate, object)로 나타내자.\n"
        "5. 그 정보요구를 해결하기 위해 필요한 내용이 뭔지를 생각해두자.\n" 
        "6. 필요한 내용에 관련된 '책'이나 '주제명 표목'을 찾는 데에 도움이 될만한 키워드(단어 또는 구)를 최소한 3개 이상 keywords에 나타내자."
    )

user_needs_analysis_model = genai.GenerativeModel(
    GEMINI_MODEL,
    system_instruction=user_needs_analysis_system_instruction
)

def _row_to_book_response(row) -> BookResponse:
    return BookResponse(
        isbn=row["isbn"],
        title=row["title"],
        kdc=row["kdc"],
        publication_year=row["publication_year"],
        intro=row["intro"],
        toc=row["toc"],
        nlk_subjects=row["nlk_subjects"]
    )

def _row_to_subject_response(row) -> SubjectResponse:
    return SubjectResponse(
        node_id=row["node_id"],
        label=row["label"],
        definition=row["definition"]
    )

async def _find_book_candidates_by_needs(keywords_str : str) -> List[BookResponse]:
    http_client = httpx.AsyncClient(timeout=10.0)

    query = truncate_string(keywords_str, MAX_QUERY_LENGTH)
    
    response = await http_client.post(
        f"{MODEL_SERVER_URL}/search/books",
        json={"query": query, "limit": 10}
    )
    response.raise_for_status()
    search_data = response.json()
    retrieved_isbns = search_data.get("retrieved_isbns", [])
    
    db_manager = get_database_manager()
    async with db_manager.get_connection() as conn:
        cursor = await conn.cursor()
        
        query = """
            SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects 
            FROM books 
            WHERE isbn IN ({})
            LIMIT ?
        """.format(','.join('?' for _ in retrieved_isbns))
        
        await cursor.execute(query, (*retrieved_isbns, 10))
        books_data = await cursor.fetchall()
        
    # Sort results to match FAISS order
    books_data = sorted(
        books_data, 
        key=lambda x: retrieved_isbns.index(x[0])
    )

    # Convert DB rows to response models
    books = [_row_to_book_response(row) for row in books_data]
        
    return books

async def _find_subject_candidates_by_needs(query) -> List[SubjectResponse]:
    
    http_client = httpx.AsyncClient(timeout=10.0)
    db_manager = get_database_manager()
    
    # Get subject-related subjects
    response = await http_client.post(
        f"{MODEL_SERVER_URL}/search/subjects",
        json={"query": query, "limit": 10}
    )
    response.raise_for_status()
    search_data = response.json()
    retrieved_node_ids = search_data.get("retrieved_node_ids", [])

    
    async with db_manager.get_connection() as conn:
        cursor = await conn.cursor()
        
        query = """
            SELECT node_id, label, definition 
            FROM subjects 
            WHERE node_id IN ({})
            LIMIT ?
        """.format(','.join('?' for _ in retrieved_node_ids))
        await cursor.execute(query, (*retrieved_node_ids, 10))
        
        subjects_data = await cursor.fetchall()
    
    # Sort results to match FAISS order
    subjects_data = sorted(
        subjects_data, 
        key=lambda x: retrieved_node_ids.index(x[0])
    )

    subjects = [_row_to_subject_response(row) for row in subjects_data]
    return subjects

async def _get_book_by_isbn(isbn: str) -> BookResponse:
    db_manager = get_database_manager()
    
    async with db_manager.get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            "SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects FROM books WHERE isbn = ?",
            (isbn,)
        )
        row = await cursor.fetchone()
        
    if row:
        return _row_to_book_response(row)
    else:
        raise ValueError(f"Book with ISBN {isbn} not found.")
    
async def _get_subject_by_node_id(node_id: str) -> SubjectResponse:
    db_manager = get_database_manager()
    
    async with db_manager.get_connection() as conn:
        cursor = await conn.cursor()
        await cursor.execute(
            "SELECT node_id, label, definition FROM subjects WHERE node_id = ?",
            (node_id,)
        )
        row = await cursor.fetchone()
        
    if row:
        return _row_to_subject_response(row)
    else:
        raise ValueError(f"Subject with node_id {node_id} not found.")

async def _get_related_books_by_subject(node_id: str, limit: int = 10) -> List[BookResponse]:
    db_manager = get_database_manager()
    try:
        async with db_manager.get_connection() as conn:
            cursor = await conn.cursor()
            query = "SELECT isbn FROM book_subject_index WHERE node_id = ?"
            await cursor.execute(query, (node_id,))
            
            retrieved_isbns = await cursor.fetchall()
            if not retrieved_isbns:
                return []

            # Flatten the list of tuples to a list of ISBNs
            retrieved_isbns = [row[0] for row in retrieved_isbns]
            
            # Query for book details by ISBNs
            query = """
            SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects FROM books 
            WHERE isbn IN ({}) ORDER BY publication_year DESC LIMIT ?
            """.format(','.join('?' for _ in retrieved_isbns))

            await cursor.execute(query, (*retrieved_isbns, limit))

            books_data = await cursor.fetchall()

            # Convert DB rows to response models
            books = [_row_to_book_response(row) for row in books_data]

            return books

    except Exception as e:
        logger.error(f"Error retrieving related books for subject {node_id}: {e}")
        raise ValueError(f"Failed to retrieve related books for subject {node_id}: {e}")

async def analyze_user_needs(user_input: str) -> UserNeedsAnalysis:

    contents = [user_input]
    try:
        response = await user_needs_analysis_model.generate_content_async(
            contents=contents,
            generation_config=user_needs_analysis_config
        )
        logger.info(f"Response from Gemini: {response.text}")
        response_json = json.loads(response.text)
        
        needs_exist = response_json.get("needs_exist", False)
        needs = response_json.get("needs", [])
        if not needs_exist:
            return UserNeedsAnalysis(
                needs_exist=False,
                needs=[]
            )
        else:
            return UserNeedsAnalysis(
                needs_exist=True,
                needs=[
                    UserNeeds(
                        subject_=need.get("subject", ""),
                        predicate_=need.get("predicate", ""),
                        object_=need.get("object", ""),
                        keywords=need.get("keywords", [])
                    ) for need in needs
                ]
            )
    except Exception as e:
        raise RuntimeError(f"Failed to generate content: {e}")
    
async def find_resources_from_needs(user_needs: UserNeeds) -> ResourcesFromNeeds:
    
    book_candidates = []
    sub_subject_candidates = []
    obj_subject_candidates = []

    
    keywords_str = ', '.join(user_needs.keywords)
    book_candidates.extend(await _find_book_candidates_by_needs(keywords_str))
    sub_subject_candidates.extend(await _find_subject_candidates_by_needs(user_needs.subject_))
    obj_subject_candidates.extend(await _find_subject_candidates_by_needs(user_needs.object_))
    
    return ResourcesFromNeeds(
        books=book_candidates,
        sub_subjects=sub_subject_candidates,
        obj_subjects=obj_subject_candidates
    )      

async def filter_resources():
    ... # Implement filtering logic if needed


async def find_resources_by_isbn(isbn: str) -> str:
    try:
        book_metadata = await _get_book_by_isbn(isbn)

        if not book_metadata.nlk_subjects:
            resource_str = f'책 정보: \n {book_metadata}'
        else:
            subjects = json.loads(book_metadata.nlk_subjects)
            subject_list = []
            for subject in subjects:
                if 'id' in subject:
                    try:
                        subject_data = await _get_subject_by_node_id(subject['id'])
                        subject_list.append(subject_data)
                    except ValueError:
                        break
            if not subject_list:
                resource_str = f'책 정보: \n {book_metadata}'
            else:
                subject_str = '\n'.join([f"주제: {subject.label} ID: {subject.node_id}, 정의:{subject.definition}" for subject in subject_list])
                resource_str = f"책 정보: \n{book_metadata}\n\n관련 주제:\n{subject_str}"

        return resource_str
    
    except ValueError as e:
        raise RuntimeError(f"Metadata not found: {e}")
    
async def find_resources_by_node_id(node_id: str) -> str:
    try:
        subject_metadata = await _get_subject_by_node_id(node_id)
        related_books = await _get_related_books_by_subject(node_id)
        if not related_books:
            return f"주제: {subject_metadata}"
        else:
            return f"주제: {subject_metadata}\n\n관련 책들:\n{related_books}"
    
    except ValueError as e:
        raise RuntimeError(f"Subject not found: {e}")

if __name__ == "__main__":
    user_input = "나는 서울의 역사에 대해 알고 싶어."
    result = analyze_user_needs(user_input)
    print(result)