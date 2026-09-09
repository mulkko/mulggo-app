"""
실제 AI(OpenAI)를 호출하는 함수. 현재 기본 모델은 gpt-5-mini.

=====================================================================
[TA 전달용] 이 파일 + idea_card_generator.py 두 개를 그대로 백엔드 코드에
포함시키면 됩니다. TA가 실제로 호출할 함수는 딱 하나입니다.

    from idea_card_generator import call_llm_for_idea_cards
    from real_llm_client import call_llm

    result = call_llm_for_idea_cards(
        {
            "target": "<사용자가 입력한 타깃 슬롯 값>",
            "differentiator": "<차별점 슬롯 값>",
            "revenue_model": "<수익모델 슬롯 값>",
            "core_skill": "<보유역량 슬롯 값>",
        },
        llm_client=call_llm,
    )
    # result 예: {"cards": [{"axis": "...", "title": "...", "description": "..."}, ...]}
    # 슬롯이 부실하면 cards가 2개 이하로 올 수 있음 (정상 동작, 에러 아님)

통합 전 반드시 확인할 것: get_client() 함수의 API 키 부분 — 지금은 로컬 테스트용
getpass 방식이라, 서버에 OPENAI_API_KEY 환경변수만 설정해주면 됩니다.
=====================================================================
"""

import os
import json
from openai import OpenAI


def get_client():
    """
    [TA 통합 시 반드시 확인] 지금은 DA가 주피터에서 손으로 테스트하기 편하게
    "환경변수에 없으면 화면에서 직접 입력받기(getpass)" 방식으로 돼 있습니다.

    실제 서비스(앱)에 넣을 때는 사람이 매번 키를 타이핑할 수 없으니,
    getpass 부분은 쓰지 말고 아래 중 팀이 쓰는 방식으로 바꿔서 API 키를 가져와야 합니다.
      예) 서버 환경변수(.env 파일 등)에서만 읽어오기
      예) 팀 시크릿 관리 도구(AWS Secrets Manager 등)에서 읽어오기
    환경변수 자체는 이미 지원하고 있으니(OPENAI_API_KEY), 서버에 그 환경변수만
    설정해주면 getpass 쪽은 아예 호출되지 않습니다.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        from getpass import getpass
        api_key = getpass("OpenAI API 키를 입력하세요 (화면에 안 보입니다): ")
    return OpenAI(api_key=api_key)


def call_llm(system_prompt: str, user_prompt: str, response_format: str = "json", model: str = "gpt-5-mini") -> str:
    """
    idea_card_generator.call_llm_for_idea_cards()의 llm_client 인자로 그대로 넣어서 쓰는 함수.

    system_prompt: 아이디어 카드 생성 규칙이 담긴 시스템 프롬프트 (idea_card_generator.SYSTEM_PROMPT)
    user_prompt: 슬롯 답변 내용 (idea_card_generator.build_user_payload 결과)
    response_format: "json"이면 JSON 강제 출력 모드로 호출
    model: 호출할 모델명. 기본값은 gpt-5-mini (gpt-5-nano보다 지시 이해력이 좋음).
           비용을 낮추고 싶으면 "gpt-5-nano"로 다시 바꿔서 테스트 가능.

    반환값: 모델이 생성한 원문 텍스트 (JSON 문자열이어야 정상)
    """
    client = get_client()

    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content
