import fetcher
import enricher
import processor
import loader
import logging
from config import LIBRARY_DB_PATH, PIPELINE_DB_PATH, EMBEDDINGS_DB_PATH, DATABASE_PATH

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")


# TODO: 작동 테스트 해보고 안되면 수정해야 함.
def run_full_pipeline():
    """
    Run the full data pipeline from fetching new books.
    """
    
    logging.info("===== Starting data pipeline =====")
    
    fetcher.fetch_new_books(library_db_path=LIBRARY_DB_PATH, pipeline_db_path=PIPELINE_DB_PATH, n_weeks=1)
    
    enricher.enrich_books(pipeline_db_path=PIPELINE_DB_PATH, main_db_path=DATABASE_PATH)
    
    processor.process_and_embed(pipeline_db_path=PIPELINE_DB_PATH)
    
    loader.save_embeddings(main_db_path=EMBEDDINGS_DB_PATH, pipeline_db_path=PIPELINE_DB_PATH)
    loader.rebuild_faiss_index()
    loader.load_to_main_db(pipeline_db_path=PIPELINE_DB_PATH, main_db_path=DATABASE_PATH)

    logging.info("===== Data pipeline completed =====")

if __name__ == "__main__":
    run_full_pipeline()