# TODO: 관계 탐색 기능 구현 
# TODO: 탐색 우선 순위 결정 알고리즘 생각 -> 이건 개념적 가능성만 보이면 충분할 듯
# TODO: 애초에 실용적이어야 하니까, 도서가 많이 할당되어 있는 주제들을 우선적으로 탐색하는 것도 좋을 듯

import networkx as nx


# To run this code you need to install the following dependencies:
# pip install google-genai

import base64
import os
from google import genai
from google.genai import types


def generate():
    client = genai.Client(
        api_key=os.environ.get("GEMINI_API_KEY"),
    )

    model = "gemini-2.5-flash-lite"
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text="""INSERT_INPUT_HERE"""),
            ],
        ),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config = types.ThinkingConfig(
            thinking_budget=0,
        ),
        response_mime_type="application/json",
        response_schema=genai.types.Schema(
            type = genai.types.Type.OBJECT,
            required = ["candidates"],
            properties = {
                "candidates": genai.types.Schema(
                    type = genai.types.Type.ARRAY,
                    items = genai.types.Schema(
                        type = genai.types.Type.OBJECT,
                        required = ["candidate"],
                        properties = {
                            "candidate": genai.types.Schema(
                                type = genai.types.Type.OBJECT,
                                required = ["is_related", "source_id", "source_label", "target_id", "target_label"],
                                properties = {
                                    "is_related": genai.types.Schema(
                                        type = genai.types.Type.BOOLEAN,
                                    ),
                                    "source_id": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                    "source_label": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                    "target_id": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                    "target_label": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                    "predicate": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                    "description": genai.types.Schema(
                                        type = genai.types.Type.STRING,
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        ),
        system_instruction=[
            types.Part.from_text(text="""
아래는 주제명 표목에서 뽑은 랜덤한 쌍들이다.
1. 너의 역할은 label과 definition 그리고 너의 지식을 종합적으로 활용하여 관계를 파악하는 것이다.
2. 만약 서로 아무 관련이 없거나, 관계가 유의미하지 않게 간접적인 경우에는 is_related에 false를 넣고, predicate랑 description에는 아무것도 적지 않아도 된다.
3. 만약 서로 유의미한 관련이 있다면, predicate에는 source_lable과 target_label이 서술될 수 있는 표현을 넣으면 된다. (e.g. source_label: '증거 재판 주의', target_label: '실체적 진실 주의' 일 때 predicate: '대립하는 개념이다') 그리고 그 판단 이유에 대해 description에 간략하게 한 줄로 이유를 작성하자.
4. predicate에 '관련이 있다'와 같이 구체적이지 않은 표현은 사용하면 안된다. 항상 두 주제 간의 구체적인 관계를 드러내야 한다. 다만, 되도록이면 label에 쓰인 이름은 predicate에 들어가지 않도록 문장을 구성하라."""),
        ],
    )

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        print(chunk.text, end="")

if __name__ == "__main__":
    generate()
