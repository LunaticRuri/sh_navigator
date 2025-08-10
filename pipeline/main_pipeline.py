import fetcher
import enricher
import processor
import loader
import logging


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

# Change these paths to your actual database paths
LIBRARY_DB_PATH = '/Users/nuriseok/sh_navigator/pipeline/db/library.db'
PIPELINE_DB_PATH = '/Users/nuriseok/sh_navigator/pipeline/db/pipeline_db.db'
EMBEDDINGS_DB_PATH = '/Users/nuriseok/sh_navigator/data/embeddings.db'
FAISS_INDEX_PATH = '/Users/nuriseok/sh_navigator/data/faiss/book_faiss_index.faiss'
ISBN_MAP_PATH = '/Users/nuriseok/sh_navigator/data/faiss/book_isbn_map.pkl'
BOOKS_DB_PATH = '/Users/nuriseok/sh_navigator/data/books.db'


def run_full_pipeline():
    """
    Run the full data pipeline from fetching new books.
    """
    logging.info("===== Starting data pipeline =====")
    fetcher.fetch_new_books(library_db_path=LIBRARY_DB_PATH, pipeline_db_path=PIPELINE_DB_PATH, n_weeks=1)
    enricher.enrich_books(pipeline_db_path=PIPELINE_DB_PATH, books_db_path=BOOKS_DB_PATH)
    processor.process_and_embed(pipeline_db_path=PIPELINE_DB_PATH)
    
    loader.save_embeddings(embeddings_db_path=EMBEDDINGS_DB_PATH, pipeline_db_path=PIPELINE_DB_PATH)
    loader.rebuild_faiss_index()
    loader.load_to_books_db(pipeline_db_path=PIPELINE_DB_PATH, books_db_path=BOOKS_DB_PATH)
    logging.info("===== Data pipeline completed =====")

if __name__ == "__main__":
    run_full_pipeline()