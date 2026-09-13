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
# 끝나는 대로 바로 다음 화면(질응답 정리)으로 보내고 리포트는 그 뒤에 별도로 돌린다):
#   POST /start        - 업종코드 매칭 후보(최대 3개)를 뽑아 즉시 응답하는 동시에,
#                         [2026-09-13] 후보 전부에 대해 상권/기술창업 분석을
#                         백그라운드로 바로 시작한다(사용자 확인 - 하나만 강제로
#                         고르게 하던 걸 없애고, 사용자가 결과 화면을 읽는 동안
#                         뒤에서 미리 돌려서 체감 대기시간을 줄임). 코드별 결과는
#                         idea_refinement_sessions.analysis_by_code(JSONB)에
#                         {"56221": {...}, ...} 형태로 각자 쌓인다 - 코드를 콤마로
#                         합쳐 한꺼번에 넘기면 밀집도 계산(density.py/venture.py의
#                         target_codes)이 문자열 전체를 코드 하나로 취급해 아무
#                         업체와도 매칭 안 되는 버그가 있었어서, 후보마다 별도
#                         백그라운드 태스크로 나눠 돌린다. 1순위(후보 중 첫 번째,
#                         가장 신뢰도 높은) 결과만 market_analysis/tech_analysis
#                         레거시 컬럼과 Q7·Q8 앵커에도 그대로 반영한다(지역은 후보가
#                         달라도 동일해서 문제 없음, 사용자 확인). 더 이상 사용자가
#                         화면에서 하나를 확정하는 절차가 없으므로 예전
#                         POST /{id}/select-industry는 제거함.
#   GET /{id}/report   - 분석 리포트 화면이 폴링하는 API. resolved_ksic_codes 전부가
#                        analysis_by_code에 채워지기 전까지는 {"ready": false}만
#                        반환하고, 다 채워지면 analysisByCode(코드별 결과 전체) +
#                        1순위 기준 marketAnalysis/techAnalysis/Q7·Q8 앵커를 같이
#                        반환한다. 프론트는 상단 셀렉박스로 analysisByCode에서 원하는
#                        코드를 골라 보여준다.
# _report_status는 1순위 후보의 진행 상태(done/error)+앵커 캐시만 들고 있는
# 인메모리 캐시 - ponytail: 서버 재시작하면 기록이 날아간다(단일 프로세스 규모엔
# 충분, 여러 워커/재시작 안전성이 필요해지면 DB 컬럼이나 Redis로 승격). 전체 후보의
# 완료 여부 자체는 이제 DB(analysis_by_code)로 판단하므로 재시작에 안전하다.

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
    # [2026-09-13] 마이페이지에서 나중에 다시 열어볼 때 "빠른진단/정밀진단" 표시하려고 저장
    # (idea_refinement_sessions.diagnosis_mode 참고) - 안 보내면(구버전 프론트) "precise" 기본값.
    mode: str = "precise"


# session_id -> {"status": "done"|"error", "targetAnchor": str|None, "differentiatorAnchor": str|None}
# [2026-09-13] "ready" 판정 자체는 더 이상 이 dict로 안 함(DB의 analysis_by_code로
# 후보 전부 끝났는지 직접 확인 - get_diagnosis_report 참고) - 이건 1순위 후보의
# Q7·Q8 앵커 문구만 캐싱해둔다(서버 재시작하면 유실, 그 경우 앵커 없이 폴백).
_report_status: dict[int, dict] = {}


def _run_candidate_analysis(
    session_id: int, ksic_code: str, is_primary: bool, has_store: bool,
    sido: str, sigungu: str, dong: str, seed: str, problem: str, solution: str,
) -> None:
    """[2026-09-13] 업종코드 후보 하나에 대한 상권/기술창업 분석 (사용자 확인 - 후보
    최대 3개를 하나로 강제 확정시키지 않고 전부 각자 분석해서, 분석 리포트 화면
    상단 셀렉박스로 전환해가며 볼 수 있게 함). POST /start가 후보 개수만큼 이 함수를
    각각 백그라운드로 걸어서, 사용자가 industry-result 화면을 읽는 동안 미리 돌게
    한다 - 예전엔 사용자가 하나를 고른 뒤(POST /select-industry)에야 시작했음.

    결과는 idea_refinement_sessions.analysis_by_code[ksic_code]에 머지해 넣는다 -
    후보마다 독립 실행이라 하나가 실패해도 다른 후보엔 영향 없다(실패해도 그 코드
    자리에 실패 표시를 남겨 "전체 후보 다 준비됐나" 체크가 그 후보에서 영원히
    멈추지 않게 한다).

    is_primary(1순위, resolved_ksic_codes[0])면 기존 market_analysis/tech_analysis
    플랫 컬럼도 같이 채운다 - 마이페이지 리포트 목록 등 이 두 컬럼만 보고 "분석
    끝났나"를 판단하는 기존 코드와의 하위호환. Q7·Q8 앵커도 여러 후보 중 하나만
    골라야 해서 1순위로 고정한다(사용자 확인 - 지역은 후보가 달라도 동일해서
    문제 없음)."""
    try:
        if has_store:
            market_analysis = _resolve_market_report(sido, sigungu, dong, [ksic_code])
            tech_analysis = None
            target_anchor = _format_market_target_anchor(market_analysis)
            differentiator_anchor = _format_market_differentiator_anchor(market_analysis)
        else:
            market_analysis = None
            tech_analysis = _resolve_tech_report([ksic_code])
            patent_data = _resolve_patent_forecast(seed, problem, solution)
            if patent_data is not None:
                tech_analysis = dict(tech_analysis) if tech_analysis else {}
                tech_analysis["patent_forecast"] = patent_data
            target_anchor = _format_venture_anchor(tech_analysis)
            differentiator_anchor = _format_patent_anchor(patent_data)

        code_payload = json.dumps(
            {"marketAnalysis": market_analysis, "techAnalysis": tech_analysis}, ensure_ascii=False,
        )

        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE idea_refinement_sessions
                SET analysis_by_code = COALESCE(analysis_by_code, '{}'::jsonb) || jsonb_build_object(%s, %s::jsonb)
                WHERE session_id = %s
                """,
                (ksic_code, code_payload, session_id),
            )
            if is_primary:
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

        if is_primary:
            _report_status[session_id] = {
                "status": "done", "targetAnchor": target_anchor, "differentiatorAnchor": differentiator_anchor,
            }
    except Exception:  # noqa: BLE001 - 백그라운드 태스크 전체를 감싸는 최종 안전망
        try:
            conn = get_connection()
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE idea_refinement_sessions
                    SET analysis_by_code = COALESCE(analysis_by_code, '{}'::jsonb) || jsonb_build_object(%s, %s::jsonb)
                    WHERE session_id = %s
                    """,
                    (ksic_code, json.dumps({"marketAnalysis": None, "techAnalysis": None, "failed": True}), session_id),
                )
                conn.commit()
            finally:
                conn.close()
        except Exception:  # noqa: BLE001
            pass
        if is_primary:
            _report_status[session_id] = {"status": "error", "targetAnchor": None, "differentiatorAnchor": None}


@router.post("/start")
def start_diagnosis(
    payload: DiagnosisStartRequest, background_tasks: BackgroundTasks, user_id: int = Depends(get_current_user_id)
) -> JSONResponse:
    """6번째(마지막 필수) 질문 = 지역 제출 시점 - 세션을 만들고 업종코드 매칭을
    끝내서 응답한다(11~13초). [2026-09-13] 매칭 후보(최대 3개) 전부에 대해 상권/
    기술창업 분석을 여기서 곧바로 백그라운드로 건다(사용자 확인) - 사용자가
    industry-result 화면에서 후보를 읽는 시간 동안 미리 분석이 진행돼서, 예전에
    "하나 확정 후에야 분석 시작"하던 것보다 체감 대기시간이 줄어든다. 후보를 하나로
    강제 확정시키지 않으므로 POST /{id}/select-industry는 더 이상 안 씀(제거됨)."""
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
                save_consented, is_extended_diagnosis, created_at,
                diagnosis_mode, industry_match_summary
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), %s, %s)
            RETURNING session_id
            """,
            (
                profile_id, "진행중", payload.origin, region, business_operation_type,
                payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
                Json(resolved_nts_codes), Json(resolved_ksic_codes),
                False, False,
                payload.mode, Json(industry_match) if industry_match is not None else None,
            ),
        )
        session_id = cur.fetchone()[0]
        conn.commit()
    finally:
        conn.close()

    for i, code in enumerate(resolved_ksic_codes):
        background_tasks.add_task(
            _run_candidate_analysis, session_id, code, i == 0, payload.has_store,
            payload.sido, payload.sigungu, payload.dong,
            payload.seed_interest, payload.problem_to_solve, payload.solution_approach,
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
    같이 반환한다.

    [2026-09-13] 업종코드 후보(최대 3개) 전부를 각자 분석하는 구조로 바뀌면서,
    "끝났다"의 기준도 인메모리 pending 플래그 대신 **DB의 analysis_by_code에 후보
    코드가 전부 들어있는지**로 직접 판단한다(서버 재시작에도 안전 - 원래도 인메모리
    기록 유실 시 DB로 폴백하던 방식이었는데, 이제 그게 기본 판단 기준이 됨).
    응답에 analysisByCode(코드별 결과 전체)도 같이 내려줘서, 분석 리포트 화면
    상단 셀렉박스가 코드 전환 시 재요청 없이 바로 전환할 수 있게 한다.

    [2026-09-13] 마이페이지 "분석 리포트"에서 지난 세션을 나중에 다시 열어볼 때도
    이 응답 하나로 화면을 완전히 그릴 수 있게, track/resolvedKsicCodes/mode/
    industryMatch/sido까지 같이 내려준다(전엔 sessionStorage에만 있던 값들 -
    idea_refinement_sessions.diagnosis_mode/industry_match_summary 참고)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        profile_id = _get_profile_id(cur, user_id)
        if profile_id is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        cur.execute(
            """
            SELECT profile_id, market_analysis, tech_analysis, business_operation_type,
                   resolved_ksic_codes, diagnosis_mode, industry_match_summary, region, analysis_by_code
            FROM idea_refinement_sessions WHERE session_id = %s
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if row is None or row[0] != profile_id:
            return _error(404, f"session_id={session_id} 세션을 찾을 수 없습니다.", "SESSION_NOT_FOUND")
        (_, market_analysis, tech_analysis, business_operation_type,
         resolved_ksic_codes, diagnosis_mode, industry_match_summary, region, analysis_by_code) = row
    finally:
        conn.close()

    resolved_ksic_codes = resolved_ksic_codes or []
    analysis_by_code = analysis_by_code or {}
    # 후보가 아예 없으면(업종 특정 실패) 기다릴 대상 자체가 없으니 바로 완료로 본다.
    all_candidates_ready = all(code in analysis_by_code for code in resolved_ksic_codes)
    if not all_candidates_ready:
        return JSONResponse(content={"success": True, "data": {"ready": False}})

    # 1순위 후보의 Q7·Q8 앵커 - 인메모리 캐시라 서버 재시작하면 유실될 수 있음, 그
    # 경우 앵커 없이 폴백(Q7·Q8 화면이 알아서 하드코딩 문구로 대체).
    status_entry = _report_status.get(session_id)
    target_anchor = status_entry["targetAnchor"] if status_entry else None
    differentiator_anchor = status_entry["differentiatorAnchor"] if status_entry else None
    industry_match_summary = industry_match_summary or {}

    return JSONResponse(content={
        "success": True,
        "data": {
            "ready": True,
            "marketAnalysis": market_analysis,
            "techAnalysis": tech_analysis,
            "targetAnchor": target_anchor,
            "differentiatorAnchor": differentiator_anchor,
            "track": "cafe" if business_operation_type == "오프라인" else "tech",
            "resolvedKsicCodes": resolved_ksic_codes,
            "mode": diagnosis_mode or "precise",
            "sido": (region or "").split(" ")[0] if region else "",
            "dong": (region or "").split(" ")[-1] if region else "",
            "industryMatchName": industry_match_summary.get("name"),
            "industryMatchState": industry_match_summary.get("state"),
            "industryMatchConfidence": industry_match_summary.get("confidence"),
            "analysisByCode": analysis_by_code,
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
