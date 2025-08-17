import httpx
import sqlite3
import random
import time
from typing import List, Tuple, Optional, Dict
import json
from datetime import datetime

NETWORK_SERVER_URL = "http://146.190.98.230:8002"
SUBJECTS_DATABASE = "/Users/nuriseok/sh_navigator/data/subject_headings.db"

def get_all_subjects() -> List[str]:
    """데이터베이스에서 모든 주제 노드 ID를 가져옵니다."""
    with sqlite3.connect(SUBJECTS_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT node_id FROM subjects")
        subjects = cursor.fetchall()
    return [s[0] for s in subjects]

def get_subject_labels(node_ids: List[str]) -> Dict[str, str]:
    """주제 노드 ID들에 대한 라벨을 가져옵니다."""
    if not node_ids:
        return {}
    
    with sqlite3.connect(SUBJECTS_DATABASE) as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(node_ids))
        query = f"SELECT node_id, label FROM subjects WHERE node_id IN ({placeholders})"
        cursor.execute(query, node_ids)
        results = cursor.fetchall()
    
    return {node_id: label for node_id, label in results}

def get_shortest_path(httpx_client: httpx.Client, source_id: str, target_id: str) -> Optional[dict]:
    """두 노드 간의 최단 경로를 구합니다."""
    try:
        response = httpx_client.get(
            f"{NETWORK_SERVER_URL}/path/shortest",
            params={"source_id": source_id, "target_id": target_id}
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting path from {source_id} to {target_id}: {e}")
        return None

def find_long_paths(min_length: int = 10, target_count: int = 10, max_attempts: int = 5000) -> List[dict]:
    """길이가 min_length 이상인 경로들을 찾습니다."""
    
    print("주제 노드들을 가져오는 중...")
    subjects = get_all_subjects()
    print(f"총 {len(subjects)}개의 주제 노드를 찾았습니다.")
    
    if len(subjects) < 2:
        print("충분한 주제 노드가 없습니다.")
        return []
    
    httpx_client = httpx.Client(timeout=30.0)
    
    long_paths = []
    attempts = 0
    successful_requests = 0
    failed_requests = 0
    
    print(f"길이 {min_length} 이상인 경로 {target_count}개를 찾는 중...")
    
    while len(long_paths) < target_count and attempts < max_attempts:
        attempts += 1
        
        # 랜덤하게 두 개의 다른 노드 선택
        source_id, target_id = random.sample(subjects, 2)
        
        # 최단 경로 구하기
        path_data = get_shortest_path(httpx_client, source_id, target_id)
        
        if path_data and 'path' in path_data and path_data['path'] is not None:
            path_length = len(path_data['path']) - 1  # 노드 개수 - 1 = 엣지 개수
            successful_requests += 1
            
            if path_length >= min_length:
                # 모든 노드의 라벨을 가져오기
                node_labels = get_subject_labels(path_data['path'])
                
                path_info = {
                    "source_id": source_id,
                    "target_id": target_id,
                    "path_length": path_length,
                    "path": path_data['path'],
                    "path_with_labels": [
                        {
                            "node_id": node_id,
                            "label": node_labels.get(node_id, "라벨 없음")
                        }
                        for node_id in path_data['path']
                    ]
                }
                long_paths.append(path_info)
                print(f"발견: {len(long_paths)}/{target_count} - 길이 {path_length} 경로")
        else:
            failed_requests += 1
        
        if attempts % 500 == 0:
            print(f"진행률: {attempts}/{max_attempts} 시도, {len(long_paths)}개 발견, 성공률: {successful_requests/(successful_requests+failed_requests)*100:.1f}%")
    
    httpx_client.close()
    
    print(f"\n=== 검색 완료 ===")
    print(f"총 시도 횟수: {attempts}")
    print(f"발견된 긴 경로: {len(long_paths)}개")
    print(f"성공률: {successful_requests/(successful_requests+failed_requests)*100:.1f}%")
    
    return long_paths

def display_paths(paths: List[dict]):
    """경로들을 보기 좋게 출력합니다."""
    for i, path_info in enumerate(paths, 1):
        print(f"\n=== 경로 {i} (길이: {path_info['path_length']}) ===")
        print(f"시작: {path_info['source_id']}")
        print(f"종료: {path_info['target_id']}")
        print("\n경로:")
        
        for j, node_info in enumerate(path_info['path_with_labels']):
            arrow = " → " if j < len(path_info['path_with_labels']) - 1 else ""
            print(f"  {j+1}. {node_info['node_id']} - {node_info['label']}{arrow}")

def save_long_paths(paths: List[dict], filename: str = None):
    """긴 경로들을 파일에 저장합니다."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"long_paths_results_{timestamp}.json"
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_paths_found": len(paths),
        "paths": paths
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"결과가 {filename}에 저장되었습니다.")

def main():
    """메인 함수"""
    print("=== 긴 경로 찾기 ===\n")
    
    # 최소 경로 길이 설정
    min_length = int(input("최소 경로 길이를 입력하세요 (기본값: 10): ").strip() or "10")
    target_count = int(input("찾을 경로 개수를 입력하세요 (기본값: 10): ").strip() or "10")
    
    print(f"\n길이 {min_length} 이상인 경로 {target_count}개를 찾습니다...")
    
    # 긴 경로 찾기
    long_paths = find_long_paths(min_length=min_length, target_count=target_count)
    
    if not long_paths:
        print("조건에 맞는 경로를 찾지 못했습니다.")
        return
    
    # 결과 출력
    display_paths(long_paths)
    
    # 결과 저장
    save_long_paths(long_paths)
    print("\n검색이 완료되었습니다!")

if __name__ == "__main__":
    main()