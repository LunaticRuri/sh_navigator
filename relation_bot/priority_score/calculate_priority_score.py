#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Priority Score Calculator for Subject Headings Network

이 스크립트는 subject headings 네트워크에서 각 노드의 우선순위 점수를 계산합니다.
우선순위 점수 = 0.4 * PageRank + 0.6 * 정규화된 책 수
"""

import sqlite3
import networkx as nx
import json
import argparse
from typing import Dict, Tuple
import logging
from tqdm import tqdm

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_network_from_db(db_path: str) -> Tuple[nx.DiGraph, Dict[str, dict]]:
    """
    데이터베이스에서 네트워크를 로드합니다.
    
    Args:
        db_path: SQLite 데이터베이스 경로
        
    Returns:
        Tuple[nx.DiGraph, Dict[str, dict]]: 네트워크 그래프와 노드 정보
    """
    logger.info(f"데이터베이스에서 네트워크 로드 중: {db_path}")
    
    G = nx.DiGraph()
    node_info = {}
    
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 모든 노드 로드
            cursor.execute("""
                SELECT node_id, label, definition, community, is_important, is_updated
                FROM subjects
            """)
            nodes = cursor.fetchall()
            
            logger.info(f"노드 {len(nodes)}개 로드됨")
            
            for node in nodes:
                node_id = node['node_id']
                G.add_node(node_id)
                node_info[node_id] = {
                    'label': node['label'],
                    'definition': node['definition'],
                    'community': node['community'],
                    'is_important': node['is_important'],
                    'is_updated': node['is_updated']
                }
            
            # 모든 관계 로드
            cursor.execute("""
                SELECT source_id, target_id, relation_type, metadata
                FROM relations
            """)
            relations = cursor.fetchall()
            
            logger.info(f"관계 {len(relations)}개 로드됨")
            
            for relation in relations:
                source_id = relation['source_id']
                target_id = relation['target_id']
                relation_type = relation['relation_type']
                metadata = relation['metadata']
                
                # 메타데이터에서 가중치 추출 (있는 경우)
                weight = 1.0
                if metadata:
                    try:
                        meta_dict = json.loads(metadata)
                        weight = float(meta_dict.get('weight', 1.0))
                    except (json.JSONDecodeError, ValueError):
                        weight = 1.0
                
                G.add_edge(source_id, target_id, 
                          relation_type=relation_type, 
                          weight=weight, 
                          metadata=metadata)
    
    except sqlite3.Error as e:
        logger.error(f"데이터베이스 오류: {e}")
        raise
    
    logger.info(f"네트워크 로드 완료: {G.number_of_nodes()}개 노드, {G.number_of_edges()}개 엣지")
    return G, node_info


def load_book_counts(db_path: str) -> Dict[str, int]:
    """
    각 주제(node_id)에 대응하는 책의 수를 로드합니다.
    
    Args:
        db_path: SQLite 데이터베이스 경로
        
    Returns:
        Dict[str, int]: 각 노드의 책 수
    """
    logger.info("각 주제별 책 수 로드 중...")
    
    book_counts = {}
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 각 주제별 책 수 계산
            cursor.execute("""
                SELECT node_id, COUNT(DISTINCT isbn) as book_count
                FROM book_subject_index
                GROUP BY node_id
            """)
            
            results = cursor.fetchall()
            
            for node_id, count in results:
                book_counts[node_id] = count
            
            logger.info(f"책 수 정보 로드 완료: {len(book_counts)}개 주제")
    
    except sqlite3.Error as e:
        logger.warning(f"책 수 로드 중 오류 (book_subject_index 테이블이 없을 수 있음): {e}")
        # 테이블이 없는 경우 빈 딕셔너리 반환
        return {}
    
    return book_counts


def calculate_pagerank(G: nx.DiGraph) -> Dict[str, float]:
    """
    PageRank를 계산합니다.
    
    Args:
        G: 네트워크 그래프
        
    Returns:
        Dict[str, float]: 각 노드의 정규화된 PageRank 값
    """
    logger.info("PageRank 계산 시작...")
    
    try:
        # 가중치를 고려한 PageRank 계산
        pagerank_scores = nx.pagerank(G, alpha=0.85, max_iter=100, tol=1e-06, weight='weight')
        
        logger.info(f"PageRank 계산 완료: {len(pagerank_scores)}개 노드")
        
        # 점수 정규화 (0-1 범위)
        max_score = max(pagerank_scores.values()) if pagerank_scores else 1.0
        normalized_scores = {node: score / max_score for node, score in pagerank_scores.items()}
        
        return normalized_scores
    
    except Exception as e:
        logger.error(f"PageRank 계산 오류: {e}")
        raise


def calculate_priority_score(pagerank_scores: Dict[str, float], book_counts: Dict[str, int], 
                           pagerank_weight: float = 0.5, book_count_weight: float = 0.5) -> Dict[str, float]:
    """
    PageRank와 책 수를 결합한 우선순위 점수를 계산합니다.
    
    Args:
        pagerank_scores: 정규화된 PageRank 점수
        book_counts: 각 노드의 책 수
        pagerank_weight: PageRank 가중치 (기본값: 0.5)
        book_count_weight: 책 수 가중치 (기본값: 0.5)
        
    Returns:
        Dict[str, float]: 각 노드의 우선순위 점수
    """
    logger.info("우선순위 점수 계산 시작...")
    
    # 책 수 정규화 (0-1 범위)
    if book_counts:
        max_book_count = max(book_counts.values()) if book_counts.values() else 1
        normalized_book_counts = {node: count / max_book_count for node, count in book_counts.items()}
    else:
        normalized_book_counts = {}
    
    # 우선순위 점수 계산
    priority_scores = {}
    
    for node_id in pagerank_scores:
        pagerank = pagerank_scores.get(node_id, 0.0)
        book_count_norm = normalized_book_counts.get(node_id, 0.0)
        
        # 가중 평균 계산
        priority_score = (pagerank_weight * pagerank) + (book_count_weight * book_count_norm)
        priority_scores[node_id] = priority_score
    
    logger.info(f"우선순위 점수 계산 완료: {len(priority_scores)}개 노드")
    
    return priority_scores


def update_database_with_priority_score(db_path: str, priority_scores: Dict[str, float]) -> None:
    """
    데이터베이스에 우선순위 점수를 업데이트합니다.
    
    Args:
        db_path: SQLite 데이터베이스 경로
        priority_scores: 각 노드의 우선순위 점수
    """
    logger.info("데이터베이스에 우선순위 점수 업데이트 중...")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # priority_score 컬럼이 없는 경우 추가
            cursor.execute("PRAGMA table_info(subjects)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'priority_score' not in columns:
                logger.info("subjects 테이블에 priority_score 컬럼 추가")
                cursor.execute("ALTER TABLE subjects ADD COLUMN priority_score REAL DEFAULT 0.0")
            
            # 우선순위 점수 업데이트
            update_count = 0
            for node_id, score in tqdm(priority_scores.items()):
                cursor.execute("""
                    UPDATE subjects 
                    SET priority_score = ?
                    WHERE node_id = ?
                """, (score, node_id))
                
                if cursor.rowcount > 0:
                    update_count += 1
                conn.commit()
            
            logger.info(f"우선순위 점수 업데이트 완료: {update_count}개 노드")
    
    except sqlite3.Error as e:
        logger.error(f"데이터베이스 업데이트 오류: {e}")
        raise


def export_priority_results(priority_scores: Dict[str, float], pagerank_scores: Dict[str, float],
                          book_counts: Dict[str, int], node_info: Dict[str, dict], output_file: str) -> None:
    """
    우선순위 점수 결과를 파일로 내보냅니다.
    
    Args:
        priority_scores: 우선순위 점수
        pagerank_scores: PageRank 점수
        book_counts: 책 수
        node_info: 노드 정보
        output_file: 출력 파일 경로
    """
    logger.info(f"우선순위 점수 결과를 파일로 내보내는 중: {output_file}")
    
    # 우선순위 점수로 정렬
    sorted_nodes = sorted(priority_scores.items(), key=lambda x: x[1], reverse=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("rank\tnode_id\tlabel\tpriority_score\tpagerank\tbook_count\tcommunity\tis_important\n")
        
        for rank, (node_id, priority_score) in enumerate(sorted_nodes, 1):
            info = node_info.get(node_id, {})
            label = info.get('label', 'N/A')
            pagerank = pagerank_scores.get(node_id, 0.0)
            book_count = book_counts.get(node_id, 0)
            community = info.get('community', 'N/A')
            is_important = info.get('is_important', 0)
            
            f.write(f"{rank}\t{node_id}\t{label}\t{priority_score:.6f}\t{pagerank:.6f}\t{book_count}\t{community}\t{is_important}\n")
    
    logger.info(f"결과 내보내기 완료: {len(sorted_nodes)}개 노드")


def print_top_priority_nodes(priority_scores: Dict[str, float], pagerank_scores: Dict[str, float],
                           book_counts: Dict[str, int], node_info: Dict[str, dict], top_n: int = 20) -> None:
    """
    상위 N개 노드를 우선순위 점수 기준으로 출력합니다.
    """
    print(f"\n=== 상위 {top_n}개 노드 (우선순위 점수 기준) ===")
    print(f"{'순위':<4} {'노드ID':<20} {'라벨':<25} {'우선순위':<8} {'PageRank':<8} {'책수':<6} {'커뮤니티':<8}")
    print("-" * 85)
    
    sorted_nodes = sorted(priority_scores.items(), key=lambda x: x[1], reverse=True)
    
    for i, (node_id, priority_score) in enumerate(sorted_nodes[:top_n], 1):
        info = node_info.get(node_id, {})
        label = info.get('label', 'N/A')[:23]
        pagerank = pagerank_scores.get(node_id, 0.0)
        book_count = book_counts.get(node_id, 0)
        community = info.get('community', 'N/A')
        
        print(f"{i:<4} {node_id:<20} {label:<25} {priority_score:.4f}   {pagerank:.4f}   {book_count:<6} {community:<8}")


def main():
    parser = argparse.ArgumentParser(description='Subject Headings 네트워크의 우선순위 점수 계산')
    parser.add_argument('--db', '-d', 
                       default='/Users/nuriseok/sh_navigator/data/subject_headings.db',
                       help='SQLite 데이터베이스 경로')
    parser.add_argument('--pagerank-weight', type=float, default=0.4,
                       help='PageRank 가중치 (기본값: 0.4)')
    parser.add_argument('--book-weight', type=float, default=0.6,
                       help='책 수 가중치 (기본값: 0.6)')
    parser.add_argument('--output', '-o',
                       help='결과를 저장할 파일 경로 (선택사항)')
    parser.add_argument('--top', type=int, default=20,
                       help='출력할 상위 노드 개수 (기본값: 20)')
    parser.add_argument('--update-db', action='store_true',
                       help='계산된 우선순위 점수를 데이터베이스에 업데이트')
    
    args = parser.parse_args()
    
    # 가중치 검증
    if abs(args.pagerank_weight + args.book_weight - 1.0) > 1e-6:
        logger.warning(f"가중치 합이 1.0이 아닙니다: {args.pagerank_weight + args.book_weight}")
    
    try:
        # 네트워크 로드
        G, node_info = load_network_from_db(args.db)
        
        if G.number_of_nodes() == 0:
            logger.error("데이터베이스에서 노드를 찾을 수 없습니다.")
            return
        
        # 책 수 정보 로드
        book_counts = load_book_counts(args.db)
        
        # PageRank 계산
        pagerank_scores = calculate_pagerank(G)
        
        # 우선순위 점수 계산
        priority_scores = calculate_priority_score(
            pagerank_scores, book_counts, 
            args.pagerank_weight, args.book_weight
        )
        
        # 결과 출력
        print_top_priority_nodes(priority_scores, pagerank_scores, book_counts, node_info, args.top)
        
        # 간단한 통계 출력
        print(f"\n=== 우선순위 점수 통계 ===")
        priority_values = list(priority_scores.values())
        book_values = list(book_counts.values()) if book_counts else [0]
        
        print(f"전체 노드 수: {len(priority_values)}")
        print(f"책 정보가 있는 노드 수: {len(book_counts)}")
        print(f"우선순위 점수 - 최대: {max(priority_values):.4f}, 최소: {min(priority_values):.4f}, 평균: {sum(priority_values)/len(priority_values):.4f}")
        print(f"책 수 - 최대: {max(book_values)}, 평균: {sum(book_values)/len(book_values):.1f}")
        
        # 데이터베이스 업데이트
        if args.update_db:
            update_database_with_priority_score(args.db, priority_scores)
        
        # 파일 출력
        if args.output:
            export_priority_results(priority_scores, pagerank_scores, book_counts, node_info, args.output)
        
        logger.info("우선순위 점수 계산이 성공적으로 완료되었습니다.")
    
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        raise


if __name__ == "__main__":
    main()
