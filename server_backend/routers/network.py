# routers/network.py
from fastapi import APIRouter, Query, Depends
from schemas.network import NetworkResponse, SeedNodeResponse
from service.subject_service import get_subject_service
from core.config import MAX_NETWORK_NEIGHBORS

router = APIRouter(prefix="/network", tags=["Network"])

@router.get("/node/{node_id}/neighbors", response_model=NetworkResponse)
async def get_node_neighbors(
    node_id: str,
    limit: int = Query(10, ge=1, le=MAX_NETWORK_NEIGHBORS),
    subject_service = Depends(get_subject_service)
):
    """특정 노드와 연결된 이웃 노드들을 조회합니다."""
    return await subject_service.get_node_neighbors(node_id, limit)

@router.get("/search-seed", response_model=SeedNodeResponse)
async def search_seed_node(
    query: str = Query(..., description="씨앗 노드를 찾기 위한 검색어"),
    subject_service = Depends(get_subject_service)
):
    """네트워크 시각화의 중심이 될 씨앗 노드를 검색합니다."""
    return await subject_service.search_seed_nodes(query)