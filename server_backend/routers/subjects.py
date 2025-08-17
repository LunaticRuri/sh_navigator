# routers/subjects.py
from fastapi import APIRouter, Query, Depends
from typing import Optional
from schemas.search import SubjectResponse, SearchResponse, KDCAccessPointListResponse
from service.subject_service import get_subject_service
from core.config import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, DEFAULT_VECTOR_SEARCH_LIMIT, MAX_VECTOR_SEARCH_LIMIT

router = APIRouter(prefix="/subjects", tags=["Subjects"])

@router.get("/search", response_model=SearchResponse)
async def search_subjects(
    query: Optional[str] = Query(None, description="주제명으로 검색"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    subject_service = Depends(get_subject_service)
):
    """주제명을 검색합니다."""
    return await subject_service.search_subjects(query, page, per_page)

@router.get("/node_id/{node_id}", response_model=SubjectResponse)
async def get_subject_by_node_id(node_id: str, subject_service = Depends(get_subject_service)):
    """노드 ID로 특정 주제를 조회합니다."""
    return await subject_service.get_subject_by_node_id(node_id)

@router.get("/vector-search", response_model=SearchResponse)
async def vector_search_subjects(
    query: str = Query(..., description="벡터 검색 쿼리"),
    limit: int = Query(DEFAULT_VECTOR_SEARCH_LIMIT, ge=10, le=MAX_VECTOR_SEARCH_LIMIT),
    page: int = Query(1, ge=1, description="페이지 번호"),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    subject_service = Depends(get_subject_service)
):
    """벡터 유사도를 기반으로 주제를 검색합니다."""
    return await subject_service.vector_search_subjects(query, limit, page, per_page)

@router.get("/kdc-access-points", response_model=KDCAccessPointListResponse)
async def get_kdc_access_points(
    node_id: str = Query(..., description="주제 노드 ID"),
    subject_service = Depends(get_subject_service)
):
    """KDC 접근점을 조회합니다."""
    return await subject_service.get_kdc_access_points(node_id)