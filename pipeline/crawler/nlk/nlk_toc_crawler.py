# -*- coding: utf-8 -*-
# =========================
# Setup
# 0. We cannot use the requests module since NLK blocks Python's requests module(???), so we use CFFI to call C code.
# 1. You need pre-requisites to compile the C code:
#   $ sudo apt-get install libcurl4-openssl-dev gcc
# 2. Then, compile the C code to create a shared library:
#   $ gcc -shared -fPIC -o librequests_c.so http_get_client.c -lcurl
# 3. Make sure all necessary packages are installed(venv recommended):
#   $ pip install cffi python-dotenv beautifulsoup4 lxml
# =========================

import os
import requests
import time
import re
import json
from cffi import FFI
import logging
from crawler.crawler_status import CrawlerStatus
from config import NLK_API_KEY


# Configure logging for the script
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

# =========================
# HTTP Utilities
# =========================
def _fetch_toc(url):
    """ Fetches the TOC content from the given URL."""
    
    time.sleep(0.5) # To avoid overwhelming the server with requests
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except Exception as e:
        logging.info(f"Error fetching {url}: {e}")
        return None

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
# NLK API Logic
# =========================
def _get_viewkey_by_isbn_nlk_api(api_key, isbn):
    time.sleep(0.5) # To avoid overwhelming the server with requests
    base_url = 'http://www.nl.go.kr/NL/search/openApi/search.do'
    try:
        my_params = {
            'key': api_key,
            'apiType': 'json',
            'detailSearch': 'true',
            'isbnOp': 'isbn',
            'isbnCode': isbn,
        }
        response = _get_with_c(base_url, params=my_params, timeout=5)
        if response.status_code != 200:
            return CrawlerStatus.CONN_FAIL, None
        data = json.loads(response.text)
        if data.get("errorCode"):
            return CrawlerStatus.CONN_FAIL, None
        total_count = int(data.get("total", 0))
        if total_count == 0:
            return CrawlerStatus.RESULT_EMPTY, None
        book = data["result"][0]
        viewkey_url = book.get("detailLink", None)
        if not viewkey_url:
            return CrawlerStatus.RESULT_EMPTY, None
        viewkey = re.search(r'(?:#viewKey=)(\d+)(?:&)', viewkey_url)
        if not viewkey:
            return CrawlerStatus.RESULT_EMPTY, None
        return CrawlerStatus.SUCCESS, viewkey.group(1)
    except (ConnectionError, ValueError) as e:
        return CrawlerStatus.INTERNAL_ERROR, "request_c module error: " + str(e)
    except json.JSONDecodeError:
        return CrawlerStatus.INTERNAL_ERROR, "Failed to decode JSON response from NLK API."
    except KeyError:
        return CrawlerStatus.INTERNAL_ERROR, "Unexpected response structure from NLK API."

# =========================
# Main Logic
# =========================
def crawl_nlk_toc(isbn : str) -> tuple[CrawlerStatus, str]:
    """
    Main function to crawl the Table of Contents (TOC) for a given ISBN from the NLK API.
    Args:
        isbn (str): The ISBN of the book to fetch the TOC for.
    Returns:
        NLKStatus: The status of the operation.
        str: The TOC content if successful, otherwise an empty string or error message.
    """    
    status, result = _get_viewkey_by_isbn_nlk_api(api_key=NLK_API_KEY, isbn=isbn)
    if status == CrawlerStatus.CONN_FAIL:
        return CrawlerStatus.CONN_FAIL, None
    elif status == CrawlerStatus.RESULT_EMPTY:
        return CrawlerStatus.RESULT_EMPTY, None
    elif status == CrawlerStatus.INTERNAL_ERROR:
        return CrawlerStatus.INTERNAL_ERROR, result
    else:
        # If we have a valid viewkey, fetch the TOC
        viewkey = result
        toc_url = f"https://www.nl.go.kr/NL/tocDownload.do?downData={viewkey},AH1"
        toc_content = _fetch_toc(toc_url)
        if toc_content:
            if toc_content.startswith("null"):
                return CrawlerStatus.NO_TOC, None
            else:
                toc_content = toc_content.replace('<body>', '').replace('</body>', '').strip()
                return CrawlerStatus.SUCCESS, toc_content
        else:
            return CrawlerStatus.CONN_FAIL, None
        


