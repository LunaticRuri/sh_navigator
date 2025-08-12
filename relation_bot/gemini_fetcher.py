import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Dict
import json
from config import GEMINI_API_KEY, GEMINI_MODEL

load_dotenv()

class RelationCandidate(BaseModel):
    source_id: str
    source_label: str
    source_definition: str
    target_id: str
    target_label: str
    target_definition: str

class PredictedRelation(BaseModel):
    is_related: bool
    source_id: str
    source_label: str
    target_id: str
    target_label: str
    predicate: str = ""
    description: str = ""


class GeminiFetcher:
    """Class to interact with Gemini API for generating relations."""

    system_instruction_text = """
아래는 주제명 표목에서 뽑은 랜덤한 쌍들이다.
1. 너의 역할은 label과 definition 그리고 너의 지식을 종합적으로 활용하여 관계를 파악하는 것이다.
2. 만약 서로 아무 관련이 없거나, 관계가 유의미하지 않게 간접적인 경우에는 is_related에 false를 넣고, predicate랑 description에는 아무것도 적지 않아도 된다.
3. 만약 서로 유의미한 관련이 있다면, predicate에는 source_lable과 target_label이 서술될 수 있는 표현을 넣으면 된다. (e.g. source_label: '증거 재판 주의', target_label: '실체적 진실 주의' 일 때 predicate: '대립하는 개념이다') 그리고 그 판단 이유에 대해 description에 간략하게 한 줄로 이유를 작성하자.
4. predicate에 '관련이 있다'와 같이 구체적이지 않은 표현은 사용하면 안된다. 항상 두 주제 간의 구체적인 관계를 드러내야 한다. 다만, 되도록이면 label에 쓰인 이름은 predicate에 들어가지 않도록 문장을 구성하라.
"""

    generate_content_config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type=genai.types.Type.OBJECT,
            required=["candidates"],
            properties={
                "candidates": genai.types.Schema(
                    type=genai.types.Type.ARRAY,
                    items=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=["candidate"],
                        properties={
                            "candidate": genai.types.Schema(
                                type=genai.types.Type.OBJECT,
                                required=[
                                    "is_related",
                                    "source_id",
                                    "source_label",
                                    "target_id",
                                    "target_label",
                                ],
                                properties={
                                    "is_related": genai.types.Schema(
                                        type=genai.types.Type.BOOLEAN,
                                    ),
                                    "source_id": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "source_label": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "target_id": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "target_label": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "predicate": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                    "description": genai.types.Schema(
                                        type=genai.types.Type.STRING,
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        ),
        system_instruction=system_instruction_text,
    )

    def __init__(self):
        """Initialize the Gemini client with API key."""
        self.client = genai.Client(
            api_key=GEMINI_API_KEY,
            model=GEMINI_MODEL
        )

    
    def _yield_batch_contents(self, candidates: List[RelationCandidate], batch_size: int = 10):
        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i + batch_size]
            yield [
                {
                    "source_id": c.source_id,
                    "source_label": c.source_label,
                    "source_definition": c.source_definition,
                    "target_id": c.target_id,
                    "target_label": c.target_label,
                    "target_definition": c.target_definition,
                }
                for c in batch
            ]
    
    
    def _get_response(self, contents: str):
        response = self.client.models.generate_content(
            contents=contents,
            config=GeminiFetcher.generate_content_config
        )
        return response.text
    
    def generate_relations(self, candidates: List[RelationCandidate]) -> List[PredictedRelation]:
        
        results = []

        for batch_contents in self._yield_batch_contents(candidates, batch_size=10):
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=str(batch_contents))],
                ),
            ]
            response_text = self._get_response(contents)
            try:
                response_json = json.loads(response_text)
                response_json = response_json.get("candidates", [])
                for item in response_json:
                    candidate = item.get("candidate", {})
                    if candidate:
                        results.append(PredictedRelation(**candidate))
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON response: {e}")
                print(f"Response text: {response_text}")
                continue
            except Exception as e:
                print(f"Unexpected error: {e}")
                continue
            
            return results
        
    def show_example_output(self):
        """Show example output for testing."""

        example_candidates = [
            RelationCandidate(
                source_id="nlk:KSH2005014167",
                source_label="파이썬[python]",
                source_definition="파이썬은 1991년에 Guido van Rossum에 의해 개발된 고급 프로그래밍 언어입니다. 이 언어는 코드를 간결하게 작성할 수 있도록 설계되었으며, 읽기 쉽고 배우기 쉬운 문법을 가지고 있습니다. 객체 지향 언어로서 다양한 프로그래밍 패러다임을 지원하며, 웹 개발, 데이터 분석, 인공지능 등 다양한 분야에서 널리 사용됩니다. 웹 크롤링, 텐서플로 등의 기술과 함께 사용되어 강력한 기능을 제공합니다. 방대한 라이브러리 생태계를 가지고 있어 개발 생산성을 높이는 데 기여합니다.",
                target_id="nlk:KSH1998000479",
                target_label="통계 분석[統計分析]",
                target_definition="데이터를 수집, 정리, 요약, 분석하여 유용한 정보를 추출하고 결론을 도출하는 과정입니다. 기술 통계와 추론 통계로 나눌 수 있으며, 다양한 통계적 방법론을 활용하여 데이터의 특성을 파악하고 예측 모델을 구축합니다. 과학, 공학, 사회과학, 경제학 등 다양한 분야에서 의사 결정을 지원하는 데 활용됩니다."
            ),
            RelationCandidate(
                source_id="nlk:KSH1997000004",
                source_label="다운사이징[downsizing]",
                source_definition="기업의 규모를 축소하여 효율성을 높이는 경영 전략으로, 인원 감축, 사업 부문 축소, 자산 매각 등을 포함할 수 있습니다. 이는 기업이 경쟁력을 강화하고 변화하는 시장 환경에 적응하기 위해 사용하는 방법입니다. 다운사이징은 단기적으로 비용 절감 효과를 가져올 수 있지만, 장기적으로는 직원들의 사기 저하나 생산성 감소를 초래할 수도 있습니다. 성공적인 다운사이징을 위해서는 명확한 목표 설정과 함께 직원들과의 충분한 소통이 중요합니다. 다운사이징은 감량 경영, 구조 조정, 리엔지니어링과 관련이 깊습니다.",
                target_id="nlk:KSH1998000005",
                target_label="근거리 통신망[近距離通信網]",
                target_definition="Local Area Network(LAN)의 약자로, 집, 사무실, 학교 등과 같이 한정된 지리적 영역 내의 컴퓨터와 주변 장치들을 연결하여 정보를 교환하고 자원을 공유할 수 있도록 구축된 네트워크 시스템입니다. 일반적으로 하나의 라우터를 통해 중앙 집중식 인터넷 연결을 공유하며, 효율적인 데이터 전달을 위해 네트워크 스위치를 추가로 사용할 수 있습니다. 유선 및 Wi-Fi 연결 장치를 모두 포함하는 개념으로, 사용자의 컴퓨터, 휴대폰, 태블릿 등이 LAN을 구성합니다. 광역 통신망(WAN)과 대조적으로, 제한된 지역을 대상으로 고속 통신이 가능하며 패킷 전달의 지연 시간이 최소화됩니다. IEEE 802 워킹 그룹에서 LAN 관련 표준안을 제시하여 다양한 장비 간 호환성을 보장합니다."
            )
        ]
        
        fetcher = GeminiFetcher()
        results = fetcher.generate_relations(example_candidates)

        print("Example Output:\n")
        for result in results:
            print(result)
            print('\n')

if __name__ == "__main__":
    fetcher = GeminiFetcher()
    fetcher.show_example_output()