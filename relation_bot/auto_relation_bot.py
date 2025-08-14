from config import MAIN_DATABASE, RELATION_BOT_DATABASE
import signal
import sqlite3
import os
import time
import logging
from tqdm import tqdm
import json
from functools import partial
from queue import Queue
from typing import Callable, Any, List
from gemini_fetcher import RelationCandidate, PredictedRelation, GeminiFetcher

# Configure logging for the application
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _default_exit_function(processed_count = 0, goal = 1000) -> bool:
    """Default exit condition function.
    Returns True if processed_count reaches the goal.
    """
    if not isinstance(goal, int) or goal <= 0:
        raise ValueError("Goal must be a positive integer.")
    return processed_count >= goal

class AutoRelationBot:
    """Automates relation prediction and database updates."""
    def __init__(self, batch_size=100, exit_condition_function:Callable[[Any], bool]  = _default_exit_function, custom_goal = None):
        self.batch_size = batch_size
        self.todo_queue = Queue()
        self.gemini_fetcher = GeminiFetcher()
        self.processed_count = 0
        # Setup exit condition function with custom goal if provided
        if exit_condition_function and custom_goal:
            self.exit_condition_function = partial(exit_condition_function, **custom_goal)
        else:
            self.exit_condition_function = partial(_default_exit_function, proceesed_count = self.processed_count, goal = custom_goal or 1000)
    
    def _check_history(self, source_id: str, target_id: str) -> bool:
        """Check if a relation has already been generated for the given source and target IDs."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM history WHERE source_id = ? AND target_id = ?", (source_id, target_id))
            return cursor.fetchone() is not None
        
    def _add_relation_to_history(self, source_id: str, target_id: str, relation_type: str):
        """Add a relation to the history table to avoid duplicate processing."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO history (source_id, target_id, relation_type) VALUES (?, ?, ?)",
                (source_id, target_id, relation_type)
            )
            conn.commit()
            logging.info(f"Added relation from {source_id} to {target_id} of type {relation_type} to history.")
    
    def _remove_from_pool(self, source_id: str, target_id: str):
        """Remove a processed relation candidate from the pool."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM pool WHERE source_id = ? AND target_id = ?",
                (source_id, target_id)
            )
            conn.commit()
            logging.info(f"Removed relation from pool: {source_id} -> {target_id}")

    def _add_to_checkpoint(self, prediction: PredictedRelation):
        """Add a relation candidate to the checkpoint table for later review or update."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO checkpoint (is_related, source_id, source_label, target_id, target_label, predicate, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (1 if prediction.is_related else 0, prediction.source_id, prediction.source_label, prediction.target_id, prediction.target_label, prediction.predicate, prediction.description))
            conn.commit()
            logging.info(f"Added prediction to checkpoint: {prediction.source_label} -> {prediction.target_label} | Related: {prediction.is_related} | Predicate: {prediction.predicate} | Description: {prediction.description}")
    
    def _reset_pool(self):
        """Reset the pool table by deleting all entries."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pool")
            conn.commit()
            logging.info("Pool table reset.")

    def _reset_checkpoint(self):
        """Reset the checkpoint table by deleting all entries."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM checkpoint")
            conn.commit()
            logging.info("Checkpoint table reset.")

    def get_total_processed_count(self) -> int:
        """Get the total number of processed candidates."""
        return self.processed_count
    
    def get_data_from_pool(self, size: int = 100):
        """Fetch relation candidates from the pool and add them to the processing queue."""
        with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT source_id, source_label, source_definition, target_id, target_label, target_definition FROM pool LIMIT {size}")
            rows = cursor.fetchall()
            # Filter out candidates already processed (in history)
            candidates = [
                RelationCandidate(
                    source_id=row[0],
                    source_label=row[1],
                    source_definition=row[2],
                    target_id=row[3],
                    target_label=row[4],
                    target_definition=row[5]
                ) for row in rows if not self._check_history(row[0], row[3])
            ]

        # Add candidates to the processing queue
        for candidate in candidates:
            self.todo_queue.put(candidate)

        logging.info(f"Loaded {len(candidates)} candidates from the pool.")

    def process_candidates(self):
        """Process candidates from the todo queue using GeminiFetcher."""
        count = 0
        gemini_batch_size = 10
        candidates = []
        
        # Collect a batch of candidates for processing
        while not self.todo_queue.empty() and count < gemini_batch_size:
            candidates.append(self.todo_queue.get())
            count += 1
        
        # Generate relation predictions
        results : List[PredictedRelation] = self.gemini_fetcher.generate_relations(candidates)

        # Update history, pool, and checkpoint for each result
        for result in results:
            try:
                self._add_relation_to_history(result.source_id, result.target_id, result.predicate)
                self._remove_from_pool(result.source_id, result.target_id)
                self._add_to_checkpoint(result)
                self.processed_count += 1
            except Exception as e:
                logging.error(f"Error processing result {result.source_label} -> {result.target_label}: {e}")
                continue

    def update_main_db(self):
        """Update the main database with the predictions in the checkpoint table and reset the checkpoint."""

        # Fetch predictions from checkpoint table
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

        with sqlite3.connect(MAIN_DATABASE) as conn:
            cursor = conn.cursor()
            # Update main database for each prediction
            for prediction in tqdm(predictions, desc="Updating main database"):
                # Skip if not related
                if not prediction.is_related:
                    continue
                
                metadata = {
                    "predicate": prediction.predicate,
                    "description": prediction.description
                }

                # Check for existing related/cosine_related relations
                cursor.execute("SELECT 1 FROM relations WHERE source_id = ? AND target_id = ? AND (relation_type ='related' or relation_type ='cosine_related')", (prediction.source_id, prediction.target_id))
                if not cursor.fetchone():
                    # Insert as a new generated relation if none exists
                    cursor.execute("INSERT OR IGNORE INTO relations (source_id, target_id, relation_type, metadata) VALUES (?, ?, ?, ?)", 
                                (prediction.source_id, prediction.target_id, 'generated', json.dumps(metadata, ensure_ascii=False)))
                    conn.commit()   
                    continue
                
                # Update metadata for existing related relation
                cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", (prediction.source_id, prediction.target_id))
                result = cursor.fetchone()
                if result:
                    result_metadata = json.loads(result[0])
                    result_metadata.update(metadata)
                    cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                                    (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
                    conn.commit()

                # Update metadata for existing cosine_related relation
                cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'", (prediction.source_id, prediction.target_id))
                result = cursor.fetchone()
                if result:
                    result_metadata = json.loads(result[0])
                    result_metadata.update(metadata)
                    cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'cosine_related'", 
                                    (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
                    conn.commit()
                
                # Update metadata for existing generated relation
                cursor.execute("SELECT metadata FROM relations WHERE source_id = ? AND target_id = ? AND relation_type = 'generated'", (prediction.source_id, prediction.target_id))
                result = cursor.fetchone()
                if result:
                    result_metadata = json.loads(result[0])
                    result_metadata.update(metadata)
                    cursor.execute("UPDATE relations SET metadata = ? WHERE source_id = ? AND target_id = ? AND relation_type = 'related'", 
                                    (json.dumps(result_metadata, ensure_ascii=False), prediction.source_id, prediction.target_id))
                    conn.commit()

        # Reset the checkpoint table after processing
        self._reset_checkpoint()

    def check_exit_condition(self):
        """Check if the exit condition is met and exit if so."""
        if self.exit_condition_function():
            logging.info(f"Exit condition met. Processed {self.processed_count} candidates.")
            raise SystemExit("Exit condition met.")
            

def graceful_exit(signum, frame):
    """Handle graceful exit on signal."""
    logging.info(f"Received termination signal. ({signum}) Exiting gracefully...")
    raise SystemExit        

if __name__ == "__main__":
    # Register signal handlers for graceful exit
    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)
    
    logging.info(f"AutoRelationBot PID: {os.getpid()}")
    logging.info("Starting AutoRelationBot...")

    bot = AutoRelationBot()
    while True:
        try:
            bot.get_data_from_pool()      # Load candidates from pool
            bot.process_candidates()      # Process candidates and generate relations
            bot.update_main_db()          # Update main database with predictions
            bot.check_exit_condition()    # Check if exit condition is met
            time.sleep(1)                 # Sleep to avoid busy waiting
            logging.info(f"Processed {bot.get_total_processed_count} candidates so far.")
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            continue
        except SystemExit:
            logging.info("Exiting AutoRelationBot.")
            break
        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received. Exiting AutoRelationBot.")
            break
