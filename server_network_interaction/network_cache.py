import logging
import aiosqlite
import networkx as nx
import json
import os
from tqdm import tqdm
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="/home/namu101/msga/env")

# Database configuration
DATA_DIR = "/home/namu101/msga/data"
DATABASE_PATH = os.path.join(DATA_DIR, 'sh_navigator.db')  # 통합된 단일 데이터베이스

logger = logging.getLogger(__name__)


class NetworkModelCache:
    """
    네트워크 모델 캐시 클래스
    
    별도의 FastAPI 서버에서 실행되는 네트워크 그래프 캐시
    메모리 사용량이 많은 NetworkX 그래프를 전담 처리
    """
    
    def __init__(self):
        self._graph: Optional[nx.Graph] = None
        self._initialized = False
    
    async def initialize(self):
        """네트워크 그래프 캐시 초기화"""
        if self._initialized:
            logger.info("Network cache already initialized")
            return
        
        try:
            logger.info(f"Initializing network cache from database: {DATABASE_PATH}")
            
            if not os.path.exists(DATABASE_PATH):
                logger.error(f"Database file not found: {DATABASE_PATH}")
                # 빈 그래프로 초기화
                self._graph = nx.Graph()
                self._initialized = True
                return
            
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                
                # NetworkX 그래프 생성 (무방향 그래프)
                self._graph = nx.Graph()
                
                # 노드 로드 (subjects 테이블에서)
                cursor = await conn.cursor()
                await cursor.execute("""
                    SELECT node_id, label, definition, community, is_important, is_updated 
                    FROM subjects
                """)
                subjects = await cursor.fetchall()
                
                if not subjects:
                    logger.warning("No subjects found in database")
                
                # 노드를 그래프에 추가
                for subject in tqdm(subjects, desc="Loading nodes"):
                    self._graph.add_node(
                        subject['node_id'],
                        label=subject['label'],
                        definition=subject['definition'],
                        community=subject['community'],
                        is_important=bool(subject['is_important']),
                        is_updated=bool(subject['is_updated'])
                    )
                
                # 엣지 로드 (relations 테이블에서)
                await cursor.execute("""
                    SELECT source_id, target_id, relation_type, metadata 
                    FROM relations
                """)
                relations = await cursor.fetchall()
                
                if not relations:
                    logger.warning("No relations found in database")
                
                # 엣지를 그래프에 추가
                for relation in tqdm(relations, desc="Loading edges"):
                    # metadata가 JSON 문자열인 경우 파싱
                    metadata = {}
                    if relation['metadata']:
                        try:
                            metadata = json.loads(relation['metadata'])
                        except (json.JSONDecodeError, TypeError):
                            # JSON 파싱 실패 시 문자열 그대로 저장
                            metadata = {'raw': relation['metadata']}
                    
                    self._graph.add_edge(
                        relation['source_id'],
                        relation['target_id'],
                        relation_type=relation['relation_type'],
                        **metadata
                    )
                
                node_count = self._graph.number_of_nodes()
                edge_count = self._graph.number_of_edges()
                logger.info(f"Network graph loaded successfully: {node_count} nodes, {edge_count} edges")
                self._initialized = True
                
        except Exception as e:
            logger.error(f"Failed to initialize network graph cache: {e}")
            # 실패 시 빈 그래프로 초기화
            self._graph = nx.Graph()
            self._initialized = True
    
    def get_graph(self) -> Optional[nx.Graph]:
        """
        전체 네트워크 그래프 반환
        
        Returns:
            NetworkX Graph 객체 또는 None
        """
        if not self._initialized:
            return None
        return self._graph
    
    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 노드의 정보 반환
        
        Args:
            node_id: 노드 ID
            
        Returns:
            노드 정보 딕셔너리 또는 None
        """
        if not self._initialized or self._graph is None:
            return None
        
        if node_id not in self._graph.nodes():
            return None
        
        return dict(self._graph.nodes[node_id])
    
    def get_node_neighbors(self, node_id: str) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        특정 노드의 이웃 노드들과 연결 정보 반환
        
        Args:
            node_id: 노드 ID
            
        Returns:
            이웃 노드 정보 딕셔너리 {neighbor_id: {node_info, edge_info}}
        """
        if not self._initialized or self._graph is None:
            return None
        
        if node_id not in self._graph.nodes():
            return None
        
        neighbors = {}
        for neighbor in self._graph.neighbors(node_id):
            edge_data = self._graph[node_id][neighbor]
            node_data = dict(self._graph.nodes[neighbor])
            
            neighbors[neighbor] = {
                'node_info': node_data,
                'edge_info': edge_data
            }
        
        return neighbors
    
    def get_shortest_path(self, source_id: str, target_id: str) -> Optional[list]:
        """
        두 노드 간의 최단 경로 반환
        
        Args:
            source_id: 시작 노드 ID
            target_id: 목표 노드 ID
            
        Returns:
            최단 경로 노드 리스트 또는 None
        """
        if not self._initialized or self._graph is None:
            return None
        
        if source_id not in self._graph.nodes() or target_id not in self._graph.nodes():
            return None
        
        try:
            path = nx.shortest_path(self._graph, source_id, target_id)
            return path
        except nx.NetworkXNoPath:
            return None
    
    def get_nodes_by_community(self, community: int) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        특정 커뮤니티에 속한 노드들 반환
        
        Args:
            community: 커뮤니티 번호
            
        Returns:
            커뮤니티 노드 정보 딕셔너리
        """
        if not self._initialized or self._graph is None:
            return None
        
        community_nodes = {}
        for node_id, node_data in self._graph.nodes(data=True):
            if node_data.get('community') == community:
                community_nodes[node_id] = node_data
        
        return community_nodes
    
    def get_important_nodes(self) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        중요한 노드들 반환
        
        Returns:
            중요 노드 정보 딕셔너리
        """
        if not self._initialized or self._graph is None:
            return None
        
        important_nodes = {}
        for node_id, node_data in self._graph.nodes(data=True):
            if node_data.get('is_important', False):
                important_nodes[node_id] = node_data
        
        return important_nodes
    
    def get_graph_stats(self) -> Optional[Dict[str, Any]]:
        """
        그래프 통계 정보 반환
        
        Returns:
            그래프 통계 딕셔너리
        """
        if not self._initialized or self._graph is None:
            return None
        
        stats = {
            'total_nodes': self._graph.number_of_nodes(),
            'total_edges': self._graph.number_of_edges(),
            'is_connected': nx.is_connected(self._graph),
            'number_of_components': nx.number_connected_components(self._graph),
            'density': nx.density(self._graph)
        }
        
        # 중요 노드 수 계산
        important_count = sum(1 for _, data in self._graph.nodes(data=True) 
                            if data.get('is_important', False))
        stats['important_nodes'] = important_count
        
        # 커뮤니티 수 계산
        communities = set()
        for _, data in self._graph.nodes(data=True):
            community = data.get('community')
            if community is not None:
                communities.add(community)
        stats['communities'] = len(communities)
        
        return stats
    
    async def refresh(self):
        """캐시 새로고침"""
        logger.info("Refreshing network cache...")
        self._initialized = False
        self._graph = None
        await self.initialize()
        logger.info("Network cache refresh completed")


# 전역 인스턴스
_network_cache_instance: Optional[NetworkModelCache] = None


def get_network_cache() -> NetworkModelCache:
    """전역 네트워크 캐시 인스턴스 반환"""
    global _network_cache_instance
    if _network_cache_instance is None:
        _network_cache_instance = NetworkModelCache()
    return _network_cache_instance


async def initialize_network_cache():
    """전역 네트워크 캐시 초기화"""
    cache = get_network_cache()
    await cache.initialize()
