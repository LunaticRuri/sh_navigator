from functools import lru_cache
import logging
import httpx
from typing import List, Dict
from fastapi import HTTPException
from database.database_manager import DatabaseManager
from core.kdc_cache import get_kdc_cache
from schemas.network import NetworkResponse, SeedNodeResponse

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
        self.kdc_cache = get_kdc_cache()
    
        
    async def get_node_neighbors(self, node_id: str, limit: int = 10) -> NetworkResponse:
        """
        Get neighbors of a specific node for network visualization.
        
        Args:
            node_id: Central node ID
            limit: Maximum number of neighbor nodes
            
        Returns:
            NetworkResponse with nodes and edges
        """
        try:
            # Validate limit
            limit = min(limit, MAX_NETWORK_NEIGHBORS)
            
            async with self.database_manager.get_connection() as conn:
                cursor = await conn.cursor()
                
                # Get current node information
                await cursor.execute(
                    "SELECT node_id, label, definition FROM subjects WHERE node_id = ?", 
                    (node_id,)
                )
                current_node = await cursor.fetchone()
                
                if not current_node:
                    raise HTTPException(status_code=404, detail="노드를 찾을 수 없습니다.")
                
                
                neighbors = await self._get_node_neighbors(cursor, node_id, limit)
                
                # Build network response
                nodes = [
                    {
                        "node_id": current_node["node_id"],
                        "label": current_node["label"],
                        "definition": current_node["definition"] or "",
                        "type": "current"
                    }
                ]
                
                edges = []
                
                for neighbor in neighbors:
                    nodes.append({
                        "node_id": neighbor["neighbor_id"],
                        "label": neighbor["label"],
                        "definition": neighbor["definition"] or "",
                        "type": "neighbor"
                    })
                    
                    edges.append({
                        "source": node_id,
                        "target": neighbor["neighbor_id"],
                        "relation_type": neighbor["relation_type"],
                        "metadata": neighbor["metadata"]
                    })
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "center_node": node_id
                }
                
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
                    candidates.append({
                        "node_id": row["node_id"],
                        "label": row["label"],
                        "definition": row["definition"] or ""
                    })
                
                return {"candidates": candidates}
                
        except Exception as e:
            logger.error(f"Error searching seed nodes: {e}")
            raise HTTPException(status_code=500, detail="씨앗 노드 검색 중 오류가 발생했습니다.")

    async def _get_node_neighbors(self, cursor, node_id: str, limit: int) -> List[Dict]:
        """
        Get neighbor nodes for network visualization and kdc access points.
        
        Args:
            cursor: Database cursor
            node_id: Central node ID
            limit: Maximum number of neighbors
            
        Returns:
            List of neighbor dictionaries
        """
        await cursor.execute("""
            SELECT DISTINCT
                CASE 
                    WHEN r.source_id = ? THEN r.target_id
                    ELSE r.source_id
                END as neighbor_id,
                s.label,
                s.definition,
                r.relation_type,
                r.metadata
            FROM relations r
            JOIN subjects s ON (
                (r.source_id = ? AND s.node_id = r.target_id) OR
                (r.target_id = ? AND s.node_id = r.source_id)
            )
            WHERE r.source_id = ? OR r.target_id = ?
            ORDER BY 
                CASE 
                    WHEN r.relation_type != 'cosine_related' THEN 0 
                    ELSE 1 
                END,
                CASE 
                    WHEN r.relation_type = 'cosine_related' THEN 
                        CAST(json_extract(r.metadata, '$.similarity') AS REAL)
                    ELSE 0
                END DESC
            LIMIT ?
        """, (node_id, node_id, node_id, node_id, node_id, limit))
        
        return await cursor.fetchall()

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