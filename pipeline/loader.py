# loader.py
import sqlite3
import numpy as np
import os
from datetime import datetime
import json
import faiss
import logging
import pickle


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")


def save_embeddings(pipeline_db_path: str, embeddings_db_path: str):
    """ Save processed book embeddings to the embeddings database."""
    
    logging.info("Saving embeddings to the database...")
    
    if not os.path.exists(pipeline_db_path):
        logging.error("Pipeline database does not exist.")
        raise FileNotFoundError("Pipeline database does not exist.")
    if not os.path.exists(embeddings_db_path):
        logging.error("Embeddings database does not exist.")
        raise FileNotFoundError("Embeddings database does not exist.")
    
    try:
        pipeline_conn = sqlite3.connect(pipeline_db_path)
        pipeline_cursor = pipeline_conn.cursor()
        embeddings_conn = sqlite3.connect(embeddings_db_path)
        embeddings_cursor = embeddings_conn.cursor()
    except sqlite3.Error as e:
        logging.error(f"Error connecting to SQLite database: {e}")
        return
    
    pipeline_cursor.execute("SELECT id, isbn, embedding FROM book_pipeline WHERE status = 'processed'")
    books_to_load = pipeline_cursor.fetchall()
    
    for record_id, isbn, embedding_blob in books_to_load:
        if not embedding_blob:
            logging.warning(f"Record ID {record_id} - ISBN {isbn} has no embedding data, skipping.")
            continue
        
        # TODO: Check embeddings' table name.
        embeddings_cursor.execute("""
            INSERT INTO books (record_id, isbn, embedding)
            VALUES (?, ?, ?)
        """, (record_id, isbn, embedding_blob))
        embeddings_conn.commit()
        
        pipeline_cursor.execute("UPDATE book_pipeline SET status = ?, last_updated = ? WHERE id = ?", ('loaded', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), record_id))
        pipeline_conn.commit()
        logging.info(f"{record_id} - {isbn} loaded to ChromaDB successfully.")
    
    pipeline_conn.close()
    embeddings_conn.close()

    logging.info("Embeddings saved successfully.")

def rebuild_faiss_index(embeddings_db_path: str, faiss_index_path: str, isbn_map_path: str):
    """ Rebuild the FAISS index with embeddings from the database."""

    if not os.path.exists(embeddings_db_path):
        raise FileNotFoundError(f"Embeddings DB not found: {embeddings_db_path}")
    if not os.path.exists(faiss_index_path):
        raise FileNotFoundError(f"FAISS index file not found: {faiss_index_path}")
    if not os.path.exists(isbn_map_path):
        raise FileNotFoundError(f"ISBN map file not found: {isbn_map_path}")

    # TODO: Consider using batch processing for large datasets.
    conn = sqlite3.connect(embeddings_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT isbn, embedding FROM books")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        raise ValueError("No embeddings found in the embeddings database.")

    isbns = []
    embeddings = []
    for isbn, embedding_blob in rows:
        isbns.append(isbn)
        embeddings.append(np.frombuffer(embedding_blob, dtype=np.float32))
    embeddings = np.stack(embeddings)
    d = embeddings.shape[1]

    
    logging.info(f"Building FAISS index (vector dimension: {d})...")
    index = faiss.IndexFlatL2(d)
    # Map IDs to vectors for easier deletion/update
    index_with_ids = faiss.IndexIDMap(index)
    # FAISS only accepts integer IDs, so use indices starting from 0 as IDs
    faiss_ids = np.arange(len(isbns))
    index_with_ids.add_with_ids(embeddings, faiss_ids)

    logging.info(f"FAISS index built with {len(isbns)} vectors.")

    # Save FAISS index and ISBN mapping
    logging.info(f"Saving FAISS index to '{faiss_index_path}'.")
    faiss.write_index(index_with_ids, faiss_index_path)

    # Mapping from FAISS integer ID to ISBN
    logging.info(f"Saving ISBN mapping to '{isbn_map_path}'.")
    isbn_map = {i: isbn for i, isbn in enumerate(isbns)}
    with open(isbn_map_path, 'wb') as f:
        pickle.dump(isbn_map, f)

    logging.info("Index construction completed.")


def load_to_books_db(pipeline_db_path: str, books_db_path: str):
    """
    Load processed books from the pipeline database to the main SQLite database.
    Args:
        pipeline_db_path (str): Path to the pipeline SQLite database.
        main_db_path (str): Path to the main SQLite database.
    """
    if not os.path.exists(pipeline_db_path):
        logging.error("Pipeline database does not exist.")
        raise FileNotFoundError("Pipeline database does not exist.")
    if not os.path.exists(books_db_path):
        logging.error("Main database does not exist.")
        raise FileNotFoundError("Main database does not exist.")
    
    logging.info("Loading processed books to the main database...")
    
    pipeline_conn = sqlite3.connect(pipeline_db_path)
    pipeline_cursor = pipeline_conn.cursor()
    
    pipeline_cursor.execute(
        """
        SELECT id, libcode, isbn, title, publication_year, kdc, intro, toc, nlk_subjects
        FROM book_pipeline
        WHERE status IN ('loaded', 'failed', 'no_data')
        """
    )
    books_to_load = pipeline_cursor.fetchall()
    
    books_conn = sqlite3.connect(books_db_path)
    books_cursor = books_conn.cursor()
    
    for record_id, libcode, isbn, title, publication_year, kdc, intro, toc, nlk_subjects in books_to_load:
        # Check if the ISBN exists in the main database
        books_cursor.execute("SELECT 1 FROM books WHERE isbn = ?", (isbn,))
        is_book_exist = books_cursor.fetchone()
        
        if is_book_exist:
            # If exists, update the existing book's libraries
            books_cursor.excute("SELECT existlibs FROM books WHERE isbn = ?", (isbn,))
            existlibs = books_cursor.fetchone()[0]
            if existlibs:
                existlibs = json.loads(existlibs)
            else:
                existlibs = []
            existlibs.append(libcode)
            books_cursor.execute("""
                UPDATE books
                SET existlibs = ?
                WHERE ISBN = ?
            """, (json.dumps(list(set(existlibs)), ensure_ascii=False), isbn))
            books_conn.commit()
            logging.info(f"ISBN {isbn} already exists in main database, updated existlibs.")
            
            # If exists, update the status in pipeline to 'completed'
            pipeline_cursor.execute("UPDATE book_pipeline SET status = ?, last_updated = ? WHERE id = ?", ('completed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), record_id))
            pipeline_conn.commit()
            
            logging.info(f"Updated status for record ID {record_id} to 'completed'.")
            
        else:
            # If not exists, insert the book into the main database
            books_cursor.execute("""
                INSERT INTO books (isbn, title, KDC, publication_year, intro, toc, nlk_subjects, existlibs)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (isbn, title, kdc, publication_year, intro or None, toc or None, nlk_subjects if nlk_subjects else None, json.dumps([libcode], ensure_ascii=False)))
            books_conn.commit()
            logging.info(f"Inserted new book with ISBN {isbn} into main database.")
            
            # Update the status in pipeline to 'completed'
            pipeline_cursor.execute("UPDATE book_pipeline SET status = ?, last_updated = ? WHERE id = ?", ('completed', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), record_id))
            pipeline_conn.commit()
            logging.info(f"Updated status for record ID {record_id} to 'completed'.")

    pipeline_conn.close()
    books_conn.close()

    logging.info("Books loaded to the main database successfully.")

if __name__ == "__main__":
    rebuild_faiss_index(
        embeddings_db_path='path/to/embeddings.db',
        faiss_index_path='path/to/faiss.index',
        isbn_map_path='path/to/isbn_map.pkl'
    )