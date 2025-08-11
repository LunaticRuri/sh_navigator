import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="/home/namu101/msga/env")


# Database Paths
DATA_DIR = "/home/namu101/msga/data"

DATABASE_PATH = os.path.join(DATA_DIR, 'sh_navigator.db')

# Change these paths to your actual database paths
LIBRARY_DB_PATH = os.path.join('libraries.db')
PIPELINE_DB_PATH = os.path.join('pipeline_db.db')
BOOKS_FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss/book_faiss_index.faiss')
ISBN_MAP_PATH = os.path.join(DATA_DIR, 'faiss/book_isbn_map.pkl')

# API Keys
DATA4LIBRARY_API_KEY = os.getenv('DATA4LIBRARY_API_KEY')
NLK_API_KEY = os.getenv('NLK_API_KEY')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Configuration
EMBEDDING_MODEL = "nlpai-lab/KURE-v1"
GEMINI_MODEL = "gemini-2.5-flash"