# routers/books.py
from fastapi import APIRouter, Query, Depends
from typing import Optional
from schemas.search import BookResponse, SearchResponse, BookListResponse
from service.book_service import get_book_service
from core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, DEFAULT_VECTOR_SEARCH_LIMIT, MAX_VECTOR_SEARCH_LIMIT

router = APIRouter(prefix="/books", tags=["Books"])

@router.get("/search", response_model=SearchResponse)
async def search_books(
    query: Optional[str] = Query(None, description="검색어 (제목, 책 소개, 목차)"),
    title: Optional[str] = Query(None, description="제목으로 검색"),
    isbn: Optional[str] = Query(None, description="ISBN으로 검색"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="페이지당 결과 수"),
    book_service = Depends(get_book_service)
):
    """도서를 검색합니다."""
    return await book_service.search_books(query, title, isbn, page, per_page)

@router.get("/isbn/{isbn}", response_model=BookResponse)
async def get_book_by_isbn(isbn: str, book_service = Depends(get_book_service)):
    """ISBN으로 특정 도서를 조회합니다."""
    return await book_service.get_book_by_isbn(isbn)

@router.get("/vector-search", response_model=SearchResponse)
async def vector_search_books(
    query: str = Query(..., description="벡터 검색 쿼리"),
    limit: int = Query(DEFAULT_VECTOR_SEARCH_LIMIT, ge=10, le=MAX_VECTOR_SEARCH_LIMIT),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    book_service = Depends(get_book_service)
):
    """벡터 유사도를 기반으로 도서를 검색합니다."""
    return await book_service.vector_search_books(query, limit, page, per_page)

@router.get("/subject-related-books", response_model=BookListResponse)
async def get_subject_related_books(
    node_id: str = Query(..., description="주제 ID"),
    limit: int = Query(..., description="최대 탐색 개수"),
    book_service = Depends(get_book_service)
):
    """주제어와 관련된 도서를 검색합니다."""
    return await book_service.get_subject_related_books(node_id, limit)