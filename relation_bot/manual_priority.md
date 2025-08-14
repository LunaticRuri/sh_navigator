# 우선 순위 리스트

> 멀티 워커 지원은 시간 부족 관계로 pass

## Manual_Relation_BOT

0. 따로 db 파일 만들어서 이미 탐색한 쌍들은 기록해야 함.
1. priority_score top 100 -> related, cosine_related 의미 구체화 해서 metadata에 넣기 (predicate, description)
   1. 단, broader, narrower 제외.
   2. 연결 없다고 LLM에서 판단하면 그냥 넘어가기
2. priority_score top 500
   1. 서로에 대해 우선 탐색 (물론 이미 탐색되었으면 스킵)
   2. 관계 없다면 최단 경로 보고 그 루트대로 탐색
3. 이미 여기까지도 시간이 오래 걸리겠지만, 이 이후에도 시간이 남으면 top 1000으로 대상 범위 늘리기

## Auto_Relation_BOT

> 나중에 indexer의 set_candidates_from_text랑 연결해서 텍스트 피딩으로 자동 동작 하게 하기
> 텍스트 피딩은 이용자의 검색 쿼리나 뉴스 기사 등의 스트림을 상정 가능.
