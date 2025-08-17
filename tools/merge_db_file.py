import sqlite3
import os

def merge_sqlite_dbs(target_db_path, source_db_paths):
    if not os.path.exists(target_db_path):
        # Copy the first source as the base if target doesn't exist
        os.system(f'cp "{source_db_paths[0]}" "{target_db_path}"')
        source_db_paths = source_db_paths[1:]

    target_conn = sqlite3.connect(target_db_path)
    target_cur = target_conn.cursor()

    for src_db in source_db_paths:
        print(f"Merging {src_db} into {target_db_path}")
        src_conn = sqlite3.connect(src_db)
        src_cur = src_conn.cursor()

        # Get all table names
        src_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in src_cur.fetchall()]

        for table in tables:
            # Get column names
            src_cur.execute(f"PRAGMA table_info({table});")
            columns = [row[1] for row in src_cur.fetchall()]
            col_str = ','.join(columns)

            # Fetch all data
            src_cur.execute(f"SELECT {col_str} FROM {table};")
            rows = src_cur.fetchall()
            if not rows:
                continue

            # Insert into target
            placeholders = ','.join(['?'] * len(columns))
            target_cur.executemany(
                f"INSERT INTO {table} ({col_str}) VALUES ({placeholders});",
                rows
            )
            target_conn.commit()

        src_conn.close()
    target_conn.close()
    print("Merge complete.")

if __name__ == "__main__":
    
    db_folder_path = './data/completed'

    db_files = [os.path.join(db_folder_path, f"books_part_{i}.db") for i in range(1, 15)]
    target_db = os.path.join(db_folder_path, "merged_contents.db")
    merge_sqlite_dbs(target_db, db_files)