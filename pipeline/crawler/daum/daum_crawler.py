import time
import requests
from bs4 import BeautifulSoup
import logging
from typing import Optional, Dict, Any, Tuple, List
from crawler.crawler_status import CrawlerStatus


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")

HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

def _fetch_page(url: str, timeout: int = 5) -> Tuple[CrawlerStatus, Optional[str]]:
    try:
        time.sleep(0.5)
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        return CrawlerStatus.SUCCESS, response.text
    except requests.RequestException as e:
        logging.warning(f"Failed to fetch {url}: {e}")
        return CrawlerStatus.CONN_FAIL, None

def _get_book_link_from_page(url: str) -> Tuple[CrawlerStatus, Any]:
    status, html_content = _fetch_page(url)
    if status == CrawlerStatus.CONN_FAIL:
        return CrawlerStatus.CONN_FAIL, None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    if soup.find('div', id='noResult'):
        return CrawlerStatus.RESULT_EMPTY, None
    
    book_link = soup.find('c-title')
    if not book_link:
        return CrawlerStatus.RESULT_EMPTY, None
    
    return CrawlerStatus.SUCCESS, 'https://search.daum.net/search' + book_link['data-href']

def _get_book_info(url: str) -> Tuple[CrawlerStatus, Optional[Dict[str, str]]]:

    status, html_content = _fetch_page(url)
    
    if status == CrawlerStatus.CONN_FAIL:
        return CrawlerStatus.CONN_FAIL, None
    
    soup = BeautifulSoup(html_content, 'html.parser')
    sections = soup.find_all('div', class_='info_section')
    if not sections:
        return CrawlerStatus.INTERNAL_ERROR, None
    
    book_intro, book_toc = '', ''
    for section in sections:
        section_type = section.find('h3')
        if not section_type:
            continue
        section_type = section_type.text.strip()
        if section_type == '책소개':
            book_intro = section.find('p', class_='desc').get_text(separator='\n', strip=True)
        elif section_type == '목차':
            book_toc = section.find('p', class_='desc').get_text(separator='\n', strip=True)
    
    if not book_intro:
        return CrawlerStatus.NO_INTRO, {'intro': None, 'toc': book_toc}
    elif not book_toc:
        return CrawlerStatus.NO_TOC, {'intro': book_intro, 'toc': None}
    elif not book_intro and not book_toc:
        return CrawlerStatus.RESULT_EMPTY, None
    else:
        return CrawlerStatus.SUCCESS, {'intro': book_intro, 'toc': book_toc}

def crawl_daum(isbn: str) -> Tuple[CrawlerStatus, Optional[Dict[str, str]]]:
    
    url = f"https://search.daum.net/search?w=book&enc=utf8&q={isbn}"
    
    try:
        status, result = _get_book_link_from_page(url)
    except Exception as e:
        logging.error(f"DAUM: Error fetching book link for ISBN {isbn}: {e}")
        return CrawlerStatus.INTERNAL_ERROR, None
    
    if status == CrawlerStatus.CONN_FAIL:
        return CrawlerStatus.CONN_FAIL, None
    elif status == CrawlerStatus.RESULT_EMPTY:
        return CrawlerStatus.RESULT_EMPTY, None
    elif status == CrawlerStatus.INTERNAL_ERROR:
        return CrawlerStatus.INTERNAL_ERROR, None
    
    try:
        status, book_info = _get_book_info(result)
    except Exception as e:
        logging.error(f"DAUM: Error fetching book intro, toc for ISBN {isbn}: {e}")
        return CrawlerStatus.INTERNAL_ERROR, None
    
    if status == CrawlerStatus.CONN_FAIL:
        return CrawlerStatus.CONN_FAIL, None
    elif status == CrawlerStatus.NO_INTRO:
        return CrawlerStatus.NO_INTRO, {'intro': None, 'toc': book_info['toc']}
    elif status == CrawlerStatus.NO_TOC:
        return CrawlerStatus.NO_TOC, {'intro': book_info['intro'], 'toc': None}
    elif status == CrawlerStatus.RESULT_EMPTY:
        return CrawlerStatus.RESULT_EMPTY, None
    elif status == CrawlerStatus.SUCCESS:
        logging.info(f"DAUM: Successfully fetched book info for ISBN {isbn}")
        return CrawlerStatus.SUCCESS, {'intro': book_info['intro'], 'toc': book_info['toc']}
    

