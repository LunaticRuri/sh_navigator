from config import RELATION_BOT_DATABASE, DATABASE_PATH, NETWORK_SERVER_URL
import sqlite3
from tqdm import tqdm
from itertools import combinations
import httpx

def create_relation_bot_database():
    """Create the relation_bot database if it does not exist."""
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        
        cursor = conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS pool')
        cursor.execute('DROP TABLE IF EXISTS history')
        cursor.execute('DROP TABLE IF EXISTS checkpoint')
        
        # Create the pool table if it does not exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                source_label TEXT NOT NULL,
                source_definition TEXT,
                target_id TEXT NOT NULL,
                target_label TEXT NOT NULL,
                target_definition TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, target_id) ON CONFLICT IGNORE
            )
        ''')

        # Create the history table if it does not exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, target_id) ON CONFLICT IGNORE
                )
        ''')

        # Create the checkpoint table if it does not exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkpoint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                is_related INTEGER NOT NULL,
                source_id TEXT NOT NULL,
                source_label TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_label TEXT NOT NULL,
                predicate TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (source_id, target_id) ON CONFLICT IGNORE
            )
        ''')
        conn.commit()

def reset_relation_bot_database():
    """Reset the relation_bot database by dropping and recreating the tables."""
    with sqlite3.connect(RELATION_BOT_DATABASE) as conn:
        cursor = conn.cursor()
        cursor.execute('DROP TABLE IF EXISTS pool')
        conn.commit()
    create_relation_bot_database()

def set_top_n_related_candidates(n: int = 100):
    with sqlite3.connect(DATABASE_PATH) as main_conn, sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
        main_cursor = main_conn.cursor()
        relation_cursor = relation_conn.cursor()

        main_cursor.execute(
            "SELECT node_id, label, definition FROM subjects ORDER BY priority_score DESC LIMIT ?",
            (n,)
        )
        top_candidates = main_cursor.fetchall()
        top_nodeids = [row[0] for row in top_candidates]

        placeholders = ','.join('?' for _ in top_nodeids)
        main_cursor.execute(
            f"SELECT source_id, target_id, relation_type FROM relations WHERE source_id IN ({placeholders})",
            top_nodeids
        )
        related_candidates = [
            candidate for candidate in main_cursor.fetchall()
            if candidate[2] not in ('broader', 'narrower')
        ]

        relation_cursor.execute("DELETE FROM pool")
        relation_conn.commit()

        for source_id, target_id, relation_type in tqdm(related_candidates):
            main_cursor.execute(
                "SELECT label, definition FROM subjects WHERE node_id = ?", (source_id,)
            )
            source = main_cursor.fetchone()
            if not source:
                continue
            source_label, source_definition = source[0], source[1] or ''

            main_cursor.execute(
                "SELECT label, definition FROM subjects WHERE node_id = ?", (target_id,)
            )
            target = main_cursor.fetchone()
            if not target:
                continue
            target_label, target_definition = target[0], target[1] or ''

            if source_label and target_label:
                relation_cursor.execute('''
                    INSERT INTO pool (
                        source_id, source_label, source_definition,
                        target_id, target_label, target_definition
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    source_id, source_label, source_definition,
                    target_id, target_label, target_definition
                ))
        relation_conn.commit()

def set_top_n_candidates(n: int = 500):

    httpx_client = httpx.Client(timeout=10.0)

    with sqlite3.connect(DATABASE_PATH) as main_conn, sqlite3.connect(RELATION_BOT_DATABASE) as relation_conn:
        main_cursor = main_conn.cursor()
        relation_cursor = relation_conn.cursor()

        main_cursor.execute(
            "SELECT node_id, label, definition FROM subjects ORDER BY priority_score DESC LIMIT ?",
            (n,)
        )
        top_candidates = main_cursor.fetchall()
        candidate_pairs = list(combinations(top_candidates, 2))

        relation_cursor.execute("DELETE FROM pool")
        relation_conn.commit()

        for (source_id, source_label, source_definition), (target_id, target_label, target_definition) in tqdm(candidate_pairs):

            main_cursor.execute(
                "SELECT source_id, target_id, relation_type FROM relations "
                "WHERE source_id = ? AND target_id = ? AND (relation_type = 'broader' OR relation_type = 'narrower')",
                (source_id, target_id)
            )
            if main_cursor.fetchone():
                continue

            if source_label and target_label:
                relation_cursor.execute('''
                    INSERT INTO pool (
                        source_id, source_label, source_definition,
                        target_id, target_label, target_definition
                    ) VALUES (?, ?, ?, ?, ?, ?)
                ''', (source_id, source_label, source_definition, target_id, target_label, target_definition)
                )
            
            # Fetch the shortest path from the network server
            response = httpx_client.get(
                f"{NETWORK_SERVER_URL}/path/shortest",
                params={"source_id": source_id, "target_id": target_id}
            )
            response.raise_for_status()
            response_data = response.json()
            if response_data.get("path"):
                path = response_data["path"]
                
                for i in range(len(path) - 1):
                    main_cursor.execute(
                        "SELECT source_id, target_id, relation_type FROM relations "
                        "WHERE source_id = ? AND target_id = ? AND (relation_type = 'broader' OR relation_type = 'narrower')",
                        (path[i], path[i + 1])
)
                    if main_cursor.fetchone():
                        continue
                    
                    main_cursor.execute(
                        "SELECT label, definition FROM subjects WHERE node_id = ?", (path[i],)
                    )
                    source = main_cursor.fetchone()
                    if not source:
                        continue
                    source_id, source_label, source_definition = path[i], source[0], source[1] or ''

                    main_cursor.execute(
                        "SELECT label, definition FROM subjects WHERE node_id = ?", (path[i + 1],)
                    )
                    target = main_cursor.fetchone()
                    if not target:
                        continue
                    target_id, target_label, target_definition = path[i+1], target[0], target[1] or ''

                    relation_cursor.execute('''
                        INSERT INTO pool (
                            source_id, source_label, source_definition,
                            target_id, target_label, target_definition
                        ) VALUES (?, ?, ?, ?, ?, ?)
                    ''', (
                        source_id, source_label, source_definition,
                        target_id, target_label, target_definition
                    ))
            relation_conn.commit()
        


if __name__ == "__main__":
    create_relation_bot_database()
    set_top_n_related_candidates(100)