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
# market_analysis/tech_analysis/best_practices_summary는 다른 세션이 만들고 있는
# 분석 리포트 기능이 채우는 자리라 여기선 NULL로 둔다.
# idea_refinement_answers/questions/brainstorm_suggestions(단계별 질문-답변 로그)는
# 이번 범위에서 제외 - 우리 5화면과 그 세분화된 step_no/question_label 구조의
# 정확한 매핑을 DA와 확정 전이라, 세션 요약만 우선 저장한다.
#
# [2026-09-11] resolved_nts_codes/resolved_ksic_codes 연결 - PSST 텍스트로
# backend/ml/industry_code_matching(업종코드 매칭)을 호출해서 채운다. 이어서 그 KSIC코드로
# market_analysis/tech_analysis도 같이 채운다(analysis.py 재사용, HTTP 안 타고 함수 직접
# 호출). 전부 LLM+DB 호출이 겹쳐서 제출 자체가 10~30초+ 걸릴 수 있다(프론트 로딩 표시
# 필수). 셋 다 실패해도 진단 저장 자체는 막지 않는다 - 핵심 흐름(진단 제출)을 부가 기능
# (매칭·분석)이 블로킹하면 안 됨.
# best_practices_summary는 대응하는 기능이 아직 없어 계속 NULL.
# [주의] resolved_ksic_codes 컬럼은 아직 실 DB(Supabase)에 없음 - schema.sql의
# ALTER TABLE을 먼저 실행해야 이 코드가 실제로 동작한다.

import json

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from psycopg2.extras import Json
from pydantic import BaseModel

from backend.api.analysis import get_market_report, get_tech_startup_report
from backend.auth.session import get_current_user_id
from backend.db.connection import get_connection
from backend.ml.industry_code_matching.service import predict as match_industry_code

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


def _resolve_industry_codes(payload: DiagnosisSubmitRequest, region: str) -> tuple[list[str], list[str]]:
    """PSST 텍스트로 업종코드 매칭 호출 - (국세청코드 목록, KSIC코드 목록). 매칭 실패 시 (빈 배열, 빈 배열)."""
    result = match_industry_code(
        payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
        is_offline_store=payload.has_store, region=region,
    )
    if not result["success"]:
        return [], []
    candidates = [result["data"]["primary"], *result["data"]["additional"]]
    nts_codes = [c["code"] for c in candidates]
    ksic_codes = list(dict.fromkeys(code for c in candidates for code in c["ksicCodes"]))
    return nts_codes, ksic_codes


def _resolve_analysis_reports(payload: DiagnosisSubmitRequest, ksic_codes: list[str]) -> tuple[dict | None, dict | None]:
    """확정된 KSIC코드로 상권/기술창업 리포트를 미리 채운다 (analysis.py 함수 직접 호출,
    자기 자신에게 HTTP 요청 안 보냄). 지역 데이터 없음 등으로 실패해도 None으로 두고
    진단 저장은 계속 진행 - 분석 리포트도 매칭과 마찬가지로 부가 기능."""
    ksic_param = ",".join(ksic_codes) if ksic_codes else None

    market = None
    try:
        resp = get_market_report(sido=payload.sido, sigungu=payload.sigungu, dong=payload.dong, ksic_code=ksic_param)
        if resp.status_code == 200:
            market = json.loads(resp.body)["data"]
    except Exception:  # noqa: BLE001 - 상권 데이터 쪽 예외 종류가 다양해 폭넓게 잡고 None으로 둠
        pass

    tech = None
    if ksic_codes:
        try:
            resp = get_tech_startup_report(ksic_code=ksic_param)
            if resp.status_code == 200:
                tech = json.loads(resp.body)["data"]
        except Exception:  # noqa: BLE001
            pass

    return market, tech


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
        resolved_nts_codes, resolved_ksic_codes = _resolve_industry_codes(payload, region)
        market_analysis, tech_analysis = _resolve_analysis_reports(payload, resolved_ksic_codes)

        cur.execute(
            """
            INSERT INTO idea_refinement_sessions (
                profile_id, status, flow_type, region, business_operation_type,
                psst_problem, psst_solution, psst_strategy,
                resolved_nts_codes, resolved_ksic_codes, market_analysis, tech_analysis,
                save_consented, is_extended_diagnosis, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING session_id
            """,
            (
                profile_id, "완료", payload.origin, region, business_operation_type,
                payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
                Json(resolved_nts_codes), Json(resolved_ksic_codes),
                Json(market_analysis) if market_analysis is not None else None,
                Json(tech_analysis) if tech_analysis is not None else None,
                False, False,
            ),
        )
        session_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={
        "success": True,
        "data": {
            "session_id": session_id,
            # 결과 화면에서 관련 공고(/api/matching?ksic=)를 바로 불러올 수 있게 같이 내려준다.
            "resolvedKsicCodes": resolved_ksic_codes,
        },
    })
