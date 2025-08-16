from functools import lru_cache
from typing import List, Dict, Tuple
from fastapi import HTTPException
import logging
import httpx
import time
from database.database_manager import DatabaseManager
from schemas.search import BookResponse, SearchResponse, BookListResponse
from core.utils import sanitize_query, truncate_string, calculate_pagination, log_search_query
from core.config import (
    MAX_QUERY_LENGTH,
    MODEL_SERVER_URL
)

logger = logging.getLogger(__name__)


class BookService:
    """Service class for book-related operations."""

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize the book service.
        
        Args:
            embedding_model: SentenceTransformer model for embeddings
            db_connection_manager: Database connection manager function
        """
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.database_manager = database_manager

    async def search_books(
        self,
        query: str = None,
        title: str = None,
        isbn: str = None,
        page: int = 1,
        per_page: int = 20
    ) -> SearchResponse:
        """
        Search books using full-text search.
        
        Args:
            query: General search query (title, intro, toc)
            title: Title-specific search
            isbn: ISBN search
            page: Page number
            per_page: Results per page
            
        Returns:
            SearchResponse with book results
        """
        try:
            # Validate and sanitize inputs
            if not any([query, title, isbn]):
                raise HTTPException(status_code=400, detail="검색어 또는 제목을 제공해야 합니다.")
            
            # Sanitize query
            if query:
                query = sanitize_query(query)
            if title:
                title = sanitize_query(title)

            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Build search query
                base_query, count_query, params = self._build_search_query(query, title, isbn)
                
                # Get total count
                await cursor.execute(count_query, params)
                result = await cursor.fetchone()
                total_count = result[0]
                
                # Calculate pagination
                pagination = calculate_pagination(total_count, page, per_page)
                
                # Get results with pagination
                final_query = f"{base_query} ORDER BY RANK LIMIT ? OFFSET ?"
                await cursor.execute(final_query, params + [per_page, pagination["offset"]])
                result_isbn_data = await cursor.fetchall()
                
                # Get detailed book information
                if result_isbn_data:
                    isbn_list = [row['ROWID'] for row in result_isbn_data]
                    books_data = await self._get_books_by_isbns(cursor, isbn_list)
                else:
                    books_data = []
                
                # Convert to response models
                books = [self._row_to_book_response(row) for row in books_data]
                
                # Log search for analytics
                search_term = query or title or isbn
                log_search_query("text_search", search_term, len(books))
                
                return SearchResponse(
                    results=books,
                    total_count=total_count,
                    page=page,
                    per_page=per_page,
                    total_pages=pagination["total_pages"]
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in book search: {e}")
            raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")

    async def get_book_by_isbn(self, isbn: str) -> BookResponse:
        """
        Get a specific book by ISBN.
        
        Args:
            isbn: Book ISBN
            
        Returns:
            BookResponse with book details
        """
        try:
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                await cursor.execute("SELECT * FROM books WHERE isbn = ?", (isbn,))
                book_data = await cursor.fetchone()
                
                if not book_data:
                    raise HTTPException(status_code=404, detail="도서를 찾을 수 없습니다.")
                
                return self._row_to_book_response(book_data)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting book by ISBN {isbn}: {e}")
            raise HTTPException(status_code=500, detail="도서 조회 중 오류가 발생했습니다.")

    async def vector_search_books(
        self,
        query: str,
        limit: int = 25,
        page: int = 1,
        per_page: int = 20
    ) -> SearchResponse:
        """
        Search books using vector similarity.
        
        Args:
            query: Search query for vector search
            limit: Maximum number of results from FAISS
            page: Page number
            per_page: Results per page
            
        Returns:
            SearchResponse with book results
        """
        try:
            # Validate and truncate query
            query = truncate_string(query, MAX_QUERY_LENGTH)
            
            
            time_start = time.time()
            response = await self.http_client.post(
                f"{MODEL_SERVER_URL}/search/books",
                json={"query": query, "limit": limit}
            )
            response.raise_for_status()
            search_data = response.json()
            retrieved_isbns = search_data.get("retrieved_isbns", [])
            logger.info(f"Query embedding and FAISS search completed in {time.time() - time_start:.2f} seconds")
            
            
            if not retrieved_isbns:
                return SearchResponse(
                    results=[],
                    total_count=0,
                    page=page,
                    per_page=per_page,
                    total_pages=1
                )

            # Get book details from database
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Calculate pagination
                total_count = min(len(retrieved_isbns), limit)
                pagination = calculate_pagination(total_count, page, per_page)
                
                # Get current page data
                current_page_limit = min(per_page, max(0, total_count - pagination["offset"]))
                
                final_query = """
                    SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects 
                    FROM books 
                    WHERE isbn IN ({})
                    LIMIT ? OFFSET ?
                """.format(','.join('?' for _ in retrieved_isbns))
                
                await cursor.execute(
                    final_query, 
                    (*retrieved_isbns, current_page_limit, pagination["offset"])
                )
                
                books_data = await cursor.fetchall()
                
                # Sort by original FAISS order
                books_data = sorted(
                    books_data, 
                    key=lambda x: retrieved_isbns.index(x[0])
                )

                # Convert to response models
                books = [self._row_to_book_response(row) for row in books_data]
                
                # Log search for analytics
                log_search_query("vector_search", query, len(books))
                
                return SearchResponse(
                    results=books,
                    total_count=total_count,
                    page=page,
                    per_page=per_page,
                    total_pages=pagination["total_pages"]
                )
    
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            raise HTTPException(status_code=500, detail=f"벡터 검색 중 오류가 발생했습니다: {str(e)}")

    async def get_subject_related_books(
        self,
        node_id: str,
        limit: int
    ) -> BookListResponse:
        """
        Get books related to a specific subject node.
        
        Args:
            node_id: Subject node ID
        Returns:
            BookListResponse with related books
        """
        try:
            # Validate node_id
            if not node_id:
                raise HTTPException(status_code=400, detail="주제 ID를 제공해야 합니다.")
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                query = "SELECT isbn FROM book_subject_index WHERE node_id = ?"
                await cursor.execute(query, (node_id,))
                
                retrieved_isbns = await cursor.fetchall()
                if not retrieved_isbns:
                    return BookListResponse(
                        books=[],
                        total_count=0
                    )

                # Flatten the list of tuples to a list of ISBNs
                retrieved_isbns = [row[0] for row in retrieved_isbns]
                
                query = """
                SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects FROM books 
                WHERE isbn IN ({}) ORDER BY publication_year DESC LIMIT ?
                """.format(','.join('?' for _ in retrieved_isbns))

                await cursor.execute(query, (*retrieved_isbns, limit))

                books_data = await cursor.fetchall()

                books = [self._row_to_book_response(row) for row in books_data]

                # Log search for analytics
                log_search_query("subject_related_books", query, len(books))

                return BookListResponse(
                    books = books,
                    total_count= len(books)
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in subject related books search: {e}")
            raise HTTPException(status_code=500, detail=f"주제 관련 도서 검색 중 오류가 발생했습니다: {str(e)}")

    def _build_search_query(
        self, 
        query: str = None, 
        title: str = None, 
        isbn: str = None
    ) -> Tuple[str, str, List[str]]:
        """
        Build SQL query for book search.
        
        Args:
            query: General search query
            title: Title search query
            isbn: ISBN search query
            
        Returns:
            Tuple of (base_query, count_query, params)
        """
        base_query = "SELECT ROWID FROM books_fts"
        count_query = "SELECT COUNT(*) FROM books_fts"
        params = []
        
        if query:
            base_query += " WHERE title MATCH ? OR intro MATCH ? OR toc MATCH ?"
            count_query += " WHERE title MATCH ? OR intro MATCH ? OR toc MATCH ?"
            params.extend([query, query, query])
        elif title:
            base_query += " WHERE title MATCH ?"
            count_query += " WHERE title MATCH ?"
            params.append(title)
        elif isbn:
            base_query += " WHERE ROWID = ?"
            count_query += " WHERE ROWID = ?"
            params.append(isbn)
        
        return base_query, count_query, params

    async def _get_books_by_isbns(self, cursor, isbn_list: List[str]) -> List[Dict]:
        """
        Get book details by list of ISBNs.
        
        Args:
            cursor: Database cursor
            isbn_list: List of ISBNs
            
        Returns:
            List of book data dictionaries
        """
        query = """
            SELECT isbn, title, kdc, publication_year, intro, toc, nlk_subjects 
            FROM books 
            WHERE isbn IN ({})
        """.format(','.join(['?'] * len(isbn_list)))
        
        await cursor.execute(query, isbn_list)
        return await cursor.fetchall()

    def _row_to_book_response(self, row) -> BookResponse:
        """
        Convert database row to BookResponse model.
        
        Args:
            row: Database row
            
        Returns:
            BookResponse model
        """
        return BookResponse(
            isbn=row["isbn"],
            title=row["title"],
            kdc=row["kdc"],
            publication_year=row["publication_year"],
            intro=row["intro"],
            toc=row["toc"],
            nlk_subjects=row["nlk_subjects"]
        )


# 전역 서비스 인스턴스
_book_service_instance = None

def set_book_service(database_manager: DatabaseManager):
    """전역 book service 인스턴스 설정"""
    global _book_service_instance
    _book_service_instance = BookService(database_manager)

@lru_cache()
def get_book_service() -> BookService:
    """FastAPI 의존성으로 사용할 book service 인스턴스 반환"""
    if _book_service_instance is None:
        raise RuntimeError("Book service not initialized")
    return _book_service_instance