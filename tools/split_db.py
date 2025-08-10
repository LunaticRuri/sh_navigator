import sqlite3
from tqdm import tqdm

def split_table_to_dbs(db_path, table_name, rows_per_db, output_dir):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()

    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in cursor.fetchall()]
    col_defs = ', '.join([f'"{col}"' for col in columns])
    placeholders = ', '.join(['?' for _ in columns])

    total_rows = len(rows)
    num_slices = (total_rows + rows_per_db - 1) // rows_per_db

    for i in tqdm(range(num_slices)):
        slice_rows = rows[i*rows_per_db:(i+1)*rows_per_db]
        out_db = f"{output_dir}/{table_name}_part_{i+1}.db"
        out_conn = sqlite3.connect(out_db)
        out_cursor = out_conn.cursor()

        # Get CREATE TABLE statement
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        create_stmt = cursor.fetchone()[0]
        out_cursor.execute(create_stmt)

        out_cursor.executemany(
            f"INSERT INTO {table_name} ({col_defs}) VALUES ({placeholders})",
            slice_rows
        )
        out_conn.commit()
        out_conn.close()

    conn.close()

if __name__ == "__main__":
    db_path = "./data/books_TODO.db"
    split_table_to_dbs(
        db_path=db_path,
        table_name="books",
        rows_per_db=155000,
        output_dir="./data"
    )