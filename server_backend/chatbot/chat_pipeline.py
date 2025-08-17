from core.config import GEMINI_API_KEY, GEMINI_MODEL, MAX_QUERY_LENGTH, MODEL_SERVER_URL, NETWORK_SERVER_URL
from schemas.chat import UserNeeds,UserNeedsAnalysis
from core.utils import truncate_string
import httpx
from typing import List
from google import genai
import google.generativeai as genai
from google.genai import types

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

user_needs_analyze_config = types.GenerateContentConfig(
    response_mime_type="application/json",
    system_instruction = (
        "너는 이용자의 입력을 받아 정보 요구를 추출하는 일을 한다.\n"
        "일은 다음의 순서에 따라 처리하자.\n"
        "1. 우선 입력에 명시적, 암시적으로 드러나는 정보요구가 있으면 needs_exist가 true, 없으면 false이다.\n"
        "2. 만약 needs_exist가 False이면, 여기서 일을 종료하면 됨. (즉 needs 는 비워둬야 함)\n"
        "3. 만약 needs_exist가 true이면, 사용자의 입력에서 알 수 있는 모든 정보 요구를 파악하자. 정보요구는 여러개 있을 수 있음.\n"
        "4. 파악된 정보요구들을 RDF 트리플(subject, predicate, object)로 나타내자.\n"
        "5. 그 정보요구를 해결하기 위해 필요한 내용이 뭔지를 생각해두자.\n" 
        "6. 필요한 내용에 관련된 '책'이나 '주제명 표목'을 찾는 데에 도움이 될만한 키워드(단어 또는 구)를 최소한 3개 이상 keywords에 나타내자."
    ),
    response_schema=genai.types.Schema(
        type = genai.types.Type.OBJECT,
        required = ["needs_exist"],
        properties = {
            "needs_exist": genai.types.Schema(
                type = genai.types.Type.BOOLEAN,
            ),
            "needs": genai.types.Schema(
                type = genai.types.Type.ARRAY,
                items = genai.types.Schema(
                    type = genai.types.Type.OBJECT,
                    required = ["subject", "predicate", "object", "keywords"],
                    properties = {
                        "subject": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                        "predicate": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                        "object": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                        "keywords": genai.types.Schema(
                            type = genai.types.Type.STRING,
                        ),
                    },
                ),
            ),
        },
    ),
)


async def analyze_user_needs(user_input: str) -> UserNeedsAnalysis:

    contents = [user_input]
    try:
        response = await model.generate_content_async(
            model=GEMINI_MODEL,
            contents=contents,
            config=user_needs_analyze_config
        )
        
        response_data = response.text
        response_json = response_data.json()
        
        needs_exist = response_json.get("needs_exist", False)
        needs = response_json.get("needs", [])
        if not needs_exist:
            return UserNeedsAnalysis(
                needs_exist=False,
                needs=[]
            )
        else:
            return UserNeedsAnalysis(
                needs_exist=True,
                needs=[
                    UserNeeds(
                        subject_=need.get("subject", ""),
                        predicate_=need.get("predicate", ""),
                        object_=need.get("object", ""),
                        keywords=need.get("keywords", [])
                    ) for need in needs
                ]
            )
    except Exception as e:
        raise RuntimeError(f"Failed to generate content: {e}")

async def find_book_candidates_by_needs(keywords_str : str) -> List[str]:
    http_client = httpx.AsyncClient(timeout=10.0)

    query = truncate_string(keywords_str, MAX_QUERY_LENGTH)
    
    response = await http_client.post(
        f"{MODEL_SERVER_URL}/search/books",
        json={"query": query, "limit": 10}
    )
    response.raise_for_status()
    search_data = response.json()
    retrieved_isbns = search_data.get("retrieved_isbns", [])
    
    with 

async def find_subject_candidates_by_needs(subject_:str, object_:str) -> List[str]:
    http_client = httpx.AsyncClient(timeout=10.0)

    # Get subject-related subjects
    response = await http_client.post(
        f"{MODEL_SERVER_URL}/search/subjects",
        json={"query": subject_, "limit": 10}
    )
    response.raise_for_status()
    search_data = response.json()
    subject_retrieved_node_ids = search_data.get("retrieved_node_ids", [])
    
    response = await http_client.post(
        f"{NETWORK_SERVER_URL}/nodes/info",
        json={"node_ids": subject_retrieved_node_ids}
    )
    response.raise_for_status()
    subject_nodes = response.json().get("nodes", [])

    # Get object-related subjects
    response = await http_client.post(
        f"{MODEL_SERVER_URL}/search/subjects",
        json={"query": object_, "limit": 10}
    )
    response.raise_for_status()
    search_data = response.json()
    object_retrieved_node_ids = search_data.get("retrieved_node_ids", [])

    response = await http_client.post(
        f"{NETWORK_SERVER_URL}/nodes/info",
        json={"node_ids": object_retrieved_node_ids}
    )
    response.raise_for_status()
    object_nodes = response.json().get("nodes", [])

if __name__ == "__main__":
    user_input = "나는 서울의 역사에 대해 알고 싶어."
    result = analyze_user_needs(user_input)
    print(result)