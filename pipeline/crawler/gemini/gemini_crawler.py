from dotenv import load_dotenv
import os
import re
import time
import logging
from typing import List, Dict, Optional
from google import genai
from google.generativeai import GenerateContentConfig
from crawler.crawler_status import CrawlerStatus
from config import GEMINI_API_KEY, GEMINI_MODEL


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s")


def _generate_summaries_query(books: List[Dict[str, str]]) -> str:
    """
    Generate a formatted query string for a list of books.
    Each book should be a dict with keys: ISBN, title, intro, toc.
    """
    lines = []
    for idx, book in enumerate(books, 1):
        if not isinstance(book, dict) or not all(k in book for k in ("isbn", "title")):
            raise ValueError("Each book must be a dictionary with keys: isbn, title, intro, toc")
        lines.append(
            f"{idx}. ISBN: {book['isbn']} | 제목: {book['title']}"
        )
    return "\n".join(lines).strip()

def _extract_summaries(response_text: str) -> List[Dict[str, str]]:
    summaries = []
    # Regex pattern to match the expected format
    pattern = r"\*\*(?:\d{13}\.\s)?(.*?)\*\*:\s*(.*)"
    for raw_line in response_text.strip().split('\n'):
        matches = re.findall(pattern, raw_line, re.DOTALL)
        for isbn, summary in matches:
            summaries.append({
                "isbn": isbn.strip(),
                "summary": summary.strip()
            })
    return summaries

def _request_gemini_response(contents: str, system_instruction: str) -> Optional[genai.types.GenerateContentResponse]:
    """
    Request content generation from the Gemini API.
    Arguments:
    - contents: The content to be processed by the Gemini API.
    - system_instruction: The system instruction to guide the content generation.
    Returns:
    - The response from the Gemini API, or None if an error occurs.
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        return client.models.generate_content(
            model=GEMINI_MODEL,
            contents=contents,
            config=GenerateContentConfig(
                system_instruction=system_instruction,
                response_modalities=["TEXT"],
                candidate_count=1,
                temperature=1,
            )
        )
    except Exception as e:
        logging.error(f"Error requesting Gemini API: {e}")
        return None

def _fill_blank_summaries(books: List[Dict[str, str]], query: str):
    # 'books' is a list of dicts with keys: id, isbn, title
    instruction = (
        "너는 책의 내용을 인터넷(알라딘, 교보문고, 아마존 등)에서 검색해 요약하는 전문가야.\n"
        "1. 검색을 하기 위해 ISBN과 제목이 주어진다.\n"
        "2. 주어진 ISBN과 제목을 통해 찾을 수 없는 책이거나, 정보가 부족하다면, '책의 요약' 부분에 '**모름**'으로 표시해.\n"
        "3. 각 책의 특징이 잘 드러나도록 내용을 요약해.\n"
        "4. 각 책은 서로 관련이 없으니 독립적으로 설명해줘.\n"
        "5. 너는 검색한 책의 내용을 바탕으로 4줄 이상 6줄 이하의 분량으로 요약을 작성해야 해.\n"
        "6. 내용과 상관 없는 인삿말 같은 건 쓰지 말고, 바로 '책의 요약'을 시작해줘.\n"
        "<출력 형식 조건>\n"
        "1. **ISBN**: '책의 요약'\n"
        "2. '책의 요약' 부분 안에선 줄바꾸지 말기.\n"
        "<출력 예시>\n"
        "1. **9791169213516**: LLM을 쓰는 것을 넘어, 이해하고 구현하는 것까지 나아가고 싶은 이를 위한 실전 가이드다. 직관적인 시각 자료와 예제를 제공해 '왜 이런 구조가 필요한지' 이해하고 실용적인 도구와 개념을 익힐 수 있도록 구성했다. 사전 훈련된 대규모 언어 모델을 사용하는 방법과 시맨틱 검색 시스템을 만드는 방법, 텍스트 분류, 검색, 클러스터링을 위해 사전 훈련된 모델과 각종 라이브러리를 사용하는 방법을 배울 수 있다.\n"
        "2. **9788957365793**: 자본주의의 작동 원리와 숨겨진 진실을 쉽게 풀어낸 책이다. 이 책은 자본주의가 어떻게 빚을 통해 발전하는지, 부분지급준비율이 돈을 어떻게 불리는지 등 일반인이 이해하기 어려운 경제 개념을 설명한다. 또한 소비 마케팅의 비밀, 금융 상품의 작동 방식, 그리고 위기 시대의 자본주의를 극복할 방안에 대해서도 다룬다. 서브프라임 모기지 사태나 저축은행 사태와 같은 경제 현상들을 통해 자본주의의 이면과 위험성을 경고하며, 독자들에게 자본주의 사회에서 현명하게 살아가는 방법을 모색할 기회를 제공한다. 이 책은 경제학 입문자나 자본주의에 대해 더 깊이 알고 싶은 사람들에게 추천되는 책이다.\n"
        "3. **9791140714490**: 돈과 경제에 관련된 영어 표현을 상세하게 다루는 책이다. 이 책은 300개의 표제어에 대한 관용구와 연어(collocation)를 통해 돈에 대한 모든 것을 탐구한다. 책의 내용은 지갑(Wallet)에서부터 개인(Individual), 가구(Household), 이웃(Neighborhood), 도시(City), 국가(Country), 세계(Globe)에 이르기까지 7개의 반경으로 확장되며, 이를 통해 돈과 경제에 대한 다양한 표현을 현대적인 맥락에서 살펴본다. 이를 통해 독자들이 돈에 대해 더욱 유연하고 풍부하게 표현하는 방법을 배울 수 있도록 돕는다. 이 책은 돈과 경제에 관한 영어 표현과 그 문화적 배경을 깊이 있게 이해하고자 하는 이들에게 유용한 자료가 될 것이다.\n"
        "4. **9788936434120**: 1980년 5월 18일 광주민주화운동의 비극을 배경으로 한 작품이다.이 소설은 당시의 참상과 그 이후 남겨진 사람들의 아픔을 깊이 있게 그려내고 있다. 작가는 철저한 고증과 취재를 바탕으로, 특유의 정교하고 밀도 있는 문체로 역사의 아픔을 섬세하게 담아냈다. 『소년이 온다』는 단순히 과거의 비극을 재현하는 데 그치지 않고, 인간의 존엄성과 폭력의 본질에 대한 근원적인 질문을 던진다. 또한, 우리가 그 아픈 역사를 어떻게 기억하고 애도해야 하는지에 대한 깊은 울림을 전한다.\n"
    )

    response = _request_gemini_response(
        contents=query,
        system_instruction=instruction
    )
    
    if not response or not getattr(response, "text", None):
        # If the response is empty or None, log an error and skip this chunk
        logging.error(f"Empty response from Gemini API for chunk. Contents: {query}")
        return False

    results = _extract_summaries(response.text)

    # Check if the number of results matches the number of books
    if len(books) != len(results):
        # If there's a mismatch, log an error and skip it
        logging.error(f"Length mismatch for books. Expected {len(books)} isbns but got {len(results)} results. Contents: {query}")
        return False
    
    for book, res in zip(books, results):
        if book['isbn'] != res['isbn']:
            # If the ISBNs do not match, log an error and skip this chunk
            logging.error(f"ISBN mismatch for book {book['isbn']} and result {res['isbn']}. Contents: {query}")
            return False
    
    # books is a list of dicts with keys: id, isbn, title, summary
    for book, res in zip(books, results):
        book.update({'summary': res['summary']})
    for book in books:
        logging.info(f"Book {book['isbn']} summary: {book['summary']}")
        summary = book.get('summary', '')
        if '**모름**' in summary:
            book['summary'] = None
    
    return books
        

def crawl_gemini(books: List[Dict[str, str]]):
    client = genai.Client(api_key=GEMINI_API_KEY)
    logging.info("Starting Gemini crawler...")
    query = _generate_summaries_query(books)
    
    max_retries = 3
    for attempt in range(max_retries):
        result = _fill_blank_summaries(books, query)
        if result:
            logging.info("Successfully filled summaries using Gemini API.")
            return CrawlerStatus.SUCCESS, result
        else:
            logging.warning(f"Attempt {attempt + 1} failed. Retrying...")
            time.sleep(2 ** attempt)
    
    logging.error("Failed to fill summaries after multiple attempts.")
    return CrawlerStatus.INTERNAL_ERROR, None

