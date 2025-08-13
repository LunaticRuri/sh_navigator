import httpx
import sqlite3
import random
import time
from typing import List, Tuple, Optional
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

def calculate_average_shortest_path_length(sample_size: int = 1000, max_retries: int = 3) -> dict:
    """주제 노드들 간의 평균 최단 경로 길이를 계산합니다."""
    
    print("주제 노드들을 가져오는 중...")
    subjects = get_all_subjects()
    print(f"총 {len(subjects)}개의 주제 노드를 찾았습니다.")
    
    if len(subjects) < 2:
        return {"error": "충분한 주제 노드가 없습니다."}
    
    # 샘플 크기 조정
    actual_sample_size = min(sample_size, len(subjects) * (len(subjects) - 1) // 2)
    print(f"샘플 크기: {actual_sample_size}")
    
    httpx_client = httpx.Client(timeout=30.0)
    
    path_lengths = []
    successful_requests = 0
    failed_requests = 0
    
    print("최단 경로들을 계산하는 중...")
    
    for i in range(actual_sample_size):
        # 랜덤하게 두 개의 다른 노드 선택
        source_id, target_id = random.sample(subjects, 2)
        
        # 최단 경로 구하기 (재시도 로직 포함)
        path_data = None
        for retry in range(max_retries):
            path_data = get_shortest_path(httpx_client, source_id, target_id)
            if path_data is not None:
                break
            if retry < max_retries - 1:
                time.sleep(1)  # 재시도 전 잠시 대기
        
        if path_data and 'path' in path_data and path_data['path'] is not None:
            path_length = len(path_data['path']) - 1  # 노드 개수 - 1 = 엣지 개수
            if path_length >= 0:  # 유효한 경로 길이인지 확인
                path_lengths.append(path_length)
                successful_requests += 1
                
                if successful_requests % 50 == 0:
                    print(f"진행률: {successful_requests}/{actual_sample_size} ({successful_requests/actual_sample_size*100:.1f}%)")
            else:
                failed_requests += 1
        else:
            failed_requests += 1
    
    httpx_client.close()
    
    if not path_lengths:
        return {"error": "성공적인 경로 계산이 없습니다."}
    
    # 통계 계산
    average_length = sum(path_lengths) / len(path_lengths)
    min_length = min(path_lengths)
    max_length = max(path_lengths)
    
    # 경로 길이별 분포
    length_distribution = {}
    for length in path_lengths:
        length_distribution[length] = length_distribution.get(length, 0) + 1
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_subjects": len(subjects),
        "sample_size": actual_sample_size,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "average_path_length": round(average_length, 3),
        "min_path_length": min_length,
        "max_path_length": max_length,
        "path_lengths_sample": path_lengths[:10],  # 처음 10개 샘플
        "length_distribution": dict(sorted(length_distribution.items()))
    }
    
    return results

def save_results(results: dict, filename: str = None):
    """결과를 파일에 저장합니다."""
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"average_path_length_results_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"결과가 {filename}에 저장되었습니다.")

def main():
    """메인 함수"""
    print("=== 주제 노드 평균 최단 경로 길이 계산 ===\n")
    
    # 샘플 크기 설정 (너무 크면 시간이 오래 걸림)
    sample_size = int(input("샘플 크기를 입력하세요 (기본값: 1000): ").strip() or "1000")
    
    print(f"\n{sample_size}개의 노드 쌍에 대해 최단 경로를 계산합니다...")
    
    # 계산 실행
    results = calculate_average_shortest_path_length(sample_size=sample_size)
    
    if "error" in results:
        print(f"오류: {results['error']}")
        return
    
    # 결과 출력
    print("\n=== 결과 ===")
    print(f"총 주제 수: {results['total_subjects']:,}")
    print(f"샘플 크기: {results['sample_size']:,}")
    print(f"성공한 요청: {results['successful_requests']:,}")
    print(f"실패한 요청: {results['failed_requests']:,}")
    print(f"평균 최단 경로 길이: {results['average_path_length']}")
    print(f"최소 경로 길이: {results['min_path_length']}")
    print(f"최대 경로 길이: {results['max_path_length']}")
    
    print("\n경로 길이별 분포:")
    for length, count in results['length_distribution'].items():
        percentage = (count / results['successful_requests']) * 100
        print(f"  길이 {length}: {count}개 ({percentage:.1f}%)")
    
    # 결과 저장
    save_results(results)
    print("\n계산이 완료되었습니다!")

if __name__ == "__main__":
    main()