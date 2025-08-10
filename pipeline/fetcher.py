# fetcher.py

import requests
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import logging
from typing import Dict, List, Any

# Load environment variables from .env file
load_dotenv()

# Configure logging for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

# Retrieve API key from environment variables
DATA4LIBRARY_API_KEY = os.getenv('DATA4LIBRARY_API_KEY')

def _get_target_libraries(library_db_path: str, n_weeks: int = 1) -> List[str]:
    """
    Returns a list of libraries that have not been updated within the specified number of weeks.
    :param library_db_path: Path to the library database file.
    :param n_weeks: Number of weeks to look back for outdated libraries.
    :return: List of (libcode, name, updated_at) tuples for libraries needing updates.
    """
    conn = sqlite3.connect(library_db_path)
    cursor = conn.cursor()
    # Calculate the cutoff datetime for outdated libraries
    n_weeks_ago = (datetime.now() - timedelta(weeks=n_weeks)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "SELECT libcode, name, updated_at FROM libraries WHERE updated_at <= ? ORDER BY updated_at ASC",
        (n_weeks_ago,)
    )
    libraries = [row for row in cursor.fetchall()]
    conn.close()
    return libraries

def _set_library_updated(library_db_path: str, libcode: str):
    """
    Updates the last updated time for a specific library in the library database.
    :param library_db_path: Path to the library database file.
    :param libcode: Library code to update.
    """
    conn = sqlite3.connect(library_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE libraries SET updated_at = ? WHERE libcode = ?",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), libcode)
    )
    conn.commit()
    conn.close()

def _save_new_books(books: List[Dict[str, Any]], libcode: str, pipeline_db_path: str = './pipeline/db/pipeline_db.db'):
    """
    Saves new books to the pipeline database and updates the library's last updated time.
    :param books: List of new books to save.
    :param libcode: Library code for the books.
    :param pipeline_db_path: Path to the pipeline database file.
    """
    # Connect to the pipeline database and ensure the book_pipeline table exists
    conn = sqlite3.connect(pipeline_db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS book_pipeline (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            libcode TEXT,
            isbn TEXT,
            title TEXT,
            publication_year TEXT,
            kdc TEXT,
            intro TEXT,
            toc TEXT,
            nlk_subjects TEXT,
            embedding BLOB,
            status TEXT,
            last_updated DATETIME
        )
    """)
    cursor = conn.cursor()

    # Insert new books, ignoring duplicates based on (isbn, libcode)
    for book in books:
        cursor.execute("""
            INSERT OR IGNORE INTO book_pipeline (libcode, isbn, title, publication_year, kdc, status, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            libcode or None,
            book.get('isbn13') or None,
            book.get('title') or None,
            book.get('publication_year') or None,
            book.get('kdc') or None,
            'new',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

    conn.commit()
    conn.close()

    logging.info(f"Saved {len(books)} new books to the pipeline database for library {libcode}.")

def _is_valid_isbn(isbn: str) -> bool:
    """
    Validate the ISBN-13 format.
    :param isbn: ISBN string to validate.
    :return: True if valid, False otherwise.
    """
    isbn = isbn.replace('-', '').replace(' ', '')
    if len(isbn) == 13 and isbn.isdigit():
        total = sum((int(isbn[i]) if i % 2 == 0 else int(isbn[i]) * 3) for i in range(12))
        check_digit = (10 - (total % 10)) % 10
        return check_digit == int(isbn[-1])
    return False

def fetch_new_books(library_db_path : str, pipeline_db_path : str, n_weeks: int = 1):
    """
    Fetches new books from the Data4Library API for libraries that need updates and saves them to the pipeline database.
    :param library_db_path: Path to the library database file.
    :param pipeline_db_path: Path to the pipeline database file.
    :param n_weeks: Number of weeks to look back for outdated libraries.
    """

    if not os.path.exists(library_db_path):
        logging.error("Library database does not exist.")
        raise FileNotFoundError("Library database does not exist.")
    if not os.path.exists(pipeline_db_path):
        logging.error("Pipeline database does not exist.")
        raise FileNotFoundError("Pipeline database does not exist.")

    # Get libraries that need to be updated
    target_libraries = _get_target_libraries(library_db_path=library_db_path, n_weeks=n_weeks)

    if not target_libraries:
        logging.info("No libraries need to be updated.")
        return

    # TODO: 실제에서는 바꾸기!
    # Limit to 3 libraries per run to avoid overloading the API
    if len(target_libraries) > 3:
        logging.info(f"Limiting to the first 3 libraries out of {len(target_libraries)} total libraries.")
        logging.info("This is a temporary limit for testing purposes.")
        logging.info("Change this limit in the code when ready for production.")
    target_libraries = target_libraries[:3]

    endpoint = "http://data4library.kr/api/itemSrch"
    FETCH_PAGE_SIZE = 100  # Number of items per page

    for libcode, name, updated_at in target_libraries:
        # Skip specific libraries by code
        if libcode == '000000':
            logging.info("Skipping library with code 000000 (NLK).")
            continue
        logging.info(f"Fetching new books for library {name} ({libcode})")

        # Format the last updated date for the API request
        updated_at_fmt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")

        params = {
            'authKey': DATA4LIBRARY_API_KEY,
            'libCode': libcode,
            'startDt': updated_at_fmt,
            'endDt': datetime.now().strftime('%Y-%m-%d'),
            'pageNo': 1,
            'pageSize': 1,  # First request to get the total count
            'format': 'json'
        }

        books = []  # List to store all fetched books

        try:
            # Initial request to get the total number of new books
            response = requests.get(endpoint, params=params)
            response.raise_for_status()
            data = response.json()['response']

            if 'request' in data:
                num_found = data.get('numFound', 0)
                if num_found == 0:
                    logging.info(f"No new books found for library {name}.")
                    logging.info(f"Url for library {name}({libcode}): {requests.utils.unquote(response.url)}")
                    _set_library_updated(library_db_path=library_db_path, libcode=libcode)
                    continue
                logging.info(f"Found {num_found} new books for library {name}({libcode}).")
                total_pages = (num_found // FETCH_PAGE_SIZE) + 1

                # Fetch all pages of new books
                for page in range(1, total_pages + 1):
                    params['pageNo'] = page
                    params['pageSize'] = FETCH_PAGE_SIZE

                    response = requests.get(endpoint, params=params)
                    response.raise_for_status()
                    data = response.json()['response']

                    if 'request' in data:
                        docs = data.get('docs', [])
                        if not docs:
                            logging.info(f"No books found on page {page} for library {name}({libcode}).")
                        else:
                            logging.info(f"Processing {len(docs)} books on page {page} for library {name}({libcode}).")
                            # Extract relevant fields from each book document
                            docs = [
                                {
                                    'isbn13': elem['doc'].get('isbn13', ''),
                                    'title': elem['doc'].get('bookname', ''),
                                    'publication_year': elem['doc'].get('publication_year', ''),
                                    'kdc': elem['doc'].get('class_no', ''),
                                    'libCode': libcode
                                }
                                for elem in docs
                                if 'isbn13' in elem['doc'] and 'bookname' in elem['doc']
                                and _is_valid_isbn(elem['doc'].get('isbn13', ''))
                            ]
                            books.extend(docs)
                    else:
                        # Handle unexpected API response format
                        logging.error(f"Error fetching books for {name}: {data.get('message', 'Unknown error')}")
                        continue

            else:
                # Handle unexpected API response format
                logging.error(f"Error fetching books for {name}: {data}")
        except requests.RequestException as e:
            logging.error(f"Request failed for library {name}: {e}")

        # Save fetched books to the pipeline database
        if books:
            logging.info(f"Processing {len(books)} new books for library {name}({libcode}).")
            _save_new_books(books, libcode, pipeline_db_path=pipeline_db_path)
            _set_library_updated(library_db_path=library_db_path, libcode=libcode)
