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
#   core_skill(진단10, 보유역량)      -> psst_team
#
# ponytail: 확정 전 임시값 2가지, DA 확인되면 교체할 것.
#  - business_operation_type: 설계문서는 has_offline_store(BOOLEAN)인데 실제 DB엔
#    VARCHAR(30)로 다르게 만들어져 있어 정확한 값 종류가 아직 안 정해짐 -
#    hasStore(True/False)를 "오프라인"/"온라인" 문자열로 임시 매핑.
#  - save_consented: NOT NULL인데 화면에 저장동의 체크박스가 아직 없어 일단 false.
#
# idea_refinement_answers/questions/brainstorm_suggestions(단계별 질문-답변 로그)는
# 이번 범위에서 제외 - 우리 5화면과 그 세분화된 step_no/question_label 구조의
# 정확한 매핑을 DA와 확정 전이라, 세션 요약만 우선 저장한다.
#
# [2026-09-11] 팀 설계문서("물꼬_사업구체화_지표결합_설계안.docx") 기준으로 구조를
# 다시 맞춤 - 핵심 결론은 "카드 인용(장식)"이 아니라 "질문 앵커(재배치)": 실측
# 데이터를 별도 리포트 화면으로 보여주고 끝내는 게 아니라, 선택 질문(Q7·Q8) 텍스트
# 바로 위에 데이터 기반 문장을 앵커로 붙여서 사용자가 그 데이터를 보고 답을
# 만들게 한다. 그래서:
#   - 별도의 "업종코드 확인" 화면은 두지 않는다 (문서가 명시적으로 배제하는 패턴 -
#     "카드 인용"처럼 읽고 끝나는 화면은 답을 바꿀 계기가 약하다고 지적함).
#   - 매칭·리포트 생성 시점은 문서의 "[1] 6문항 입력 → [2] 업종코드 매칭 →
#     [3] 리포트 생성" 순서를 따라 "6번째(마지막 필수) 질문 제출 시점" = 지역
#     제출 시점 하나로 통일한다(예전엔 5번 매장형태 제출 시점에 세션을 만들고
#     지역은 별도 PATCH로 나중에 채웠는데, 문서 기준과 안 맞아 합쳤다).
#   - 매장형태(오프라인=카페형/그 외=기술창업형)로 자동 분기해서, 카페형은
#     상권분석(생활인구지수·동일업종밀집도) 기반 앵커를, 기술창업형은
#     기술창업분석(유사벤처인증기업·특허출원추이) 기반 앵커를 Q7(타깃)·Q8(차별점)에
#     각각 내려준다. Q9(수익모델)는 우수사례 집계가 필요한데 그 매칭 기능 자체가
#     아직 없어(§4.4, best_practices_summary 계속 NULL) 문서의 안전장치 원칙대로
#     그냥 폴백(하드코딩 문구)한다. Q10(보유역량)도 문서가 "자연스러운 지표 없음"
#     이라 명시한 대로 폴백.
#   - 전부 LLM+DB+외부API(KIPRIS) 호출이 겹쳐서 지역 제출 자체가 오래 걸릴 수 있다
#     (프론트 로딩 표시 필수). 실패해도 그 부분만 None/폴백 - 핵심 흐름(진단 진행)을
#     부가 기능이 블로킹하면 안 됨.
#
# [2026-09-12] 지역 제출(POST /start) 응답을 "업종코드 매칭"과 "상권/기술창업 분석
# 생성" 두 단계로 분리(사용자 확인 - 실측: 업종코드 매칭만 11~13초, 리포트 생성이
# 추가로 7~9초 더 걸려 합치면 18~22초. 사용자가 중간에 이탈할 위험 때문에, 매칭이
# 끝나는 대로 바로 다음 화면(질응답 정리)으로 보내고 리포트는 백그라운드로 계속
# 돌린다):
#   POST /start           - 업종코드 매칭만 하고 즉시 응답. 세션도 이 시점에 만들되
#                            market_analysis/tech_analysis는 아직 NULL - 응답 직후
#                            백그라운드 태스크(_run_report_in_background)로 리포트
#                            생성을 넘긴다.
#   GET /{id}/report      - 분석 리포트 화면이 폴링하는 API. 아직 안 끝났으면
#                            {"ready": false}만 반환, 끝났으면 marketAnalysis/
#                            techAnalysis + Q7·Q8 앵커까지 같이 반환.
# _report_status는 진행 상태(pending/done/error)를 세션별로 들고 있는 인메모리
# 캐시 - ponytail: 서버 재시작하면 "pending" 기록이 날아간다(단일 프로세스 규모엔
# 충분, 여러 워커/재시작 안전성이 필요해지면 DB 컬럼이나 Redis로 승격).

import json

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from psycopg2.extras import Json
from pydantic import BaseModel

from backend.analysis_report.tech_startup.patent_forecast import get_patent_trend_with_forecast
from backend.api.analysis import PATENT_FORECAST_YEARS, get_market_report, get_tech_startup_report
from backend.auth.session import get_current_user_id
from backend.chatbot.idea_card_generator import call_llm_for_idea_cards
from backend.chatbot.real_llm_client import call_llm
from backend.db.connection import get_connection
from backend.ml.industry_code_matching.service import predict as match_industry_code

router = APIRouter(prefix="/api/diagnosis", tags=["diagnosis"])


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


def _get_profile_id(cur, user_id: int) -> int | None:
    cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
    row = cur.fetchone()
    return row[0] if row else None


def _resolve_industry_codes(
    seed: str, problem: str, solution: str, has_store: bool, region: str
) -> tuple[list[str], list[str], dict | None]:
    """PSST 텍스트로 업종코드 매칭 호출 - (국세청코드 목록, KSIC코드 목록, 판정 요약).
    매칭 실패 시 (빈 배열, 빈 배열, None)."""
    result = match_industry_code(seed, problem, solution, is_offline_store=has_store, region=region)
    if not result["success"]:
        return [], [], None
    data = result["data"]
    candidates = [data["primary"], *data["additional"]]
    nts_codes = [c["code"] for c in candidates]
    ksic_codes = list(dict.fromkeys(code for c in candidates for code in c["ksicCodes"]))
    match_summary = {
        "state": data["state"],
        "name": data["primary"]["name"],
        "confidence": data["primary"].get("confidence", ""),
        "question": data.get("question", ""),
    }
    return nts_codes, ksic_codes, match_summary


def _resolve_market_report(sido: str, sigungu: str, dong: str, ksic_codes: list[str]) -> dict | None:
    """상권분석(카페형 Q7·Q8 앵커의 데이터 소스). 실패해도 None - 부가 기능이라 진단
    진행을 막지 않는다."""
    ksic_param = ",".join(ksic_codes) if ksic_codes else None
    try:
        resp = get_market_report(sido=sido, sigungu=sigungu, dong=dong, ksic_code=ksic_param)
        if resp.status_code == 200:
            return json.loads(resp.body)["data"]
    except Exception:  # noqa: BLE001 - 상권 데이터 쪽 예외 종류가 다양해 폭넓게 잡고 None으로 둠
        pass
    return None


def _format_market_target_anchor(market_analysis: dict | None) -> str | None:
    """카페형 Q7(타깃) 앵커 - "이 지역 생활인구지수는 {footfall}, 상주인구는
    {resident_population}명이에요." (설계문서 §3 예시 문구 그대로). footfall/resident는
    단순 숫자가 아니라 population.py가 반환하는 dict라 score/resident_population 키를
    각각 뽑아 쓴다. footfall.data_type("생활인구"/"유동인구")로 실제 지표명이 갈린다 -
    population.compute_footfall_score() 참고, 생활인구는 서울만 있고 그 외 지역은
    유동인구로 대체된다(원본 데이터 자체가 그렇게 구성됨) - "생활인구지수"로 고정
    표기하면 서울 아닌 지역에서 틀린 이름이 나간다."""
    if not market_analysis:
        return None
    footfall = market_analysis.get("footfall") or {}
    resident = market_analysis.get("resident_population") or {}
    data_type = footfall.get("data_type")
    score = footfall.get("score")
    population = resident.get("resident_population")
    if data_type is None or score is None or population is None:
        return None
    return f"이 지역 {data_type}지수는 {score}, 상주인구는 {population}명이에요."


def _format_market_differentiator_anchor(market_analysis: dict | None) -> str | None:
    """카페형 Q8(차별점) 앵커 - "반경 500m 안에 동일업종이 {N}곳 있고, 특히 한 구역엔
    {최댓값}곳이 몰려 있어요." density는 resolved_ksic_codes가 있어야 채워진다(density.py
    참고) - 없으면 None."""
    if not market_analysis:
        return None
    density = market_analysis.get("density")
    if not density:
        return None
    same_count = density.get("same_industry_count")
    cells = (density.get("grid") or {}).get("cells") or []
    if same_count is None or not cells:
        return None
    max_count = max(c.get("count", 0) for c in cells)
    return f"반경 500m 안에 동일업종이 {same_count}곳 있고, 특히 한 구역엔 {max_count}곳이 몰려 있어요."


def _resolve_tech_report(ksic_codes: list[str]) -> dict | None:
    """기술창업형 Q7(타깃) 앵커의 데이터 소스(유사 벤처인증기업 통계). 실패해도 None."""
    if not ksic_codes:
        return None
    try:
        resp = get_tech_startup_report(ksic_code=",".join(ksic_codes))
        if resp.status_code == 200:
            return json.loads(resp.body)["data"]
    except Exception:  # noqa: BLE001
        pass
    return None


def _format_venture_anchor(tech_analysis: dict | None) -> str | None:
    """기술창업형 Q7(타깃) 앵커 - "유사 벤처인증기업 N개 중 X형이 Y%로 가장 많아요."
    tech_analysis.type_distribution(venture.compute_venture_type_distribution 결과, 컬럼:
    인증유형/건수/비율(%))에서 가장 비중 큰 유형을 뽑는다."""
    if not tech_analysis:
        return None
    similar_count = tech_analysis.get("similar_count", 0)
    distribution = tech_analysis.get("type_distribution") or []
    if not similar_count or not distribution:
        return None
    top = max(distribution, key=lambda d: d.get("건수", 0))
    return f"유사 벤처인증기업 {similar_count}개 중 {top.get('인증유형', '')}형이 {top.get('비율(%)', 0)}%로 가장 많아요."


def _resolve_patent_forecast(seed: str, problem: str, solution: str) -> dict | None:
    """기술창업형 Q8(차별점) 앵커의 데이터 소스(특허출원 추이) - KIPRIS+OpenAI 외부 API
    호출이라 느리고 일일 호출 제한이 있다(patent_forecast.py 모듈 주석 참고). 실패해도
    None."""
    try:
        return get_patent_trend_with_forecast(seed, problem, solution, past_years=PATENT_FORECAST_YEARS)
    except Exception:  # noqa: BLE001 - KIPRIS/OpenAI 쪽 예외 종류가 다양해 폭넓게 잡고 None으로 둠
        return None


def _format_patent_anchor(patent_data: dict | None) -> str | None:
    """특허출원 추이를 한 문장으로 요약 - 최근 3개년 평균과 앞 3개년 평균을 비교해
    증가/감소/보합만 판단한다(정밀 추세선 대신 방향성만, 화면 문구용이라 이 정도로 충분)."""
    if not patent_data:
        return None
    actual = patent_data.get("actual") or {}
    valid = sorted((int(y), c) for y, c in actual.items() if c is not None)
    if len(valid) < 3:
        return None
    keyword = patent_data.get("keyword", "관련 분야")
    start_year = valid[0][0]
    recent_avg = sum(c for _, c in valid[-3:]) / 3
    older_avg = sum(c for _, c in valid[:3]) / 3
    if recent_avg > older_avg:
        return f"'{keyword}' 관련 특허출원이 {start_year}년 이후 늘고 있어요."
    if recent_avg < older_avg:
        return f"'{keyword}' 관련 특허출원이 {start_year}년 이후 줄고 있어요."
    return f"'{keyword}' 관련 특허출원이 {start_year}년 이후 비슷한 수준을 유지하고 있어요."


class DiagnosisStartRequest(BaseModel):
    origin: str  # "problem" | "opportunity" -> flow_type
    seed_interest: str
    problem_to_solve: str
    solution_approach: str
    has_store: bool
    sido: str
    sigungu: str
    dong: str


# session_id -> {"status": "pending"|"done"|"error", "targetAnchor": str|None, "differentiatorAnchor": str|None}
_report_status: dict[int, dict] = {}


def _run_report_in_background(
    session_id: int, has_store: bool, sido: str, sigungu: str, dong: str,
    resolved_ksic_codes: list[str], seed: str, problem: str, solution: str,
) -> None:
    """POST /start 응답을 보낸 뒤 이어서 실행 - 상권/기술창업 분석을 만들어 DB에
    UPDATE하고, 끝났다는 걸 _report_status로 표시한다. 실패해도 "error"로 표시할 뿐
    예외를 올리지 않는다 - 백그라운드 태스크라 터뜨려봐야 아무도 못 본다."""
    try:
        if has_store:
            market_analysis = _resolve_market_report(sido, sigungu, dong, resolved_ksic_codes)
            tech_analysis = None
            target_anchor = _format_market_target_anchor(market_analysis)
            differentiator_anchor = _format_market_differentiator_anchor(market_analysis)
        else:
            market_analysis = None
            tech_analysis = _resolve_tech_report(resolved_ksic_codes)
            patent_data = _resolve_patent_forecast(seed, problem, solution)
            if patent_data is not None:
                tech_analysis = dict(tech_analysis) if tech_analysis else {}
                tech_analysis["patent_forecast"] = patent_data
            target_anchor = _format_venture_anchor(tech_analysis)
            differentiator_anchor = _format_patent_anchor(patent_data)

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE idea_refinement_sessions SET market_analysis = %s, tech_analysis = %s WHERE session_id = %s",
                (
                    Json(market_analysis) if market_analysis is not None else None,
                    Json(tech_analysis) if tech_analysis is not None else None,
                    session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        _report_status[session_id] = {
            "status": "done", "targetAnchor": target_anchor, "differentiatorAnchor": differentiator_anchor,
        }
    except Exception:  # noqa: BLE001 - 백그라운드 태스크 전체를 감싸는 최종 안전망
        _report_status[session_id] = {"status": "error", "targetAnchor": None, "differentiatorAnchor": None}


@router.post("/start")
def start_diagnosis(
    payload: DiagnosisStartRequest, background_tasks: BackgroundTasks, user_id: int = Depends(get_current_user_id)
) -> JSONResponse:
    """6번째(마지막 필수) 질문 = 지역 제출 시점 - 세션을 만들고 업종코드 매칭만 먼저
    끝내서 응답한다(11~13초). 상권/기술창업 분석(추가 7~9초)은 백그라운드로 넘기고
    market_analysis/tech_analysis는 일단 NULL로 저장 - 분석 리포트 화면이
    GET /{id}/report로 완료 여부를 폴링한다(모듈 상단 주석 참고)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        profile_id = _get_profile_id(cur, user_id)
        if profile_id is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        region = " ".join(p for p in [payload.sido, payload.sigungu, payload.dong] if p)
        business_operation_type = "오프라인" if payload.has_store else "온라인"
        resolved_nts_codes, resolved_ksic_codes, industry_match = _resolve_industry_codes(
            payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
            payload.has_store, region=region,
        )

        cur.execute(
            """
            INSERT INTO idea_refinement_sessions (
                profile_id, status, flow_type, region, business_operation_type,
                psst_problem, psst_solution, psst_strategy,
                resolved_nts_codes, resolved_ksic_codes,
                save_consented, is_extended_diagnosis, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            RETURNING session_id
            """,
            (
                profile_id, "진행중", payload.origin, region, business_operation_type,
                payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
                Json(resolved_nts_codes), Json(resolved_ksic_codes),
                False, False,
            ),
        )
        session_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    # 백그라운드 태스크가 실제로 시작되기 전에 폴링이 먼저 들어와도 "아직 안 끝남"으로
    # 보이도록, 응답을 만들기 전에 미리 pending으로 표시해둔다.
    _report_status[session_id] = {"status": "pending", "targetAnchor": None, "differentiatorAnchor": None}
    background_tasks.add_task(
        _run_report_in_background, session_id, payload.has_store, payload.sido, payload.sigungu, payload.dong,
        resolved_ksic_codes, payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
    )

    return JSONResponse(content={
        "success": True,
        "data": {
            "session_id": session_id,
            "resolvedKsicCodes": resolved_ksic_codes,
            "industryMatch": industry_match,
            "track": "cafe" if payload.has_store else "tech",
        },
    })


@router.get("/{session_id}/report")
def get_diagnosis_report(session_id: int, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """분석 리포트 화면이 폴링하는 API - 백그라운드 리포트 생성이 끝났는지 확인한다.
    아직이면 {"ready": false}만, 끝났으면 marketAnalysis/techAnalysis + Q7·Q8 앵커까지
    같이 반환한다."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        profile_id = _get_profile_id(cur, user_id)
        if profile_id is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        cur.execute(
            "SELECT profile_id, market_analysis, tech_analysis FROM idea_refinement_sessions WHERE session_id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        if row is None or row[0] != profile_id:
            return _error(404, f"session_id={session_id} 세션을 찾을 수 없습니다.", "SESSION_NOT_FOUND")
        market_analysis, tech_analysis = row[1], row[2]
    finally:
        conn.close()

    status_entry = _report_status.get(session_id)
    if status_entry is not None and status_entry["status"] == "pending":
        return JSONResponse(content={"success": True, "data": {"ready": False}})

    # status_entry가 없는 경우(서버 재시작 등으로 인메모리 기록 유실) - DB에 이미
    # 채워져 있으면 완료로 간주. 앵커 문구는 그 경우 재계산 없이 비워둔다(Q7·Q8
    # 화면이 알아서 하드코딩 문구로 폴백).
    target_anchor = status_entry["targetAnchor"] if status_entry else None
    differentiator_anchor = status_entry["differentiatorAnchor"] if status_entry else None

    return JSONResponse(content={
        "success": True,
        "data": {
            "ready": True,
            "marketAnalysis": market_analysis,
            "techAnalysis": tech_analysis,
            "targetAnchor": target_anchor,
            "differentiatorAnchor": differentiator_anchor,
        },
    })


def _load_own_session(cur, session_id: int, profile_id: int) -> list | None:
    """session_id가 이 profile 소유인지 같이 확인 - 남의 세션을 URL의 session_id만
    바꿔서 건드리지 못하게 막는다. 없거나 남의 것이면 None."""
    cur.execute(
        "SELECT profile_id, resolved_ksic_codes FROM idea_refinement_sessions WHERE session_id = %s",
        (session_id,),
    )
    row = cur.fetchone()
    if row is None or row[0] != profile_id:
        return None
    return row


class DiagnosisFinishRequest(BaseModel):
    target: str = ""
    differentiator: str = ""
    revenue_model: str = ""
    core_skill: str = ""


@router.post("/{session_id}/finish")
def finish_diagnosis(
    session_id: int, payload: DiagnosisFinishRequest, user_id: int = Depends(get_current_user_id)
) -> JSONResponse:
    """10번(보유역량, 마지막) 제출 시점 - psst_team(보유역량)을 채우고 상태를 완료로
    바꾼다. 타깃/차별점/수익모델은 DB에 저장할 컬럼이 없어 아이디어 카드 생성 LLM
    프롬프트 재료로만 그 자리에서 쓰고 끝난다(모듈 상단 주석 참고)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        profile_id = _get_profile_id(cur, user_id)
        if profile_id is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        row = _load_own_session(cur, session_id, profile_id)
        if row is None:
            return _error(404, f"session_id={session_id} 세션을 찾을 수 없습니다.", "SESSION_NOT_FOUND")
        resolved_ksic_codes = row[1] or []

        cur.execute(
            "UPDATE idea_refinement_sessions SET psst_team = %s, status = %s WHERE session_id = %s",
            (payload.core_skill, "완료", session_id),
        )
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

    return JSONResponse(content={
        "success": True,
        "data": {
            "session_id": session_id,
            "cards": cards,
            # 결과 화면에서 관련 공고(/api/matching?ksic=)를 바로 불러올 수 있게 같이 내려준다.
            "resolvedKsicCodes": resolved_ksic_codes,
        },
    })
