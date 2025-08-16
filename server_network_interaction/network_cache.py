import logging
import aiosqlite
import networkx as nx
import json
import os
from tqdm import tqdm
from typing import Dict, Optional, Any, List
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
        self._graph: Optional[nx.MultiDiGraph] = None
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
                self._graph = nx.MultiDiGraph()
                self._initialized = True
                return
            
            async with aiosqlite.connect(DATABASE_PATH) as conn:
                conn.row_factory = aiosqlite.Row
                
                # NetworkX 그래프 생성
                self._graph = nx.MultiDiGraph()
                
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
                        key=relation['relation_type'],
                        **metadata
                    )
                
                node_count = self._graph.number_of_nodes()
                edge_count = self._graph.number_of_edges()
                logger.info(f"Network graph loaded successfully: {node_count} nodes, {edge_count} edges")
                self._initialized = True
                
        except Exception as e:
            logger.error(f"Failed to initialize network graph cache: {e}")
            # 실패 시 빈 그래프로 초기화
            self._graph = nx.MultiDiGraph()
            self._initialized = True
    
    def get_graph(self) -> Optional[nx.MultiDiGraph]:
        """
        전체 네트워크 그래프 반환
        
        Returns:
            NetworkX MultiDiGraph 객체 또는 None
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
    
    def get_node_neighbors(self, node_id: str, limit: int, relation_type: Optional[str] = None) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        특정 노드의 이웃 노드들과 연결 정보 반환
        
        Args:
            node_id: 노드 ID
            limit: 이웃 노드 수 제한
            relation_type: 특정 관계 타입만 필터링 (선택사항)
            
        Returns:
            이웃 노드 정보 딕셔너리 {neighbor_id: [edge_info_list]}
        """
        if not self._initialized or self._graph is None:
            return None
        
        if node_id not in self._graph.nodes():
            return None
        
        nodes = []
        edges = []
        

        limit_count = 0

        for neighbor_id in self._graph.neighbors(node_id):
            if limit_count >= limit:
                break

            node_data = dict(self._graph.nodes[neighbor_id])
            node_data['node_id'] = neighbor_id
            nodes.append(node_data)
            
            # MultiDiGraph에서 같은 노드 쌍 간의 모든 엣지 가져오기
            for edge_key, edge_data in self._graph[node_id][neighbor_id].items():
                # relation_type 필터링
                if relation_type and edge_data.get('relation_type') != relation_type:
                    continue
                
                edges.append({
                    'source_id': node_id,
                    'target_id': neighbor_id,
                    **edge_data
                })
            
            limit_count += 1
        
        return nodes, edges
    
    def get_shortest_path(self, source_id: str, target_id: str, relation_type: Optional[str] = None) -> Optional[list]:
        """
        두 노드 간의 최단 경로 반환
        
        Args:
            source_id: 시작 노드 ID
            target_id: 목표 노드 ID
            relation_type: 특정 관계 타입만 사용 (선택사항)
            
        Returns:
            최단 경로 노드 리스트 또는 None
        """
        if not self._initialized or self._graph is None:
            return None
        
        if source_id not in self._graph.nodes() or target_id not in self._graph.nodes():
            return None
        
        try:
            # 특정 relation_type만 사용하는 경우 서브그래프 생성
            if relation_type:
                # 해당 relation_type을 가진 엣지만 포함하는 서브그래프 생성
                filtered_edges = []
                for u, v, key, data in self._graph.edges(keys=True, data=True):
                    if data.get('relation_type') == relation_type:
                        filtered_edges.append((u, v))
                
                # 필터링된 엣지로 새 그래프 생성
                subgraph = nx.DiGraph()
                subgraph.add_nodes_from(self._graph.nodes())
                subgraph.add_edges_from(filtered_edges)
                
                path = nx.shortest_path(subgraph, source_id, target_id)
            else:
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
            'is_connected': nx.is_weakly_connected(self._graph),
            'number_of_components': nx.number_weakly_connected_components(self._graph),
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
        
        # relation_type별 엣지 수 통계
        relation_stats = {}
        for _, _, data in self._graph.edges(data=True):
            rel_type = data.get('relation_type', 'unknown')
            relation_stats[rel_type] = relation_stats.get(rel_type, 0) + 1
        
        stats['relation_types'] = relation_stats
        
        return stats
    
    def get_edges_between_nodes(self, node1: str, node2: str, relation_type: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
        """
        두 노드 간의 모든 엣지 반환
        
        Args:
            node1: 첫 번째 노드 ID
            node2: 두 번째 노드 ID
            relation_type: 특정 관계 타입만 필터링 (선택사항)
            
        Returns:
            엣지 정보 리스트
        """
        if not self._initialized or self._graph is None:
            return None
        
        if node1 not in self._graph.nodes() or node2 not in self._graph.nodes():
            return None
        
        if not self._graph.has_edge(node1, node2):
            return []
        
        edges = []
        for edge_key, edge_data in self._graph[node1][node2].items():
            if relation_type and edge_data.get('relation_type') != relation_type:
                continue
            
            edges.append({
                'edge_key': edge_key,
                'edge_info': edge_data
            })
        
        return edges
    
    def get_relation_types(self) -> Optional[List[str]]:
        """
        그래프에 존재하는 모든 relation_type 반환
        
        Returns:
            relation_type 리스트
        """
        if not self._initialized or self._graph is None:
            return None
        
        relation_types = set()
        for _, _, data in self._graph.edges(data=True):
            if 'relation_type' in data:
                relation_types.add(data['relation_type'])
        
        return list(relation_types)
    
    def get_nodes_with_relation_type(self, relation_type: str) -> Optional[List[Dict[str, Any]]]:
        """
        특정 relation_type을 가진 엣지와 연결된 모든 노드들 반환
        
        Args:
            relation_type: 찾을 관계 타입
            
        Returns:
            노드 정보 리스트
        """
        if not self._initialized or self._graph is None:
            return None
        
        connected_nodes = set()
        for u, v, data in self._graph.edges(data=True):
            if data.get('relation_type') == relation_type:
                connected_nodes.add(u)
                connected_nodes.add(v)
        
        result = []
        for node_id in connected_nodes:
            node_data = dict(self._graph.nodes[node_id])
            node_data['node_id'] = node_id
            result.append(node_data)
        
        return result
    
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
