# -*- coding: utf-8 -*-
"""
Configuration module for SH Navigator API

This module contains all configuration constants and environment variables
used throughout the application.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path="/home/namu101/msga/env")

DATA_DIR = "/home/namu101/msga/data"

# Database Paths
DATABASE_PATH = os.path.join(DATA_DIR, 'sh_navigator.db')
KDC_DB_PATH = os.path.join(DATA_DIR, 'kdc_sections', 'sections.db')

# FAISS Index Paths
BOOKS_FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss/book_faiss_index.faiss')
ISBN_MAP_PATH = os.path.join(DATA_DIR, 'faiss/book_isbn_map.pkl')
SUBJECTS_FAISS_INDEX_PATH = os.path.join(DATA_DIR, 'faiss/subject_faiss_index.faiss')
NODE_ID_MAP_PATH = os.path.join(DATA_DIR, 'faiss/subject_node_id_map.pkl')

# Model Configuration
MODEL_NAME = "nlpai-lab/KURE-v1"
MODEL_SERVER_URL = "http://127.0.0.1:8001"

# Network Interaction Server Configuration
NETWORK_SERVER_URL = "http://127.0.0.1:8002"

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

# Database Connection Pool Configuration
DB_POOL_MAX_CONNECTIONS = 20
DB_POOL_MIN_CONNECTIONS = 2
DB_CONNECTION_TIMEOUT = 30

# Chat Session Configuration
SESSION_TIMEOUT = 1800  # 30 minutes in seconds

# CORS Configuration
CORS_ORIGINS = ["*"]  # Change to specific domains in production

# Pagination Configuration
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_VECTOR_SEARCH_LIMIT = 25
MAX_VECTOR_SEARCH_LIMIT = 100
MAX_NETWORK_NEIGHBORS = 50

# Query Processing Configuration
MAX_QUERY_LENGTH = 200
