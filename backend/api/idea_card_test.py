# [테스트 전용] 사업 구체화 "아이디어 카드 생성" 검증용 엔드포인트.
# 정식 슬롯필링 화면(프론트)이 아직 안 나와서, backend/chatbot/idea_card_generator.py가
# 잘 도는지만 먼저 확인하는 용도. DB에는 아무것도 저장하지 않는다.
#
# 실제 사용 함수는 이거 하나뿐: idea_card_generator.call_llm_for_idea_cards(slots, llm_client)
# (backend/chatbot/real_llm_client.py::call_llm을 llm_client로 주입)
# [2026-09-09] idea_card_generator.py/real_llm_client.py는 원래 backend/idea_llm/에 있었는데,
# CLAUDE.md 폴더 구조상 "사업구체화 챗봇" 코드는 backend/chatbot/에 있어야 해서(chain.py가
# 이미 거기 있음) backend/chatbot/으로 옮김 - 같은 기능의 앞/뒤 반쪽이라 한 폴더에 모음.
#
# [2026-09-09 추가] validate_slots()가 슬롯별 "근거로 쓰기 부실함(10자 미만)" 여부를 이미
# 판단하고 있는데, call_llm_for_idea_cards()의 반환값({"cards": [...]})엔 그 정보가 안
# 담겨서 나간다 - 그래서 카드가 적게(또는 0개) 나와도 어느 슬롯 때문인지 알 방법이 없었음.
# idea_card_generator.py 자체는 손 안 대고(팀에서 완성해서 전달받은 로직), 이미 공개돼있는
# validate_slots()를 여기서 한 번 더 호출해서 weak_slots로 같이 내려준다.
#
# [2026-09-09 추가] 업종코드(KSIC) 연결. Onboarding.tsx 소개 문구대로 "질문에 답한 내용 →
# 업종코드 판정 → 상권/기술창업 분석"으로 이어져야 하는데, 그 다리(업종코드 판정)가 빠져
# 있었음. 새로 안 만들고, 공고문 분류에 이미 쓰는 backend/ml/classifier/decide_industry.py를
# 그대로 재사용 - 4개 슬롯 답변을 합친 텍스트를 그 함수에 넣어서 KSIC 코드를 뽑는다.
# 결과 코드가 있으면 /analysis/tech-startup?ksic_code=... 를 그대로 부르면 다음 단계로
# 이어진다(사용자 위치 정보가 없어도 되는 쪽이라 여기 자동 연결 대상은 tech-startup만;
# /analysis/market은 sido/sigungu/dong이 추가로 필요해서 여기선 연결 안 함).
#
# [2026-09-10 교체] 위 "업종만 매칭"(질문 1개) 경로는 설계 문서
# (`E:\3차프로젝트\슬롯필링_기능_설계_260905.pdf`, `슬롯필링_260909.xlsx`)와 어긋나서
# 폐기하고 /slot-filling으로 교체함:
#   - PDF 5장: 업종코드 매칭엔 seed(슬롯0)+problem_to_solve(슬롯2)+solution_approach(슬롯5)
#     세 개 원문이 필요하다고 명시. 자유서술 1개만으로는 신뢰도가 낮음.
#   - xlsx 각주: 슬롯 0~5(시드/출발점분기/문제정의/사업화방식/매장운영여부/지역규모)가
#     업종코드+분석리포트 "필수", 6~9(타깃/차별점/수익모델/보유역량)는 "선택"
#     (아이디어 브레인스토밍용 — 이건 이미 idea_card_generator.py가 그대로 구현하고 있었음)
# has_store로 상권분석(/analysis/market)/기술창업분석(/analysis/tech-startup) 리포트
# 분기까지 안내하되, 실제 리포트 조회는 프론트에서 별도 호출(여기선 라우팅 힌트만 반환).
# 출발점 분기(문제해결형/기회추구형)는 질문 문구만 바뀌고 데이터 처리엔 영향 없어서
# (PDF 4장) 백엔드로 안 넘어옴 - 프론트에서만 문구 선택에 씀.

from fastapi import APIRouter
from pydantic import BaseModel

from backend.chatbot.idea_card_generator import call_llm_for_idea_cards, validate_slots
from backend.chatbot.real_llm_client import call_llm
from backend.ml.classifier.decide_industry import decide_industry

router = APIRouter(prefix="/api/test", tags=["test"])

SLOT_LABELS = {
    "target": "타깃",
    "differentiator": "차별점",
    "revenue_model": "수익모델",
    "core_skill": "보유역량",
}
SLOT_ORDER = ["target", "differentiator", "revenue_model", "core_skill"]
MIN_DESCRIPTION_LENGTH = 10  # idea_card_generator.MIN_SLOT_LENGTH와 동일 기준으로 맞춤


def _build_ksic_dict(industry: dict | None) -> dict | None:
    if not industry:
        return None
    return {
        "codes": industry.get("확정코드", []),
        "names": industry.get("확정업종명", []),
        "stage": industry.get("확정단계"),
        "confidence": industry.get("ksic_confidence"),
    }


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

    validity = validate_slots(slots)
    weak_slots = [SLOT_LABELS[key] for key, ok in validity.items() if not ok]

    try:
        result = call_llm_for_idea_cards(slots, llm_client=call_llm)
    except Exception as e:  # noqa: BLE001 - 테스트 엔드포인트라 에러 종류 안 가리고 그대로 보여줌
        return {"success": False, "cards": None, "weak_slots": weak_slots, "ksic": None, "error": f"아이디어 카드 생성 실패: {e}"}

    # 4개 슬롯 답변을 합쳐서 업종 판정용 텍스트로 씀 (별도 요약 로직 없이 원문 그대로 - 가장 단순한 형태)
    combined_text = " ".join(slots[k] for k in SLOT_ORDER if slots[k].strip())
    ksic = None
    if combined_text.strip():
        industry = decide_industry(combined_text)
        ksic = _build_ksic_dict(industry)

    return {"success": True, "cards": result.get("cards", []), "weak_slots": weak_slots, "ksic": ksic, "error": None}


class SlotFillingTestRequest(BaseModel):
    # 슬롯 0~5 (xlsx 번호 기준) — 업종코드+분석리포트 필수
    seed_interest: str = ""       # 슬롯 0: 시드(자유입력)
    problem_to_solve: str = ""    # 슬롯 2: 문제/기회정의
    solution_approach: str = ""   # 슬롯 3: 사업화 방식
    has_store: bool | None = None  # 슬롯 4: 매장 운영 여부 (True=예)
    sido: str = ""                # 슬롯 5: 지역·규모
    sigungu: str = ""
    dong: str = ""
    # 슬롯 6~9 — 아이디어 브레인스토밍(선택). 값 없으면 idea_card_generator가 알아서 스킵.
    target: str = ""
    differentiator: str = ""
    revenue_model: str = ""
    core_skill: str = ""


@router.post("/slot-filling")
def test_slot_filling(payload: SlotFillingTestRequest) -> dict:
    """
    슬롯필링_기능_설계_260905.pdf 5장 기준 업종코드 매칭
    (seed+problem_to_solve+solution_approach) + 슬롯필링_260909.xlsx 6~9번
    브레인스토밍(idea_card_generator, 기존 구현 그대로 재사용)을 한 흐름으로 합친 엔드포인트.
    """
    required = {
        "seed_interest": payload.seed_interest,
        "problem_to_solve": payload.problem_to_solve,
        "solution_approach": payload.solution_approach,
    }
    too_short = [name for name, value in required.items() if len(value.strip()) < MIN_DESCRIPTION_LENGTH]
    if too_short:
        return {"success": False, "ksic": None, "report_type": None, "cards": None, "weak_slots": None,
                "error": f"필수 항목이 {MIN_DESCRIPTION_LENGTH}글자 미만이에요: {', '.join(too_short)}"}

    combined_text = " ".join(required.values())
    industry = decide_industry(combined_text)
    ksic = _build_ksic_dict(industry)

    report_type = None
    if payload.has_store is not None:
        report_type = "market" if payload.has_store else "tech_startup"

    brainstorm_slots = {
        "target": payload.target,
        "differentiator": payload.differentiator,
        "revenue_model": payload.revenue_model,
        "core_skill": payload.core_skill,
    }
    weak_slots = [SLOT_LABELS[key] for key, ok in validate_slots(brainstorm_slots).items() if not ok]
    try:
        result = call_llm_for_idea_cards(brainstorm_slots, llm_client=call_llm)
    except Exception as e:  # noqa: BLE001 - 테스트 엔드포인트라 에러 종류 안 가리고 그대로 보여줌
        return {"success": False, "ksic": ksic, "report_type": report_type, "cards": None,
                "weak_slots": weak_slots, "error": f"아이디어 카드 생성 실패: {e}"}

    return {
        "success": True,
        "ksic": ksic,
        "report_type": report_type,
        "region": {"sido": payload.sido, "sigungu": payload.sigungu, "dong": payload.dong},
        "cards": result.get("cards", []),
        "weak_slots": weak_slots,
        "error": None,
    }
