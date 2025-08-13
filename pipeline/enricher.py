# enricher.py
import sqlite3
import logging
import json
import os
from datetime import datetime
from pipeline.crawler.nlk.nlk_toc_crawler import crawl_nlk_toc
from pipeline.crawler.nlk.nlk_subject_crawler import crawl_nlk_subjects
from crawler.daum.daum_crawler import crawl_daum
from crawler.gemini.gemini_crawler import crawl_gemini
from crawler.crawler_status import CrawlerStatus



# Configure logging for the script
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s"
)

def _update_pipeline_db(cursor, record_id: str, intro: str, toc: str, subjects: list, status: str):
    """
    Update the record in the pipeline database.
    Args:
        cursor: SQLite cursor object.
        record_id (str): ID of the book record.
        intro (str): Intro text to set (can be None).
        toc (str): Table of contents text to set (can be None).
        subjects (str): Subjects to set (can be None).
        status (str): New status to set.
    
    subjects example: [{'type': 'nlsh', 'label': 'Medicine', 'id': 'KSH1234567890'}, ...]
    """
    cursor.execute("""
        UPDATE book_pipeline 
        SET intro = coalesce(?, intro), toc = coalesce(?, toc), nlk_subjects = coalesce(?, nlk_subjects), status = coalesce(?, status), last_updated = ?
        WHERE id = ?
    """, (intro, toc, json.dumps(subjects, ensure_ascii=False), status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), record_id))
    cursor.connection.commit()

def enrich_books(pipeline_db_path: str, main_db_path: str, gemini_search_grounding: bool = False):
    """
    Enrich books in the pipeline database by crawling external sources for intro and TOC.
    Args:
        pipeline_db_path (str): Path to the pipeline SQLite database.
        book_db_path (str): Path to the book SQLite database.
        gemini_search_grounding (bool): Whether to use Gemini Search Grounding for missing data.
    """

    if not os.path.exists(pipeline_db_path):
        logging.error("Pipeline database does not exist.")
        raise FileNotFoundError("Pipeline database does not exist.")
    if not os.path.exists(main_db_path):
        logging.error("Book database does not exist.")
        raise FileNotFoundError("Book database does not exist.")

    pipeline_conn = sqlite3.connect(pipeline_db_path)
    pipeline_cursor = pipeline_conn.cursor()

    book_conn = sqlite3.connect(main_db_path)
    book_cursor = book_conn.cursor()


    # Fetch books with status 'new' for enrichment
    pipeline_cursor.execute("SELECT id, isbn FROM book_pipeline WHERE status = 'new'")
    books_to_enrich = pipeline_cursor.fetchall()

    for record_id, isbn in books_to_enrich:
        # Skip books already present in Book DB
        book_cursor.execute("SELECT COUNT(*) FROM books WHERE isbn = ?", (isbn,))
        if book_cursor.fetchone()[0]:
            logging.info(f"ISBN {isbn} already exists in ChromaDB, skipping enrichment.")
            _update_pipeline_db(pipeline_cursor, record_id, None, None, None, 'loaded')
            continue
        
        intro = None
        toc = None

        # 1. NLK TOC Crawling
        status, result = crawl_nlk_toc(isbn)
        if status == CrawlerStatus.SUCCESS:
            toc = result
            logging.info(f"NLK: Fetched TOC for ISBN {isbn}")
        elif status == CrawlerStatus.INTERNAL_ERROR:
            logging.error(f"NLK: Internal Error fetching TOC for ISBN {isbn} with NLK: {result}")
        elif status in (CrawlerStatus.RESULT_EMPTY, CrawlerStatus.NO_TOC):
            logging.info(f"NLK: No TOC found for ISBN {isbn}. Status: {status}")

        # 2. NLK Subjects Crawling
        # subjects example: [{'type': 'nlsh', 'label': 'Medicine', 'id': 'KSH1234567890'}, ...]
        status, subjects = crawl_nlk_subjects(isbn)
        if status == CrawlerStatus.SUCCESS:
            logging.info(f"NLK: Fetched subjects for ISBN {isbn}")
            if subjects:
                _update_pipeline_db(pipeline_cursor, record_id, None, None, subjects, None)
        elif status == CrawlerStatus.INTERNAL_ERROR:
            logging.error(f"NLK: Internal Error fetching subjects for ISBN {isbn}: {subjects}")
            _update_pipeline_db(pipeline_cursor, record_id, None, None, [], None)
        elif status == CrawlerStatus.RESULT_EMPTY:
            logging.info(f"NLK: No subjects found for ISBN {isbn}. Status: {status}")
            _update_pipeline_db(pipeline_cursor, record_id, None, None, [], None)
    

        # 3. Daum Search Crawling
        status, result = crawl_daum(isbn)
        if status == CrawlerStatus.SUCCESS:
            intro = result.get('intro')
            # Prefer NLK TOC if already fetched, otherwise use Daum's
            toc = result.get('toc') if not toc else toc
        elif status == CrawlerStatus.INTERNAL_ERROR:
            logging.error(f"Daum: Error fetching book info for ISBN {isbn}: {result}")
        elif status == CrawlerStatus.RESULT_EMPTY:
            logging.info(f"Daum: No book info found for ISBN {isbn}. Status: {status}")
        elif status == CrawlerStatus.NO_INTRO:
            toc = result.get('toc') if not toc else toc
        elif status == CrawlerStatus.NO_TOC:
            intro = result.get('intro') if not intro else intro

        # 4. Gemini Search Grounding (batch processing handled later)

        # 5. Update the book_pipeline table with the enriched data
        # If the TOC contains a specific message, treat it as missing
        # Check for missing TOC messages and set toc to None if found
        if toc and any(s in toc for s in ['목차가 없습니다', '목차가 없는 도서입니다', '목차 정보가 없습니다']):
            toc = None

        if intro:
            _update_pipeline_db(pipeline_cursor, record_id, intro, toc, None, 'enriched')
        elif gemini_search_grounding and not intro:
            _update_pipeline_db(pipeline_cursor, record_id, intro, toc, None, 'gemini_batch')
        else:
            _update_pipeline_db(pipeline_cursor, record_id, intro, toc, None, 'no_data')

    pipeline_conn.commit()
    pipeline_conn.close()
    book_conn.close()

    # 6. Process Gemini Search Grounding if enabled
    if gemini_search_grounding:
        # Reconnect to DB for Gemini batch processing
        pipeline_conn = sqlite3.connect(pipeline_db_path)
        pipeline_cursor = pipeline_conn.cursor()
        pipeline_cursor.execute("SELECT id, isbn, title FROM book_pipeline WHERE status = 'gemini_batch'")
        gemini_books = pipeline_cursor.fetchall()

        # Split books into chunks for batch processing
        n = 5
        gemini_books_dicts = [
            {"id": record_id, "isbn": isbn, "title": title}
            for record_id, isbn, title in gemini_books
        ]
        gemini_book_chunks = [gemini_books_dicts[i:i + n] for i in range(0, len(gemini_books_dicts), n)]

        for chunk in gemini_book_chunks:
            # Each chunk is a list of dicts with keys: id, isbn, title
            status, books = crawl_gemini(chunk)  # Process chunk with Gemini
            if status == CrawlerStatus.SUCCESS:
                for book in books:
                    # Update status based on Gemini enrichment result
                    if book.get('summary'):
                        _update_pipeline_db(pipeline_cursor, book['id'], None, None, None, 'enriched')
                    else:
                        _update_pipeline_db(pipeline_cursor, book['id'], None, None, None, 'failed')
                    logging.info(f"Gemini Search Grounding enriched book {book['isbn']} with summary.")
            else:
                logging.error(f"Gemini Search Grounding failed for chunk: {chunk}. Status: {status}")
                continue

        # Mark any remaining 'gemini_batch' books as 'failed'
        pipeline_cursor.execute("UPDATE book_pipeline SET status = 'failed' WHERE status = 'gemini_batch'")
        pipeline_conn.commit()
        pipeline_conn.close()