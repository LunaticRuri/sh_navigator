# -*- coding: utf-8 -*-
# =========================
# Setup
# 0. We cannot use the requests module since NLK blocks Python's requests module(???), so we use CFFI to call C code.
# 1. You may need pre-requisites to compile the C code:
#   $ sudo apt-get install libcurl4-openssl-dev gcc
# 2. Then, compile the C code to create a shared library:
#   $ gcc -shared -fPIC -o librequests_c.so http_get_client.c -lcurl
# 3. Make sure all necessary packages are installed(venv recommended):
#   $ pip install cffi python-dotenv beautifulsoup4 lxml
# =========================

import os
import re
import sqlite3
import json
from cffi import FFI
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from crawler.crawler_status import CrawlerStatus

# =========================
# Config & Constants
# =========================

# Load environment variables from .env file
load_dotenv()
NLK_API_KEY = os.getenv('NLK_API_KEY')

# Configure logging for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

# =========================
# CFFI HTTP Client
# =========================
ffi = FFI()
ffi.cdef("""
    typedef struct {
        char *body;
        size_t size;
        long status_code;
        char *url;
    } Response;
    typedef struct {
        const char *key;
        const char *value;
    } KeyValue;
    Response* requests_get(const char *base_url, const KeyValue *params, const KeyValue *headers, double timeout_seconds);
    void free_response(Response *response);
""")
C_LIB = ffi.dlopen(os.path.join(os.path.dirname(__file__), "librequests_c.so"))

class CResponse:
    def __init__(self, c_response_ptr):
        if c_response_ptr == ffi.NULL:
            raise ConnectionError("Request failed. Check stderr for C-level error details (e.g., timeout).")
        self._c_response = c_response_ptr

    @property
    def status_code(self):
        return self._c_response.status_code

    @property
    def text(self):
        return ffi.string(self._c_response.body).decode('utf-8')

    @property
    def url(self):
        if self._c_response.url == ffi.NULL:
            return None
        return ffi.string(self._c_response.url).decode('utf-8')

    def __del__(self):
        if hasattr(self, '_c_response'):
            C_LIB.free_response(self._c_response)

def _dict_to_keyvalue(d):
    if not d:
        return ffi.NULL, []
    kv_array = ffi.new("KeyValue[]", len(d) + 1)
    kept_alive = []
    for i, (key, value) in enumerate(d.items()):
        c_key = ffi.new("char[]", str(key).encode('utf-8'))
        c_value = ffi.new("char[]", str(value).encode('utf-8'))
        kept_alive.extend([c_key, c_value])
        kv_array[i].key = c_key
        kv_array[i].value = c_value
    kv_array[len(d)].key = ffi.NULL
    kv_array[len(d)].value = ffi.NULL
    return kv_array, kept_alive

def _get_with_c(url, params=None, headers=None, timeout=None):
    c_params, params_kept_alive = _dict_to_keyvalue(params)
    c_headers, headers_kept_alive = _dict_to_keyvalue(headers)
    c_timeout = float(timeout) if timeout else 0.0
    c_response_ptr = C_LIB.requests_get(url.encode('utf-8'), c_params, c_headers, c_timeout)
    return CResponse(c_response_ptr)

# =========================
# LOD Logic
# =========================

def _get_viewkey(isbn : str = None, api_key : str = NLK_API_KEY) -> str:
    """ Fetches the viewkey for a given ISBN from the NLK API."""
    if not api_key:
        logging.error("NLK API key is not set. Please set the NLK_API_KEY environment variable.")
        return None
    if not isbn:
        logging.error("ISBN is required to fetch the Lod link.")
        return None

    base_url = 'http://www.nl.go.kr/NL/search/openApi/search.do'
    my_params = {
        'key': api_key,
        'apiType': 'json',
        'detailSearch': 'true',
        'isbnOp': 'isbn',
        'isbnCode': isbn,
    }
    response = _get_with_c(base_url, params=my_params, timeout=5)
    if response.status_code == 200:
        
        data = json.loads(response.text)
        if data.get("errorCode"):
            return None
        
        total_count = int(data.get("total", 0))
        if total_count == 0:
            return None
        
        book = data["result"][0]
        viewkey_url = book.get("detailLink", None)
        if not viewkey_url:
            return None
        
        viewkey = re.search(r'(?:#viewKey=)(.*?)(?:&)', viewkey_url)
        if not viewkey:
            return None
        
        return viewkey.group(1)  

def _get_komarc(viewkey : str) -> str:
    """ Fetches KOMARC data from NLK using the provided viewkey. """
    
    if not viewkey:
        logging.error("Detail link is required to fetch subjects.")
        return None
    
    detail_link = f'http://www.nl.go.kr/NL/marcDownload.do?downData={viewkey},AH1'
    response = _get_with_c(detail_link, timeout=5)
    if response.status_code != 200:
        logging.error(f"Failed to fetch subjects from {detail_link}. Status code: {response.status_code}")
        return None
    
    return response.text

def _get_mods(viewkey : str) -> str:
    """ Fetches MODS data from NLK using the provided viewkey. """
    
    if not viewkey:
        logging.error("Viewkey is required to fetch MODS data.")
        return None
    
    mods_url = f'https://www.nl.go.kr/NL/search/mods_view.do?contentsId={viewkey}'
    response = _get_with_c(mods_url, timeout=5)
    if response.status_code != 200:
        logging.error(f"Failed to fetch MODS data from {mods_url}. Status code: {response.status_code}")
        return None
    
    return response.text

def _extract_subjects_from_komarc(komarc_data: str) -> List[Dict[str, Any]]:
    """
    Extracts subject fields (650) from a KOMARC data string and returns a list of subject dictionaries.

    This function converts the KOMARC data string to bytes to accurately handle field positions,
    since KOMARC field offsets are byte-based and may include multi-byte characters (e.g., Korean).

    Args:
        komarc_data (str): The original KOMARC data as a string.

    Returns:
        list: A list of dictionaries containing extracted subject information.
              Example: [{'type': 'nlsh', 'label': 'Medicine', 'id': 'KSH1234567890'}, ...]
    """
    subjects = []
    try:
        # Since KOMARC field positions are byte-based, convert to bytes for accurate slicing.
        komarc_bytes = komarc_data.encode('utf-8')

        leader_bytes = komarc_bytes[:24]
        base_address = int(leader_bytes[12:17].decode('ascii'))

        directory_bytes = komarc_bytes[24:base_address]

        directory_entries = [directory_bytes[i:i+12] for i in range(0, len(directory_bytes), 12)]
        
        data_fields_bytes = komarc_bytes[base_address:]

        for entry in directory_entries:
            tag = entry[:3].decode('ascii')
            
            if tag == '650':
                field_length = int(entry[3:7].decode('ascii'))
                start_pos = int(entry[7:12].decode('ascii'))
                
                # Use the byte position (start_pos) and field length (field_length) from the directory
                # to extract the field's bytes from the data fields section.
                # Subtract 1 from the length to exclude the field terminator character.
                field_bytes = data_fields_bytes[start_pos : start_pos + field_length - 1]

                # Decode the extracted byte data back to a string for parsing
                field_data_str = field_bytes.decode('utf-8')
                    
                #For debugging, logging.info(repr(field_data_str))
                # logging.info(repr(field_data_str))
                
                # NLSH (National Library of Korea Subject Headings)
                match = re.search(r'8\x1fa(.*?)(?:\x1f|$)', field_data_str)
                if match:
                    subject_label = match.group(1).strip()
                    # Try to extract the KSH ID (e.g., KSH1234567890)
                    ksh_match = re.search(r'\x1f0KSH(\d{10})', field_data_str)
                    subject_ksh = f'KSH{ksh_match.group(1)}' if ksh_match else None
                    subjects.append({
                        'type': 'nlsh',
                        'label': subject_label,
                        'id': subject_ksh
                    })
                
                # LCSH (Library of Congress Subject Headings)
                lcsh_label_match = re.search(r'0\x1fa(.*?)(?:\x1f|$)', field_data_str)
                if lcsh_label_match:
                    subject_label = lcsh_label_match.group(1).strip()
                    # Try to extract the LCSH ID (if available)?
                    lcsh_id_match = re.search(r'\x1f0([^\x1f]+)', field_data_str)
                    subject_lcsh = lcsh_id_match.group(1).strip() if lcsh_id_match else None
                    subjects.append({
                        'type': 'lcsh',
                        'label': subject_label,
                        'id': subject_lcsh
                    })

    except (ValueError, IndexError, UnicodeDecodeError) as e:
        print(f"An error occurred while parsing the data: {e}")
        print("The provided data may not conform to the standard KOMARC structure or there may be an encoding issue.")

    return subjects

def _extract_subjects_from_mods(mods_data: str) -> List[Dict[str, Any]]:
    """
    Extracts subject fields from MODS data and returns a list of subject dictionaries.
    
    Args:
        mods_data (str): The MODS data as a string.
        
    Returns:
        list: A list of dictionaries containing extracted subject information.
    """
    subjects = []
    soup = BeautifulSoup(mods_data, 'xml')
    
    for subject in soup.find_all('subject'):
        subject_id = subject.get('ID', None)
        subject_authority = subject.get('authority', None)
        subject_label = subject.get_text(strip=True)
        if not subject_label:
            continue
        
        if subject_authority == '국립중앙도서관주제명표목표':
            subjects.append({
                'type': 'nlsh',
                'label': subject_label,
                'id': subject_id
            })
        elif subject_authority == 'lcsh':
            subjects.append({
                'type': 'lcsh',
                'label': subject_label,
                'id': subject_id
            })
        else:
            subjects.append({
                'type': 'other',
                'label': subject_label,
                'id': subject_id
            })
    
    return subjects

# =========================
# Main Logic
# =========================

def main():
    db_path = './books_part_6.db'
    
    if not os.path.exists(db_path):
        logging.info("Database file does not exist.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ISBN FROM books WHERE is_updated = 0 AND (toc IS NOT NULL OR intro IS NOT NULL)")
    isbn_list = cursor.fetchall()

    logging.info(f"Fetched {len(isbn_list)} ISBNs from the database.")

    if not isbn_list:
        logging.info("No ISBNs found in the database.")
        return

    for isbn in isbn_list:
        isbn = isbn[0]    
        
        try:
            viewkey = _get_viewkey(isbn=isbn, api_key=NLK_API_KEY)
            
            if viewkey:
                # MODS
                if not viewkey.isdigit():
                    subjects = _extract_subjects_from_mods(_get_mods(viewkey))
                # KOMARC
                else:
                    subjects = _extract_subjects_from_komarc(_get_komarc(viewkey))
            else:
                subjects = []
        except Exception as e:
            logging.error(f"Error processing ISBN {isbn}: {e}")
            subjects = []
            return CrawlerStatus.INTERNAL_ERROR, None
        
        if subjects:
            return CrawlerStatus.SUCCESS, subjects
        else:
            logging.info(f"No subjects found for ISBN {isbn}.")
            return CrawlerStatus.RESULT_EMPTY, None