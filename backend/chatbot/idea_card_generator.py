"""
아이디어 카드 생성 기능 — 프롬프트 + 호출 함수

입력: 사업 구체화용 4개 슬롯 (타깃, 차별점, 수익모델, 보유역량)
출력: 3개 고정 축(타깃 관점 / 수익모델 관점 / 보유역량 활용) 기반 아이디어 카드

핵심 제약:
1. 카드는 반드시 아래 3개 축 순서로 생성 (타깃 → 수익모델 → 보유역량)
2. 각 카드의 근거는 입력받은 4개 슬롯 값만 사용. 새로운 사실(숫자, 시장데이터, 경쟁사 등) 생성 금지
3. 근거가 되는 슬롯이 비어있거나 너무 짧으면(10자 미만) 해당 축은 건너뜀 (억지로 3개 채우지 않음)
4. 문체는 전부 제안형 종결어미("~도 있어요", "~해보는 것도 방법이에요") 고정, 명령형 금지
5. 출력은 JSON 강제 (파싱 실패 방지)
"""

import json
import re


# ----------------------------------------------------------------------
# 1. 입력 계약
# ----------------------------------------------------------------------

REQUIRED_SLOTS = ["target", "differentiator", "revenue_model", "core_skill"]

# 슬롯별 최소 글자수 기준 (이보다 짧으면 "근거 부실"로 판단해 해당 축 스킵)
MIN_SLOT_LENGTH = 10


def validate_slots(slots: dict) -> dict:
    """
    입력 슬롯 검증. 어떤 슬롯이 유효한지(길이 기준 통과) 여부를 반환.
    프롬프트에 "어떤 축을 만들 수 있는지" 미리 알려주기 위한 사전 필터링 단계.
    """
    slots = slots or {}
    validity = {}
    for key in REQUIRED_SLOTS:
        value = (slots.get(key) or "").strip()
        validity[key] = len(value) >= MIN_SLOT_LENGTH
    return validity


# ----------------------------------------------------------------------
# 2. 시스템 프롬프트
# ----------------------------------------------------------------------

SYSTEM_PROMPT = """너는 창업 아이디어 브레인스토밍 도우미다.
사용자가 슬롯필링에서 답한 4가지 정보(타깃, 차별점, 수익모델, 보유역량)를 바탕으로,
아래 3개 축 순서대로 참고용 아이디어 카드를 만든다.

[축 순서 — 반드시 이 순서로]
1. 타깃 관점 — 타깃 슬롯 + 보유역량 슬롯을 조합해서, 타깃을 넓히거나 좁힐 수 있는 아이디어
2. 수익모델 관점 — 수익모델 슬롯 + 차별점 슬롯을 조합해서, 다른 수익구조 아이디어
3. 보유역량 활용 — 보유역량 슬롯 + 차별점 슬롯을 조합해서, 역량을 더 살릴 수 있는 아이디어

[반드시 지킬 규칙]
- 각 카드의 근거는 오직 사용자가 답한 4개 슬롯 값에서만 가져온다. 슬롯에 없는 숫자, 시장 데이터,
  경쟁사 이름, 트렌드 등을 새로 만들어내지 않는다.
- 문장은 전부 제안형으로 끝낸다 ("~도 있어요", "~해보는 것도 방법이에요"). "~하세요", "~해야 합니다" 같은
  명령형·단정형은 금지.
- 해당 축에 필요한 슬롯이 비어있거나 내용이 너무 짧아 근거로 삼기 어려우면, 그 축은 건너뛰고 카드를
  만들지 않는다. 억지로 3개를 채우려 하지 않는다.
- 각 카드는 title(10자 내외 짧은 제목)과 description(1문장, 근거를 자연스럽게 포함) 두 필드로 구성한다.
- 이미 사용자가 답한 내용을 그대로 반복하지 말고, 반드시 새로운 조합/방향을 제안한다.

[나쁜 예시 — 이렇게 하면 안 됨]
입력 예: 타깃="노트북 작업하는 20~30대 직장인·프리랜서", 보유역량="바리스타 경력 5년"

나쁜 예 1 (타깃 관점): title="바리스타 타깃확장", description="직장인·프리랜서에 바리스타 경력의
신뢰감을 더해 타깃을 확장해보는 것도 방법이에요."
→ 왜 나쁜가: 타깃(직장인·프리랜서)이 그대로다. "신뢰감을 더한다"는 건 타깃 확장이 아니라 그냥
꾸밈말을 붙인 것뿐이다. 타깃 관점 카드는 원래와 완전히 다른 사람들(예: 학생, 시니어, 육아맘,
스터디 모임 등 연령·상황이 다른 집단)을 제시해야 한다.

나쁜 예 2 (보유역량 활용): title="바리스타 역량 활용"
→ 왜 나쁜가: 제목에 슬롯에 적힌 직업명("바리스타")을 그대로 갖다 썼다. 제목은 그 역량으로
"무엇을 만들 수 있는지" 결과물이나 컨셉으로 표현해야 한다. (좋은 예: "원두 클래스", "홈카페 키트"
처럼 역량을 활용한 결과물 이름으로.)

[좋은 예시]
같은 입력에 대해:
{"axis": "타깃 관점", "title": "원데이 클래스 수강생", "description": "노트북 작업자 외에, 커피를
배우고 싶은 입문자를 위한 원데이 클래스로 타깃을 넓혀볼 수도 있어요."}
{"axis": "보유역량 활용", "title": "홈카페 키트 판매", "description": "매장 운영 노하우를 살려서,
집에서 비슷한 맛을 낼 수 있는 원두·레시피 키트를 함께 판매해보는 것도 방법이에요."}
→ 타깃이 실제로 바뀌었고("입문자"), 제목에 "바리스타"라는 원문 단어 없이 결과물 이름으로 표현됐다.

- 3개 카드는 서로 다른 슬롯 축을 근거로 삼는 것에 그치지 않고, 실제 사업 방향 자체가 서로
  겹치지 않게 한다. 위 좋은 예시처럼 "클래스 운영"과 "상품 판매"처럼 성격이 다른 방향이어야 하며,
  전부 "기존 상품에 부가서비스를 얹는" 같은 동일한 패턴으로 수렴하지 않도록 한다.

[출력 형식]
아래 JSON 형식으로만 출력한다. 다른 설명, 인사말, 마크다운 코드블록 표시(```)는 절대 포함하지 않는다.

{
  "cards": [
    {"axis": "타깃 관점", "title": "...", "description": "..."},
    {"axis": "수익모델 관점", "title": "...", "description": "..."},
    {"axis": "보유역량 활용", "title": "...", "description": "..."}
  ]
}

건너뛴 축이 있으면 그 축은 cards 배열에서 아예 제외한다. 3개 모두 유효하면 3개 전부, 일부만
유효하면 그만큼만 포함한다."""


# ----------------------------------------------------------------------
# 3. 유저 프롬프트(입력 페이로드) 생성
# ----------------------------------------------------------------------

def build_user_payload(slots: dict) -> str:
    """
    슬롯 딕셔너리를 받아 LLM에 보낼 유저 메시지 텍스트를 만든다.
    유효하지 않은 슬롯은 "(답변 없음 또는 부실함)"으로 명시해서,
    모델이 해당 축을 스스로 건너뛰도록 신호를 준다.
    """
    slots = slots or {}
    validity = validate_slots(slots)

    label_map = {
        "target": "타깃",
        "differentiator": "차별점",
        "revenue_model": "수익모델",
        "core_skill": "보유역량",
    }

    lines = []
    for key, label in label_map.items():
        value = (slots.get(key) or "").strip()
        if validity[key]:
            lines.append(f"- {label}: {value}")
        else:
            lines.append(f"- {label}: (답변 없음 또는 부실함 — 이 슬롯이 근거로 필요한 축은 건너뛸 것)")

    return "\n".join(lines)


# ----------------------------------------------------------------------
# 4. LLM 호출 (기존 인프라 재사용 가정 — 특허키워드 변환 함수와 동일 패턴)
# ----------------------------------------------------------------------

def call_llm_for_idea_cards(slots: dict, llm_client=None) -> dict:
    """
    slots: {"target": str, "differentiator": str, "revenue_model": str, "core_skill": str}
    llm_client: 실제 LLM 호출 함수/클라이언트. real_llm_client.py의 call_llm을 주입해서 쓴다.
                (여기서는 인터페이스만 정의. 실제 사용 모델은 real_llm_client.py에서 결정됨)

    반환: {"cards": [...]} 형태의 dict. 파싱 실패 시 {"cards": []} 반환 (안전한 폴백).
    """
    user_payload = build_user_payload(slots)

    # 4개 슬롯이 전부 부실하면 아예 호출하지 않음 (비용 절감 + 빈 응답 방지)
    validity = validate_slots(slots)
    if not any(validity.values()):
        return {"cards": []}

    if llm_client is None:
        raise ValueError("llm_client가 필요합니다. real_llm_client.py의 call_llm을 주입하세요.")

    raw_response = llm_client(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_payload,
        response_format="json",
    )

    return parse_llm_response(raw_response)


def parse_llm_response(raw_response: str) -> dict:
    """
    LLM 응답 문자열을 안전하게 JSON으로 파싱.
    혹시 모델이 코드블록(```json ... ```)을 붙이거나 앞뒤에 텍스트를 붙였을 경우까지 대비.
    """
    if not raw_response:
        return {"cards": []}

    text = raw_response.strip()
    # 코드블록 마커 제거 (모델이 규칙을 어기고 붙였을 경우의 방어 코드)
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"cards": []}

    cards = parsed.get("cards", [])
    if not isinstance(cards, list):
        return {"cards": []}

    # 필드 누락된 카드는 제외 (부분 파싱 방어)
    valid_cards = [
        c for c in cards
        if isinstance(c, dict) and c.get("axis") and c.get("title") and c.get("description")
    ]

    return {"cards": valid_cards}
