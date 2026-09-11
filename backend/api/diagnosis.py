# 사업구체화 진단(슬롯필링) 정식 저장 API.
#
# [2026-09-11] pages/diagnosis/(진단방식선택+구체화진단1~4) 5화면 제출은 지금까지
# backend/api/idea_card_test.py의 POST /api/test/slot-filling(DB 미저장, 테스트
# 전용)을 재사용해왔다. 이 파일은 그걸 대체하는 정식 저장 경로 - DA가 설계한
# idea_refinement_sessions 테이블(팀 ERD 구글시트 "0. ERD 구조" 탭, 테이블 19)에
# 실제로 저장한다.
#
# [컬럼명 함정, 사용자+DA 확인] 실제 DB 컬럼명과 설계문서 한글 라벨이 어긋난다 -
# 설계문서 기준 psst_problem의 한글명은 "PSST-사업 아이템"(문제가 아니라 시드/
# 아이디어), psst_solution의 한글명은 "PSST-문제 정의"(해결책이 아니라 문제/기회
# 정의), psst_strategy가 "사업화 방식"(우리가 흔히 말하는 "solution"에 해당).
# 컬럼명만 보고 매핑하면 틀린다:
#   seed_interest(진단1, 시드)        -> psst_problem
#   problem_to_solve(진단2, 문제정의) -> psst_solution
#   solution_approach(진단3, 사업화방식) -> psst_strategy
#
# ponytail: 확정 전 임시값 2가지, DA 확인되면 교체할 것.
#  - business_operation_type: 설계문서는 has_offline_store(BOOLEAN)인데 실제 DB엔
#    VARCHAR(30)로 다르게 만들어져 있어 정확한 값 종류가 아직 안 정해짐 -
#    hasStore(True/False)를 "오프라인"/"온라인" 문자열로 임시 매핑.
#  - save_consented: NOT NULL인데 화면에 저장동의 체크박스가 아직 없어 일단 false.
#
# resolved_nts_codes/market_analysis/tech_analysis/best_practices_summary는 다른
# 세션이 만들고 있는 업종코드 매칭·분석 기능이 채우는 자리라 여기선 NULL로 둔다.
# idea_refinement_answers/questions/brainstorm_suggestions(단계별 질문-답변 로그)는
# 이번 범위에서 제외 - 우리 5화면과 그 세분화된 step_no/question_label 구조의
# 정확한 매핑을 DA와 확정 전이라, 세션 요약만 우선 저장한다.

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.auth.session import get_current_user_id
from backend.chatbot.idea_card_generator import call_llm_for_idea_cards
from backend.chatbot.real_llm_client import call_llm
from backend.db.connection import get_connection

router = APIRouter(prefix="/api/diagnosis", tags=["diagnosis"])


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


class DiagnosisSubmitRequest(BaseModel):
    origin: str  # "problem" | "opportunity" -> flow_type
    seed_interest: str
    problem_to_solve: str
    solution_approach: str
    has_store: bool
    sido: str
    sigungu: str
    dong: str
    target: str = ""
    differentiator: str = ""
    revenue_model: str = ""
    core_skill: str = ""


@router.post("/submit")
def submit_diagnosis(payload: DiagnosisSubmitRequest, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")
        profile_id = row[0]

        region = " ".join(p for p in [payload.sido, payload.sigungu, payload.dong] if p)
        business_operation_type = "오프라인" if payload.has_store else "온라인"

        cur.execute(
            """
            INSERT INTO idea_refinement_sessions (
                profile_id, status, flow_type, region, business_operation_type,
                psst_problem, psst_solution, psst_strategy,
                save_consented, is_extended_diagnosis, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING session_id
            """,
            (
                profile_id, "완료", payload.origin, region, business_operation_type,
                payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
                False, False,
            ),
        )
        session_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    slots = {
        "target": payload.target,
        "differentiator": payload.differentiator,
        "revenue_model": payload.revenue_model,
        "core_skill": payload.core_skill,
    }
    try:
        card_result = call_llm_for_idea_cards(slots, llm_client=call_llm)
        cards = card_result.get("cards", [])
    except Exception:
        cards = []  # 카드 생성 실패해도 세션 저장은 이미 끝났으니 요청 자체는 성공 처리

    return JSONResponse(content={"success": True, "data": {"session_id": session_id, "cards": cards}})
