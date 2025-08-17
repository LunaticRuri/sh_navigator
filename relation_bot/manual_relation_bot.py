import sqlite3
import json
from typing import List
from gemini_fetcher import RelationCandidate, PredictedRelation, GeminiFetcher
from config import RELATION_BOT_DATABASE, MAIN_DATABASE
from tqdm import tqdm

def _check_history(source_id: str, target_id: str) -> bool:
    """
    Check if a relation has already been generated for the given source and target IDs.
    Returns True if the relation exists in the history table, otherwise False.
    """
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM history WHERE source_id = ? AND target_id = ?",
            (source_id, target_id)
        )
        return cursor.fetchone() is not None

def main():
    """
    Generate relation predictions using the GeminiFetcher.
    Fetches jobs from the pool table, filters out those already in history,
    generates predictions in batches, and saves them to the checkpoint table.
    """
    print("Fetching jobs from the relation bot pool...")
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT source_id, source_label, source_definition, target_id, target_label, target_definition FROM pool"
        )
        jobs = cursor.fetchall()
        filtered_jobs = []
        # Filter out jobs that are already in history
        for source_id, source_label, source_definition, target_id, target_label, target_definition in tqdm(jobs, desc="Filtering jobs"):
            if _check_history(source_id, target_id):
                continue
            filtered_jobs.append((source_id, source_label, source_definition, target_id, target_label, target_definition))
    
    # Convert filtered jobs to RelationCandidate objects
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
    
    if not candidates:
        print("No candidates found in the pool.")
        raise SystemExit

    print(f"Total candidates to process: {len(candidates)}")
    
    conn = sqlite3.connect(RELATION_BOT_DATABASE)
    cursor = conn.cursor()

    print("Initializing GeminiFetcher...")
    fetcher = GeminiFetcher()
    # Process candidates in batches of 1000
    print("Generating predictions in batches...")
    for i in range(0, len(candidates), 1000):
        batch_candidates = candidates[i:i + 1000]
        if not batch_candidates:
            continue

        predictions = fetcher.generate_relations(batch_candidates, progress=i)
        
        if not predictions:
            print("No predictions generated.")
            continue
        
        # Save predictions to checkpoint table
        for prediction in predictions:
            cursor.execute("""
                INSERT OR IGNORE INTO checkpoint (is_related, source_id, source_label, target_id, target_label, predicate, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (
                1 if prediction.is_related else 0,
                prediction.source_id,
                prediction.source_label,
                prediction.target_id,
                prediction.target_label,
                prediction.predicate,
                prediction.description
            ))
            conn.commit()
        
        print("*" + "=" * 20 + f" Batch {i // 1000 + 1} processed. {len(batch_candidates)} candidates processed." + "=" * 20 + "*")
        print(f"Progress: {i + len(batch_candidates)} / {len(candidates)} candidates processed.")

    conn.close()
    print("Relation predictions saved to the database.")

def update_main_db():
    """
    Update the main database with the predictions from the checkpoint table.
    For each prediction:
      - If not related, record in history.
      - If related, update or insert into relations table and record in history.
      - Merge metadata if relation already exists.
    """
    conn = sqlite3.connect(MAIN_DATABASE)
    cursor = conn.cursor()

    # Fetch predictions from checkpoint table
    with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
        relation_cursor = relation_conn.cursor()
        relation_cursor.execute(
            "SELECT is_related, source_id, source_label, target_id, target_label, predicate, description FROM checkpoint"
        )
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
        # Skip if source or target ID is corrupted
        cursor.execute(
            "SELECT * FROM subjects WHERE node_id = ? OR node_id = ?",
            (prediction.source_id, prediction.target_id)
        )
        if len(cursor.fetchall()) != 2:
            print(f"Skipping corrupted prediction: {prediction.source_id} -> {prediction.target_id}")
            continue

        # If prediction is not related, record in history and skip
        if not prediction.is_related:
            with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
                relation_cursor = relation_conn.cursor()
                relation_cursor.execute(
                    "INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",
                    (prediction.source_id, prediction.target_id)
                )
                relation_conn.commit()
            continue
        
        # Prepare metadata for related predictions
        metadata = {
            "predicate": prediction.predicate,
            "description": prediction.description
        }

        # Check if a related or cosine_related relation already exists
        cursor.execute(
            "SELECT 1 FROM relations WHERE source_id = ? AND target_id = ? AND (relation_type ='related' or relation_type ='cosine_related')",
            (prediction.source_id, prediction.target_id)
        )
        if not cursor.fetchone():
            # Insert new generated relation if none exists
            cursor.execute(
                "INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, metadata) VALUES (?, ?, ?, ?)", 
                (prediction.source_id, prediction.target_id, 'generated', json.dumps(metadata, ensure_ascii=False))
            )
            conn.commit()   
            # Record in history
            with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
                relation_cursor = relation_conn.cursor()
                relation_cursor.execute(
                    "INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",
                    (prediction.source_id, prediction.target_id)
                )
                relation_conn.commit()
            continue
        
        # Update metadata for existing related relation
        cursor.execute(
            "SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'related'",
            (prediction.source_id, prediction.target_id)
        )
        result = cursor.fetchone()
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute(
                "UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id)
            )
            conn.commit()

        # Update metadata for existing cosine_related relation
        cursor.execute(
            "SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'",
            (prediction.source_id, prediction.target_id)
        )
        result = cursor.fetchone()
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute(
                "UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'", 
                (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id)
            )
            conn.commit()
        
        # Update metadata for existing generated relation (upgrade to related)
        cursor.execute(
            "SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'generated'",
            (prediction.source_id, prediction.target_id)
        )
        result = cursor.fetchone()
        if result:
            result_metadata = json.loads(result[0])
            result_metadata.update(metadata)
            cursor.execute(
                "UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id)
            )
            conn.commit()
        
        # Record in history
        with sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
            relation_cursor = relation_conn.cursor()
            relation_cursor.execute(
                "INSERT OR IGNORE INTO history (source_id, target_id, created_at) VALUES (?, ?, datetime('now'))",
                (prediction.source_id, prediction.target_id)
            )
            relation_conn.commit()
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    print("Starting relation generation...")
    main()
    print("Relation generation completed. Updating main database...")
    update_main_db()
    print("Relation generation completed and main database updated.")