import pandas as pd
import sqlite3
import numpy as np
from collections import defaultdict, deque
import os
import random

def get_important_nodes_by_community(csv_file_path, db_file_path, output_file_path=None):
    """
    각 커뮤니티별로 degree 상위 10%의 중요 노드를 추출합니다.
    단, 각 커뮤니티마다 최소 하나의 노드는 포함됩니다.
    
    Args:
        csv_file_path (str): network_nodes.csv 파일 경로
        db_file_path (str): subject_headings.db 파일 경로
        output_file_path (str, optional): 결과를 저장할 CSV 파일 경로
    
    Returns:
        pd.DataFrame: 중요 노드 정보가 담긴 데이터프레임
    """
    
    # CSV 파일 읽기
    print("Loading network nodes data...")
    df = pd.read_csv(csv_file_path)
    
    # 데이터베이스 연결
    print("Connecting to database...")
    conn = sqlite3.connect(db_file_path)
    
    # 각 커뮤니티별로 그룹화
    communities = df.groupby('community')
    
    important_nodes = []
    
    print(f"Processing {len(communities)} communities...")
    
    for community_id, community_df in communities:
        # 커뮤니티 내 노드 개수
        total_nodes = len(community_df)
        
        # 상위 10% 계산 (최소 1개)
        top_5_percent_count = max(1, int(np.ceil(total_nodes * 0.1)))
        
        # degree 기준으로 내림차순 정렬하여 상위 노드 선택
        top_nodes = community_df.nlargest(top_5_percent_count, 'degree')
        
        # 각 노드에 대해 라벨 정보 가져오기
        for _, node_row in top_nodes.iterrows():
            doc_id = node_row['doc_id']
            
            # 데이터베이스에서 라벨 조회
            cursor = conn.execute(
                "SELECT label FROM subjects WHERE node_id = ?",
                (doc_id,)
            )
            result = cursor.fetchone()
            
            if result:
                label = result[0]
                important_nodes.append({
                    'community': community_id,
                    'node_id': node_row['node_id'],
                    'doc_id': doc_id,
                    'degree': node_row['degree'],
                    'label': label,
                    'total_community_nodes': total_nodes,
                    'selected_nodes_count': top_5_percent_count,
                    'rank_in_community': top_nodes.index.get_loc(node_row.name) + 1
                })
            else:
                # 라벨이 없는 경우도 포함
                important_nodes.append({
                    'community': community_id,
                    'node_id': node_row['node_id'],
                    'doc_id': doc_id,
                    'degree': node_row['degree'],
                    'label': None,
                    'total_community_nodes': total_nodes,
                    'selected_nodes_count': top_5_percent_count,
                    'rank_in_community': top_nodes.index.get_loc(node_row.name) + 1
                })
    
    conn.close()
    
    # 결과를 데이터프레임으로 변환
    result_df = pd.DataFrame(important_nodes)
    
    # 커뮤니티별로 정렬
    result_df = result_df.sort_values(['community', 'rank_in_community'])
    
    print(f"Total important nodes selected: {len(result_df)}")
    print(f"Communities processed: {result_df['community'].nunique()}")
    
    # 파일로 저장 (옵션)
    if output_file_path:
        result_df.to_csv(output_file_path, index=False, encoding='utf-8')
        print(f"Results saved to: {output_file_path}")
    
    return result_df

def analyze_community_statistics(result_df):
    """
    커뮤니티별 통계를 분석합니다.
    
    Args:
        result_df (pd.DataFrame): get_important_nodes_by_community 결과
    """
    print("\n=== Community Statistics ===")
    
    # 커뮤니티별 통계
    community_stats = result_df.groupby('community').agg({
        'total_community_nodes': 'first',
        'selected_nodes_count': 'first',
        'degree': ['mean', 'max', 'min']
    }).round(2)
    
    community_stats.columns = ['total_nodes', 'selected_nodes', 'avg_degree', 'max_degree', 'min_degree']
    
    print(f"Top 10 largest communities:")
    top_communities = community_stats.nlargest(10, 'total_nodes')
    print(top_communities)
    
    print(f"\nOverall statistics:")
    print(f"- Total communities: {len(community_stats)}")
    print(f"- Average community size: {community_stats['total_nodes'].mean():.1f}")
    print(f"- Largest community size: {community_stats['total_nodes'].max()}")
    print(f"- Smallest community size: {community_stats['total_nodes'].min()}")
    print(f"- Total important nodes: {len(result_df)}")
    
    return community_stats

def analyze_node_count_distribution(result_df):
    """
    커뮤니티별 선정된 중요 노드 개수의 분포를 분석합니다.
    
    Args:
        result_df (pd.DataFrame): get_important_nodes_by_community 결과
    """
    print("\n=== Selected Node Count Distribution ===")
    
    # 커뮤니티별 선정된 노드 개수 계산
    node_count_per_community = result_df.groupby('community')['selected_nodes_count'].first()
    
    # 분포 분석
    distribution = node_count_per_community.value_counts().sort_index()
    
    print("Distribution of selected nodes per community:")
    print("Selected Nodes | Communities | Percentage")
    print("-" * 42)
    
    total_communities = len(node_count_per_community)
    cumulative_count = 0
    
    for selected_count, community_count in distribution.items():
        cumulative_count += community_count
        percentage = (community_count / total_communities) * 100
        cumulative_percentage = (cumulative_count / total_communities) * 100
        print(f"{selected_count:12d} | {community_count:11d} | {percentage:8.2f}% (cumulative: {cumulative_percentage:.2f}%)")
    
    # 통계 요약
    print(f"\nSummary Statistics:")
    print(f"- Mean selected nodes per community: {node_count_per_community.mean():.2f}")
    print(f"- Median selected nodes per community: {node_count_per_community.median():.2f}")
    print(f"- Min selected nodes per community: {node_count_per_community.min()}")
    print(f"- Max selected nodes per community: {node_count_per_community.max()}")
    print(f"- Standard deviation: {node_count_per_community.std():.2f}")
    
    # 주요 분포 구간별 분석
    print(f"\nDistribution by ranges:")
    print(f"- Communities with 1 node: {(node_count_per_community == 1).sum()} ({((node_count_per_community == 1).sum() / total_communities * 100):.1f}%)")
    print(f"- Communities with 2-5 nodes: {((node_count_per_community >= 2) & (node_count_per_community <= 5)).sum()} ({(((node_count_per_community >= 2) & (node_count_per_community <= 5)).sum() / total_communities * 100):.1f}%)")
    print(f"- Communities with 6-10 nodes: {((node_count_per_community >= 6) & (node_count_per_community <= 10)).sum()} ({(((node_count_per_community >= 6) & (node_count_per_community <= 10)).sum() / total_communities * 100):.1f}%)")
    print(f"- Communities with 11-20 nodes: {((node_count_per_community >= 11) & (node_count_per_community <= 20)).sum()} ({(((node_count_per_community >= 11) & (node_count_per_community <= 20)).sum() / total_communities * 100):.1f}%)")
    print(f"- Communities with 21+ nodes: {(node_count_per_community >= 21).sum()} ({((node_count_per_community >= 21).sum() / total_communities * 100):.1f}%)")
    
    return node_count_per_community

def analyze_distance_to_important_nodes(db_file_path, result_df, sample_size=1000, max_distance=6):
    """
    랜덤하게 선정된 노드에서 중요 노드까지의 최단 거리를 분석합니다.
    
    Args:
        db_file_path (str): subject_headings.db 파일 경로
        result_df (pd.DataFrame): 중요 노드 정보가 담긴 데이터프레임
        sample_size (int): 분석할 랜덤 노드 개수
        max_distance (int): 탐색할 최대 거리
    
    Returns:
        dict: 거리 분석 결과
    """
    print(f"\n=== Distance Analysis to Important Nodes ===")
    print(f"Analyzing {sample_size} random nodes...")
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_file_path)
    
    # 중요 노드 집합 생성
    important_node_ids = set(result_df['doc_id'].tolist())
    print(f"Important nodes count: {len(important_node_ids)}")
    
    # 전체 노드 목록 가져오기
    cursor = conn.execute("SELECT node_id FROM subjects")
    all_nodes = [row[0] for row in cursor.fetchall()]
    print(f"Total nodes in network: {len(all_nodes)}")
    
    # 네트워크 그래프 구축 (인접 리스트)
    print("Building network graph...")
    graph = defaultdict(list)
    
    # 모든 관계를 무방향 그래프로 구축 (관계 유형 상관없이)
    cursor = conn.execute("SELECT source_id, target_id FROM relations")
    edge_count = 0
    for source, target in cursor:
        graph[source].append(target)
        graph[target].append(source)  # 무방향 그래프
        edge_count += 1
        if edge_count % 500000 == 0:
            print(f"  Processed {edge_count} edges...")
    
    print(f"Graph built with {edge_count} edges")
    
    # 랜덤 노드 샘플링
    random.seed(42)  # 재현 가능한 결과를 위해
    sample_nodes = random.sample(all_nodes, min(sample_size, len(all_nodes)))
    
    distances = []
    unreachable_count = 0
    
    print("Calculating distances...")
    for i, start_node in enumerate(sample_nodes):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(sample_nodes)} nodes...")
        
        # BFS로 최단 거리 계산
        distance = bfs_distance_to_important_nodes(graph, start_node, important_node_ids, max_distance)
        
        if distance == -1:
            unreachable_count += 1
        else:
            distances.append(distance)
    
    conn.close()
    
    # 결과 분석
    if distances:
        print(f"\n=== Distance Analysis Results ===")
        print(f"Sample size: {len(sample_nodes)}")
        print(f"Reachable nodes: {len(distances)}")
        print(f"Unreachable nodes (within {max_distance} steps): {unreachable_count}")
        print(f"Reachability rate: {(len(distances) / len(sample_nodes)) * 100:.2f}%")
        
        distances_array = np.array(distances)
        
        print(f"\nDistance Statistics:")
        print(f"- Mean distance: {distances_array.mean():.2f}")
        print(f"- Median distance: {np.median(distances_array):.2f}")
        print(f"- Min distance: {distances_array.min()}")
        print(f"- Max distance: {distances_array.max()}")
        print(f"- Standard deviation: {distances_array.std():.2f}")
        
        print(f"\nDistance Distribution:")
        distance_counts = np.bincount(distances_array)
        for distance, count in enumerate(distance_counts):
            if count > 0:
                percentage = (count / len(distances)) * 100
                print(f"- Distance {distance}: {count} nodes ({percentage:.1f}%)")
        
        return {
            'distances': distances,
            'unreachable_count': unreachable_count,
            'sample_size': len(sample_nodes),
            'reachability_rate': (len(distances) / len(sample_nodes)) * 100,
            'mean_distance': distances_array.mean(),
            'median_distance': np.median(distances_array)
        }
    else:
        print("No reachable important nodes found within the specified distance limit.")
        return None

def bfs_distance_to_important_nodes(graph, start_node, important_nodes, max_distance):
    """
    BFS를 사용하여 시작 노드에서 가장 가까운 중요 노드까지의 거리를 계산합니다.
    
    Args:
        graph (dict): 네트워크 그래프 (인접 리스트)
        start_node (str): 시작 노드 ID
        important_nodes (set): 중요 노드 ID 집합
        max_distance (int): 최대 탐색 거리
    
    Returns:
        int: 최단 거리 (-1 if unreachable within max_distance)
    """
    if start_node in important_nodes:
        return 0
    
    visited = {start_node}
    queue = deque([(start_node, 0)])
    
    while queue:
        current_node, distance = queue.popleft()
        
        if distance >= max_distance:
            continue
        
        for neighbor in graph[current_node]:
            if neighbor not in visited:
                if neighbor in important_nodes:
                    return distance + 1
                
                visited.add(neighbor)
                queue.append((neighbor, distance + 1))
    
    return -1  # 최대 거리 내에서 중요 노드에 도달할 수 없음

def find_connected_important_node_pairs(db_file_path, result_df, output_file_path=None):
    """
    중요 노드들 중에서 서로 연결된 쌍들을 찾습니다.
    
    Args:
        db_file_path (str): subject_headings.db 파일 경로
        result_df (pd.DataFrame): 중요 노드 정보가 담긴 데이터프레임
        output_file_path (str, optional): 결과를 저장할 CSV 파일 경로
    
    Returns:
        pd.DataFrame: 연결된 중요 노드 쌍들의 정보
    """
    print(f"\n=== Finding Connected Important Node Pairs ===")
    
    # 데이터베이스 연결
    conn = sqlite3.connect(db_file_path)
    
    # 중요 노드 집합 생성
    important_node_ids = set(result_df['doc_id'].tolist())
    print(f"Important nodes count: {len(important_node_ids)}")
    
    # 중요 노드 정보를 딕셔너리로 변환 (빠른 검색을 위해)
    node_info_dict = {}
    for _, row in result_df.iterrows():
        node_info_dict[row['doc_id']] = {
            'label': row['label'],
            'community': row['community'],
            'degree': row['degree'],
            'rank_in_community': row['rank_in_community']
        }
    
    # 연결된 쌍들 찾기
    connected_pairs = []
    processed_pairs = set()  # 중복 방지를 위한 집합
    
    print("Searching for connections between important nodes...")
    
    # 중요 노드들 간의 직접 연결 찾기
    cursor = conn.execute("""
        SELECT source_id, target_id, relation_type 
        FROM relations 
        WHERE source_id IN ({}) AND target_id IN ({})
    """.format(
        ','.join(['?' for _ in important_node_ids]),
        ','.join(['?' for _ in important_node_ids])
    ), list(important_node_ids) + list(important_node_ids))
    
    connection_count = 0
    for source_id, target_id, relation_type in cursor:
        # 무방향 그래프로 처리하기 위해 정렬된 순서로 쌍 생성
        pair_key = tuple(sorted([source_id, target_id]))
        
        if pair_key not in processed_pairs and source_id != target_id:
            processed_pairs.add(pair_key)
            
            source_info = node_info_dict[source_id]
            target_info = node_info_dict[target_id]
            
            # 같은 커뮤니티인지 확인
            same_community = source_info['community'] == target_info['community']
            
            connected_pairs.append({
                'source_id': source_id,
                'source_label': source_info['label'],
                'source_community': source_info['community'],
                'source_degree': source_info['degree'],
                'source_rank': source_info['rank_in_community'],
                'target_id': target_id,
                'target_label': target_info['label'],
                'target_community': target_info['community'],
                'target_degree': target_info['degree'],
                'target_rank': target_info['rank_in_community'],
                'relation_type': relation_type,
                'same_community': same_community,
                'community_distance': 0 if same_community else 1
            })
            
            connection_count += 1
            if connection_count % 1000 == 0:
                print(f"  Found {connection_count} connections...")
    
    conn.close()
    
    # 결과를 데이터프레임으로 변환
    if connected_pairs:
        pairs_df = pd.DataFrame(connected_pairs)
        
        # 관계 유형별로 정렬
        pairs_df = pairs_df.sort_values(['relation_type', 'same_community'], ascending=[True, False])
        
        print(f"\n=== Connection Analysis Results ===")
        print(f"Total connected pairs: {len(pairs_df)}")
        
        # 관계 유형별 분포
        print(f"\nConnection types distribution:")
        relation_counts = pairs_df['relation_type'].value_counts()
        for relation_type, count in relation_counts.items():
            percentage = (count / len(pairs_df)) * 100
            print(f"- {relation_type}: {count} pairs ({percentage:.1f}%)")
        
        # 커뮤니티 내/간 연결 분포
        print(f"\nCommunity connection distribution:")
        same_community_count = pairs_df['same_community'].sum()
        inter_community_count = len(pairs_df) - same_community_count
        print(f"- Same community: {same_community_count} pairs ({(same_community_count / len(pairs_df)) * 100:.1f}%)")
        print(f"- Inter-community: {inter_community_count} pairs ({(inter_community_count / len(pairs_df)) * 100:.1f}%)")
        
        # 가장 많이 연결된 노드들
        print(f"\nMost connected important nodes:")
        node_connections = defaultdict(int)
        for _, row in pairs_df.iterrows():
            node_connections[row['source_id']] += 1
            node_connections[row['target_id']] += 1
        
        # 상위 10개 노드
        top_connected = sorted(node_connections.items(), key=lambda x: x[1], reverse=True)[:10]
        for i, (node_id, conn_count) in enumerate(top_connected, 1):
            node_info = node_info_dict[node_id]
            print(f"{i:2d}. {node_info['label']} (Community: {node_info['community']}) - {conn_count} connections")
        
        # 관계 유형별 상위 쌍들 출력
        print(f"\nTop connections by relation type:")
        for relation_type in ['broader', 'narrower', 'related', 'cosine_related']:
            type_pairs = pairs_df[pairs_df['relation_type'] == relation_type]
            if len(type_pairs) > 0:
                print(f"\n{relation_type.upper()} ({len(type_pairs)} pairs):")
                for i, (_, row) in enumerate(type_pairs.head(3).iterrows(), 1):
                    community_marker = "🏠" if row['same_community'] else "🌉"
                    print(f"  {i}. {row['source_label']} ↔ {row['target_label']} {community_marker}")
        
        # 파일로 저장 (옵션)
        if output_file_path:
            pairs_df.to_csv(output_file_path, index=False, encoding='utf-8')
            print(f"\nConnected pairs saved to: {output_file_path}")
        
        return pairs_df
    
    else:
        print("No direct connections found between important nodes.")
        return pd.DataFrame()

def analyze_connection_patterns(pairs_df, result_df):
    """
    연결 패턴을 심화 분석합니다.
    
    Args:
        pairs_df (pd.DataFrame): 연결된 쌍 정보
        result_df (pd.DataFrame): 중요 노드 정보
    """
    if len(pairs_df) == 0:
        print("No connections to analyze.")
        return
    
    print(f"\n=== Connection Pattern Analysis ===")
    
    # 커뮤니티별 내부 연결 밀도
    community_internal_connections = pairs_df[pairs_df['same_community'] == True].groupby('source_community').size()
    community_sizes = result_df.groupby('community').size()
    
    print(f"\nCommunities with highest internal connectivity:")
    community_density = {}
    for community in community_internal_connections.index:
        size = community_sizes.get(community, 0)
        connections = community_internal_connections[community]
        max_possible = size * (size - 1) / 2  # 완전 그래프의 최대 연결 수
        density = connections / max_possible if max_possible > 0 else 0
        community_density[community] = {
            'size': size,
            'connections': connections,
            'density': density
        }
    
    # 밀도 기준 상위 10개 커뮤니티
    top_dense_communities = sorted(community_density.items(), key=lambda x: x[1]['density'], reverse=True)[:10]
    for i, (community, stats) in enumerate(top_dense_communities, 1):
        if stats['density'] > 0:
            print(f"{i:2d}. Community {community}: {stats['connections']}/{int(stats['size']*(stats['size']-1)/2)} connections (density: {stats['density']:.3f})")
    
    # 브릿지 역할을 하는 노드들 (여러 커뮤니티와 연결)
    bridge_nodes = defaultdict(set)
    for _, row in pairs_df[pairs_df['same_community'] == False].iterrows():
        bridge_nodes[row['source_id']].add(row['target_community'])
        bridge_nodes[row['target_id']].add(row['source_community'])
    
    print(f"\nTop bridge nodes (connecting multiple communities):")
    bridge_scores = {node: len(communities) for node, communities in bridge_nodes.items()}
    top_bridges = sorted(bridge_scores.items(), key=lambda x: x[1], reverse=True)[:10]
    
    node_info_dict = {row['doc_id']: row for _, row in result_df.iterrows()}
    for i, (node_id, bridge_score) in enumerate(top_bridges, 1):
        if bridge_score > 1:  # 2개 이상 커뮤니티와 연결
            node_info = node_info_dict[node_id]
            print(f"{i:2d}. {node_info['label']} (Community: {node_info['community']}) - connects to {bridge_score} other communities")

def create_balanced_node_pairs_sample(result_df, connected_pairs_df, total_sample_size=100000):
    """
    중요 노드들 중에서 연결된 쌍과 연결되지 않은 쌍을 균형있게 샘플링하여 지정된 크기의 데이터셋을 생성합니다.
    
    Args:
        result_df (pd.DataFrame): 중요 노드 정보
        connected_pairs_df (pd.DataFrame): 연결된 중요 노드 쌍들
        total_sample_size (int): 생성할 총 샘플 크기
    
    Returns:
        pd.DataFrame: 균형잡힌 노드 쌍 샘플
    """
    print(f"\n=== Creating Balanced Node Pairs Sample ({total_sample_size:,} pairs) ===")
    
    # 중요 노드 정보를 딕셔너리로 변환
    node_info_dict = {}
    for _, row in result_df.iterrows():
        node_info_dict[row['doc_id']] = {
            'label': row['label'],
            'community': row['community'],
            'degree': row['degree'],
            'rank_in_community': row['rank_in_community']
        }
    
    important_nodes = list(result_df['doc_id'])
    print(f"Total important nodes: {len(important_nodes):,}")
    
    # 연결된 쌍들의 집합 생성 (빠른 검색을 위해)
    connected_pairs_set = set()
    for _, row in connected_pairs_df.iterrows():
        pair_key = tuple(sorted([row['source_id'], row['target_id']]))
        connected_pairs_set.add(pair_key)
    
    print(f"Connected pairs: {len(connected_pairs_set):,}")
    
    # 연결된 쌍들을 샘플에 포함
    connected_sample = []
    for _, row in connected_pairs_df.iterrows():
        source_info = node_info_dict[row['source_id']]
        target_info = node_info_dict[row['target_id']]
        
        connected_sample.append({
            'source_id': row['source_id'],
            'source_label': source_info['label'],
            'source_community': source_info['community'],
            'source_degree': source_info['degree'],
            'source_rank': source_info['rank_in_community'],
            'target_id': row['target_id'],
            'target_label': target_info['label'],
            'target_community': target_info['community'],
            'target_degree': target_info['degree'],
            'target_rank': target_info['rank_in_community'],
            'is_connected': True,
            'existing_relation_type': row['relation_type'],
            'same_community': row['same_community']
        })
    
    print(f"Added {len(connected_sample):,} connected pairs")
    
    # 연결되지 않은 쌍들을 랜덤 샘플링
    remaining_sample_size = total_sample_size - len(connected_sample)
    print(f"Need to sample {remaining_sample_size:,} unconnected pairs")
    
    if remaining_sample_size <= 0:
        print("Connected pairs already exceed target sample size. Using only connected pairs.")
        sample_df = pd.DataFrame(connected_sample[:total_sample_size])
    else:
        # 전체 가능한 쌍의 수 계산
        total_possible_pairs = len(important_nodes) * (len(important_nodes) - 1) // 2
        total_unconnected_pairs = total_possible_pairs - len(connected_pairs_set)
        
        print(f"Total possible pairs: {total_possible_pairs:,}")
        print(f"Total unconnected pairs: {total_unconnected_pairs:,}")
        
        # 랜덤 시드 설정
        random.seed(42)
        
        # 연결되지 않은 쌍들을 효율적으로 샘플링
        unconnected_sample = []
        attempts = 0
        max_attempts = remaining_sample_size * 10  # 무한 루프 방지
        
        print("Sampling unconnected pairs...")
        sample_progress_interval = max(1, remaining_sample_size // 20)  # 20회 진행률 표시
        
        while len(unconnected_sample) < remaining_sample_size and attempts < max_attempts:
            # 랜덤하게 두 노드 선택
            source_idx = random.randint(0, len(important_nodes) - 1)
            target_idx = random.randint(0, len(important_nodes) - 1)
            
            if source_idx != target_idx:  # 자기 자신과의 쌍 제외
                source_id = important_nodes[source_idx]
                target_id = important_nodes[target_idx]
                
                # 정렬된 순서로 쌍 생성
                pair_key = tuple(sorted([source_id, target_id]))
                
                # 연결되지 않은 쌍인지 확인
                if pair_key not in connected_pairs_set:
                    source_info = node_info_dict[source_id]
                    target_info = node_info_dict[target_id]
                    
                    # 같은 커뮤니티인지 확인
                    same_community = source_info['community'] == target_info['community']
                    
                    unconnected_sample.append({
                        'source_id': source_id,
                        'source_label': source_info['label'],
                        'source_community': source_info['community'],
                        'source_degree': source_info['degree'],
                        'source_rank': source_info['rank_in_community'],
                        'target_id': target_id,
                        'target_label': target_info['label'],
                        'target_community': target_info['community'],
                        'target_degree': target_info['degree'],
                        'target_rank': target_info['rank_in_community'],
                        'is_connected': False,
                        'existing_relation_type': None,
                        'same_community': same_community
                    })
                    
                    # 중복 방지를 위해 집합에 추가
                    connected_pairs_set.add(pair_key)
                    
                    # 진행률 표시
                    if len(unconnected_sample) % sample_progress_interval == 0:
                        progress = (len(unconnected_sample) / remaining_sample_size) * 100
                        print(f"  Sampled {len(unconnected_sample):,}/{remaining_sample_size:,} unconnected pairs ({progress:.1f}%)")
            
            attempts += 1
        
        print(f"Successfully sampled {len(unconnected_sample):,} unconnected pairs")
        
        # 연결된 쌍과 연결되지 않은 쌍을 결합
        all_samples = connected_sample + unconnected_sample
        sample_df = pd.DataFrame(all_samples)
    
    # 결과 분석
    print(f"\n=== Sample Dataset Analysis ===")
    print(f"Total sample size: {len(sample_df):,}")
    
    connected_count = sample_df['is_connected'].sum()
    unconnected_count = len(sample_df) - connected_count
    
    print(f"Connected pairs: {connected_count:,} ({(connected_count/len(sample_df)*100):.1f}%)")
    print(f"Unconnected pairs: {unconnected_count:,} ({(unconnected_count/len(sample_df)*100):.1f}%)")
    
    # 커뮤니티 내/간 분포
    same_community_count = sample_df['same_community'].sum()
    inter_community_count = len(sample_df) - same_community_count
    
    print(f"\nCommunity distribution:")
    print(f"Same community pairs: {same_community_count:,} ({(same_community_count/len(sample_df)*100):.1f}%)")
    print(f"Inter-community pairs: {inter_community_count:,} ({(inter_community_count/len(sample_df)*100):.1f}%)")
    
    # 연결된 쌍 중 관계 유형 분포
    if connected_count > 0:
        print(f"\nRelation types in connected pairs:")
        relation_counts = sample_df[sample_df['is_connected'] == True]['existing_relation_type'].value_counts()
        for relation_type, count in relation_counts.head(5).items():
            percentage = (count / connected_count) * 100
            print(f"- {relation_type}: {count:,} pairs ({percentage:.1f}%)")
    
    # 샘플 예시 출력
    print(f"\nSample examples:")
    print("Connected pairs:")
    connected_examples = sample_df[sample_df['is_connected'] == True].head(3)
    for i, (_, row) in enumerate(connected_examples.iterrows(), 1):
        community_marker = "🏠" if row['same_community'] else "🌉"
        print(f"  {i}. {row['source_label']} ↔ {row['target_label']} ({row['existing_relation_type']}) {community_marker}")
    
    print("Unconnected pairs:")
    unconnected_examples = sample_df[sample_df['is_connected'] == False].head(3)
    for i, (_, row) in enumerate(unconnected_examples.iterrows(), 1):
        community_marker = "🏠" if row['same_community'] else "🌉"
        print(f"  {i}. {row['source_label']} ↔ {row['target_label']} (no connection) {community_marker}")
    
    return sample_df

def main():
    """
    메인 실행 함수
    """
    # 파일 경로 설정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(current_dir)
    csv_file_path = os.path.join(current_dir,'..', "louvain_analysis_final", "network_nodes.csv")
    db_file_path = os.path.join(current_dir, "..", "..", "data", "subject_headings.db")
    output_file_path = os.path.join(current_dir, 'results', "important_nodes_by_community.csv")
    
    # 파일 존재 확인
    if not os.path.exists(csv_file_path):
        print(f"Error: CSV file not found at {csv_file_path}")
        return
    
    if not os.path.exists(db_file_path):
        print(f"Error: Database file not found at {db_file_path}")
        return
    
    # 중요 노드 추출
    result_df = get_important_nodes_by_community(csv_file_path, db_file_path, output_file_path)
    
    # 통계 분석
    community_stats = analyze_community_statistics(result_df)
    
    # 노드 개수 분포 분석
    node_distribution = analyze_node_count_distribution(result_df)
    
    # 랜덤 노드에서 중요 노드까지의 거리 분석
    distance_analysis = analyze_distance_to_important_nodes(db_file_path, result_df, sample_size=500, max_distance=5)
    
    # 중요 노드들 간의 연결 분석
    connected_pairs_output = os.path.join(current_dir, "connected_important_pairs.csv")
    connected_pairs = find_connected_important_node_pairs(db_file_path, result_df, connected_pairs_output)
    
    # 연결 패턴 심화 분석
    if len(connected_pairs) > 0:
        analyze_connection_patterns(connected_pairs, result_df)
    
    # 균형잡힌 노드 쌍 샘플 생성 (10만개)
    balanced_sample_output = os.path.join(current_dir, "balanced_node_pairs_sample.csv")
    balanced_sample = create_balanced_node_pairs_sample(result_df, connected_pairs, total_sample_size=100000)
    balanced_sample.to_csv(balanced_sample_output, index=False, encoding='utf-8')
    print(f"\nBalanced sample saved to: {balanced_sample_output}")
    
    # 샘플 결과 출력
    print("\n=== Sample Results ===")
    print("Top 5 communities by size with their important nodes:")
    for community_id in community_stats.nlargest(5, 'total_nodes').index:
        community_nodes = result_df[result_df['community'] == community_id]
        print(f"\nCommunity {community_id} (total nodes: {community_nodes.iloc[0]['total_community_nodes']}):")
        for _, node in community_nodes.head(3).iterrows():  # 상위 3개만 출력
            print(f"  - Rank {node['rank_in_community']}: {node['label']} (degree: {node['degree']})")

if __name__ == "__main__":
    main()
