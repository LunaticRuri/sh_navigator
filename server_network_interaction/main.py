# -*- coding: utf-8 -*-
"""
Network Interaction Server

별도의 FastAPI 서버로 분리된 네트워크 모델 캐시 서비스
메모리 사용량이 많은 NetworkX 그래프 처리를 별도 프로세스에서 실행
"""

import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any, Optional, List
from pydantic import BaseModel

from network_cache import NetworkModelCache, get_network_cache, initialize_network_cache

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(
    title="Network Interaction Server",
    description="네트워크 모델 접근을 처리하는 FastAPI 서버",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response 모델들

class NodesInfoRequest(BaseModel):
    node_ids: List[str]

class NodeInfoResponse(BaseModel):
    node_id: str
    info: Optional[Dict[str, Any]]

class NeighborsResponse(BaseModel):
    node_id: str
    nodes: Optional[List[Dict[str, Any]]]
    edges: Optional[List[Dict[str, Any]]]

class ShortestPathResponse(BaseModel):
    source_id: str
    target_id: str
    path: Optional[List[str]]

class GraphStatsResponse(BaseModel):
    stats: Optional[Dict[str, Any]]

class CommunityNodesResponse(BaseModel):
    community: int
    nodes: Optional[Dict[str, Dict[str, Any]]]

class ImportantNodesResponse(BaseModel):
    nodes: Optional[Dict[str, Dict[str, Any]]]

class HealthResponse(BaseModel):
    status: str
    initialized: bool
    message: str


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 네트워크 캐시 초기화"""
    try:
        logger.info("Initializing network cache...")
        await initialize_network_cache()
        logger.info("Network cache initialization completed")
    except Exception as e:
        logger.error(f"Failed to initialize network cache: {e}")
        raise


def get_cache() -> NetworkModelCache:
    """의존성 주입을 위한 캐시 인스턴스 반환"""
    return get_network_cache()


@app.get("/health", response_model=HealthResponse)
async def health_check(cache: NetworkModelCache = Depends(get_cache)):
    """서버 상태 확인"""
    graph = cache.get_graph()
    initialized = graph is not None
    
    return HealthResponse(
        status="healthy" if initialized else "initializing",
        initialized=initialized,
        message="Network cache is ready" if initialized else "Network cache is not initialized"
    )


@app.get("/stats", response_model=GraphStatsResponse)
async def get_graph_stats(cache: NetworkModelCache = Depends(get_cache)):
    """그래프 통계 정보 조회"""
    stats = cache.get_graph_stats()
    return GraphStatsResponse(stats=stats)


@app.get("/node/info", response_model=NodeInfoResponse)
async def get_node_info(
    node_id: str,
    cache: NetworkModelCache = Depends(get_cache)
):
    """특정 노드의 정보 조회"""
    info = cache.get_node_info(node_id)
    return NodeInfoResponse(node_id=node_id, info=info)


@app.post("/nodes/info")
async def get_nodes_info(
    request: NodesInfoRequest,
    cache: NetworkModelCache = Depends(get_cache)
):
    """여러 노드의 정보를 한번에 조회"""
    results = {}
    for node_id in request.node_ids:
        info = cache.get_node_info(node_id)
        results[node_id] = info
    
    return {"nodes": results}


@app.get("/node/neighbors", response_model=NeighborsResponse)
async def get_node_neighbors(
    node_id: str,
    relation_type: Optional[str] = None,
    cache: NetworkModelCache = Depends(get_cache)
):
    """특정 노드의 이웃 노드들 조회"""
    nodes, edges = cache.get_node_neighbors(node_id, relation_type)
    return NeighborsResponse(node_id=node_id, nodes=nodes, edges=edges)


@app.get("/path/shortest", response_model=ShortestPathResponse)
async def get_shortest_path(
    source_id: str,
    target_id: str,
    relation_type: Optional[str] = None,
    cache: NetworkModelCache = Depends(get_cache)
):
    """두 노드 간의 최단 경로 계산"""
    path = cache.get_shortest_path(source_id, target_id, relation_type)
    return ShortestPathResponse(
        source_id=source_id,
        target_id=target_id,
        path=path
    )


@app.get("/community/nodes", response_model=CommunityNodesResponse)
async def get_community_nodes(
    community: int,
    cache: NetworkModelCache = Depends(get_cache)
):
    """특정 커뮤니티에 속한 노드들 조회"""
    nodes = cache.get_nodes_by_community(community)
    return CommunityNodesResponse(community=community, nodes=nodes)


@app.get("/nodes/important", response_model=ImportantNodesResponse)
async def get_important_nodes(cache: NetworkModelCache = Depends(get_cache)):
    """중요한 노드들 조회"""
    nodes = cache.get_important_nodes()
    return ImportantNodesResponse(nodes=nodes)


@app.post("/cache/refresh")
async def refresh_cache(cache: NetworkModelCache = Depends(get_cache)):
    """캐시 새로고침"""
    try:
        await cache.refresh()
        return {"status": "success", "message": "Cache refreshed successfully"}
    except Exception as e:
        logger.error(f"Failed to refresh cache: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh cache: {e}")