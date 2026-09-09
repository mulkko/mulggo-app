# [테스트 전용] 사업 구체화 "아이디어 카드 생성" 검증용 엔드포인트.
# 정식 슬롯필링 화면(프론트)이 아직 안 나와서, backend/chatbot/idea_card_generator.py가
# 잘 도는지만 먼저 확인하는 용도. DB에는 아무것도 저장하지 않는다.
#
# 실제 사용 함수는 이거 하나뿐: idea_card_generator.call_llm_for_idea_cards(slots, llm_client)
# (backend/chatbot/real_llm_client.py::call_llm을 llm_client로 주입)
# [2026-09-09] idea_card_generator.py/real_llm_client.py는 원래 backend/idea_llm/에 있었는데,
# CLAUDE.md 폴더 구조상 "사업구체화 챗봇" 코드는 backend/chatbot/에 있어야 해서(chain.py가
# 이미 거기 있음) backend/chatbot/으로 옮김 - 같은 기능의 앞/뒤 반쪽이라 한 폴더에 모음.

from fastapi import APIRouter
from pydantic import BaseModel

from backend.chatbot.idea_card_generator import call_llm_for_idea_cards
from backend.chatbot.real_llm_client import call_llm

router = APIRouter(prefix="/api/test", tags=["test"])


class IdeaCardTestRequest(BaseModel):
    target: str = ""
    differentiator: str = ""
    revenue_model: str = ""
    core_skill: str = ""


@router.post("/idea-cards")
def test_idea_cards(payload: IdeaCardTestRequest) -> dict:
    slots = {
        "target": payload.target,
        "differentiator": payload.differentiator,
        "revenue_model": payload.revenue_model,
        "core_skill": payload.core_skill,
    }

    try:
        result = call_llm_for_idea_cards(slots, llm_client=call_llm)
    except Exception as e:  # noqa: BLE001 - 테스트 엔드포인트라 에러 종류 안 가리고 그대로 보여줌
        return {"success": False, "cards": None, "error": f"아이디어 카드 생성 실패: {e}"}

    return {"success": True, "cards": result.get("cards", []), "error": None}
