import sqlite3
import json
from typing import List
from gemini_fetcher import RelationCandidate, PredictedRelation, GeminiFetcher
from config import RELATION_BOT_DATABASE, DATABASE_PATH
from tqdm import tqdm



def _check_already_generated(source_id: str, target_id: str) -> bool:
    """Check if a relation has already been generated for the given source and target IDs."""
    
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM history WHERE source_id = ? AND target_id = ?", (source_id, target_id))
        return cursor.fetchone() is not None

def main():
    """Generate relation predictions using the GeminiFetcher."""
    
    print("Fetching jobs from the relation bot pool...")
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT source_id, source_label, source_definition, target_id, target_label, target_definition FROM pool")
        jobs = cursor.fetchall()
        filtered_jobs = []
        for source_id, source_label, source_definition, target_id, target_label, target_definition in jobs:
            if _check_already_generated(source_id, target_id):
                continue
            filtered_jobs.append((source_id, source_label, source_definition, target_id, target_label, target_definition))
    
    candidates = [
        RelationCandidate(
            source_id=row[0],
            source_label=row[1],
            source_definition=row[2],
            target_id=row[3],
            target_label=row[4],
            target_definition=row[5]
        ) for row in filtered_jobs
    ]

    # Filter out candidates that have already been generated
    candidates = [c for c in candidates if not _check_already_generated(c.source_id, c.target_id)]
    if not candidates:
        print("No candidates found in the pool.")
        raise SystemExit

    print(f"Total candidates to process: {len(candidates)}")
    
    conn = sqlite3.connect(RELATION_BOT_DATABASE)
    cursor = conn.cursor()


    print("Initializing GeminiFetcher...")
    fetcher = GeminiFetcher()
    # 1000개 마다 진행 상황을 저장.
    print("Generating predictions in batches...")
    for i in range(0, len(candidates), 1000):
        batch_candidates = candidates[i:i + 1000]
        if not batch_candidates:
            continue

        predictions = fetcher.generate_relations(batch_candidates, progress=i)
        
        if not predictions:
            print("No predictions generated.")
            continue
        
        for prediction in predictions:
            cursor.execute("""
                INSERT OR IGNORE INTO checkpoint (is_related, source_id, source_label, target_id, target_label, predicate, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (1 if prediction.is_related else 0, prediction.source_id, prediction.source_label, prediction.target_id, prediction.target_label, prediction.predicate, prediction.description))
            conn.commit()
        
        print("*" + "=" * 20 + f" Batch {i // 1000 + 1} processed. {len(batch_candidates)} candidates processed." + "=" * 20 + "*")
        print(f"Progress: {i + len(batch_candidates)} / {len(candidates)} candidates processed.")

    conn.close()
    print("Relation predictions saved to the database.")


def update_main_db():
    """Update the main database with the predictions."""
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
        relation_cursor = relation_conn.cursor()
        relation_cursor.execute("SELECT is_related, source_id, source_label, target_id, target_label, predicate, description FROM checkpoint")
        predictions = [
            PredictedRelation(
                is_related=row[0],
                source_id=row[1],
                source_label=row[2],
                target_id=row[3],
                target_label=row[4],
                predicate=row[5],
                description=row[6]
            ) 
            for row in relation_cursor.fetchall()
            ]

    for prediction in tqdm(predictions, desc="Updating main database"):
        # 예측된 관계 없는 경우
        if not prediction.is_related:
            with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
                relation_cursor = relation_conn.cursor()
                relation_cursor.execute("INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",(prediction.source_id, prediction.target_id))
                relation_conn.commit()
            continue
        
        metadata = {
            "predicate": prediction.predicate,
            "description": prediction.description
        }

        cursor.execute("SELECT 1 FROM relations WHERE source_id = ? AND target_id = ? AND (relation_type ='related' or relation_type ='cosine_related')", (prediction.source_id, prediction.target_id))
        # 기존 related-type 관계가 없는 경우
        if not cursor.fetchone():
            # 새로운 관계를 생성 - generated 관계로 저장
            cursor.execute("INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, metadata) VALUES (?, ?, ?, ?)", 
                           (prediction.source_id, prediction.target_id, 'generated', json.dumps(metadata, ensure_ascii=False)))
            conn.commit()   
            
            # history 테이블에 기록
            with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
                relation_cursor = relation_conn.cursor()
                relation_cursor.execute("INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",(prediction.source_id, prediction.target_id))
                relation_conn.commit()
            # Skip to the next prediction if no existing related-type relation
            continue
        
        
        cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", (prediction.source_id, prediction.target_id))
        result = cursor.fetchone()
        # nlk의 related 관계가 있는 경우
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                            (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
            conn.commit()

        cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'", (prediction.source_id, prediction.target_id))
        result = cursor.fetchone()
        # cosine_related 관계가 있는 경우
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'", 
                            (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
            conn.commit()
        
        cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'generated'", (prediction.source_id, prediction.target_id))
        result = cursor.fetchone()
        # generated 관계가 있는 경우
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                            (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
            conn.commit()
        
        # history 테이블에 기록
        with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
            relation_cursor = relation_conn.cursor()
            relation_cursor.execute("INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",(prediction.source_id, prediction.target_id))
            relation_conn.commit()
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Starting relation generation...")
    main()
    print("Relation generation completed. Updating main database...")
    update_main_db()
    print("Relation generation completed and main database updated.")