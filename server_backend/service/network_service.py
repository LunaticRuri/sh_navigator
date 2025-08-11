from functools import lru_cache
import logging
import httpx
from fastapi import HTTPException
from database.database_manager import DatabaseManager
from core.config import NETWORK_SERVER_URL
from schemas.network import NetworkResponse, SeedNodeResponse, SeedNodeCandidate, NetworkEdge, NetworkNode

from core.config import MAX_NETWORK_NEIGHBORS


logger = logging.getLogger(__name__)


class NetworkService:
    """Service for handling network-related operations."""

    def __init__(self, database_manager: DatabaseManager):
        """
        Initialize the subject service.
        
        Args:
            db_connection_manager: Database connection manager function
        """
        self.http_client = httpx.AsyncClient(timeout=10.0)
        self.database_manager = database_manager
    
        
    async def get_node_neighbors(self, node_id: str, limit: int = 10) -> NetworkResponse:
        """
        Get neighbors of a specific node.
        
        Args:
            node_id: Central node ID
            limit: Maximum number of neighbor nodes
            
        Returns:
            NetworkResponse with nodes and edges
        """
        try:
            # Validate limit
            limit = min(limit, MAX_NETWORK_NEIGHBORS)            

            # Get current node information from the network interaction server
            response = await self.http_client.get(
                f"{NETWORK_SERVER_URL}/node/info",
                params={"node_id": node_id}
            )
            response.raise_for_status()
            data = response.json()
            if not data or "info" not in data or not data["info"]:
                raise HTTPException(status_code=404, detail="노드 정보를 찾을 수 없습니다.")
            
            nodes = [
                NetworkNode(
                    node_id=node_id,
                    label=data['info']['label'],
                    definition=data['info'].get('definition', ""),
                    community=data['info'].get('community', 0),
                    type="current"
                )
            ]

            # Get neighbors from the network interaction server
            response = await self.http_client.get(
                f"{NETWORK_SERVER_URL}/node/neighbors",
                params={"node_id": node_id}
            )

            response.raise_for_status()
            data = response.json()
            
            if not data:
                return NetworkResponse(nodes=[], edges=[], center_node=node_id)

            edges = []
            
            for node in data['nodes']:
                nodes.append(
                    NetworkNode(
                        node_id = node["node_id"],
                        label = node["label"],
                        definition = node["definition"] or "",
                        community = node.get('community', 0),
                        type = "neighbor"
                    )
                )

            for edge in data['edges']:
                edge_data = NetworkEdge(
                    source=edge["source_id"],
                    target=edge["target_id"],
                    relation_type=edge["relation_type"],
                    metadata={k: v for k, v in edge.items() if k not in ("source_id", "target_id", "relation_type")}
                )
                edges.append(edge_data)
            
            edges = edges[:limit]  # Limit the number of edges

            return NetworkResponse(
                nodes=nodes,
                edges=edges,
                center_node=node_id
            )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting node neighbors for {node_id}: {e}")
            raise HTTPException(status_code=500, detail="네트워크 데이터 조회 중 오류가 발생했습니다.")

    async def search_seed_nodes(self, query: str) -> SeedNodeResponse:
        """
        Search for seed nodes for network visualization.
        
        Args:
            query: Search query for seed nodes
            
        Returns:
            SeedNodeResponse with candidate nodes
        """
        try:
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Search using FTS
                await cursor.execute("""
                    SELECT s.node_id, s.label, s.definition
                    FROM subjects_fts sf
                    JOIN subjects s ON sf.node_id = s.node_id
                    WHERE sf.label MATCH ?
                    ORDER BY sf.rank
                    LIMIT 10
                """, (query,))
                
                results = await cursor.fetchall()
                
                candidates = []
                for row in results:
                    candidates.append(
                        SeedNodeCandidate(
                            node_id=row["node_id"],
                            label=row["label"],
                            definition=row["definition"] or ""
                        )
                    )
                return SeedNodeResponse(candidates=candidates)
                
        except Exception as e:
            logger.error(f"Error searching seed nodes: {e}")
            raise HTTPException(status_code=500, detail="씨앗 노드 검색 중 오류가 발생했습니다.")

# 전역 서비스 인스턴스
_network_service_instance = None

def set_network_service(database_manager: DatabaseManager):
    """전역 network service 인스턴스 설정"""
    global _network_service_instance
    _network_service_instance = NetworkService(database_manager)

@lru_cache()
def get_network_service() -> NetworkService:
    """FastAPI 의존성으로 사용할 network service 인스턴스 반환"""
    if _network_service_instance is None:
        raise RuntimeError("Network service not initialized")
    return _network_service_instance