"""HIGH confidence 자동확정 게이팅 정책.

배경 (2026-09-12 실측, 독립홀드아웃 110건)
------------------------------------------
기존 ``ksic_confidence``(=이 모듈에서 ``match_strength``로 이름을 명확히 함)는
"문자열/코드 매칭이 얼마나 직접적인가"일 뿐 실제 정답 확률이 아니다.

    confidence==HIGH  T2b 정확도 59.6%  (그중 특정업종 확정 49건만 보면 53.1%)
    confidence==MED   T2b 정확도 96.0%
    confidence==LOW   T2b 정확도 100.0%

즉 "확신 있다"고 표시한 그룹이 오히려 제일 부정확했다. 원인은 두 갈래:

1. 이름/동의어 매칭의 "지원대상/신청자격/지원업종 문맥" 판정(rule_detectors.
   classify_occurrence_role)이 최대 650자 근접 창만 보고, 후보가 실제로 그
   헤더가 규정하는 지원대상 목록의 일부인지는 확인하지 않는다.
2. 직접 KSIC 코드 매칭도 "KSIC 헤더 근처"라는 이유만으로 참고용 코드표
   (통계 예시, 국세청 코드 안내 등)를 지원대상 표로 오인하는 경우가 있다.

이 모듈은 confidence(match_strength)를 건드리지 않고, 그 위에 별도의
게이팅 신호(scope_decision/scope_verified/auto_accept_eligible/
final_confidence)를 얹는다. 자동확정 여부는 이제 confidence==HIGH가 아니라
``auto_accept_eligible``로 결정한다.

값의 근거가 되는 재보정 테이블은 ``scripts/46_build_confidence_calibration.py``가
만드는 ``data/ml/confidence_calibration_table.csv``에서 로드한다. 파일이 없거나
해당 조합이 없으면 보수적으로 강등(HIGH->MED)한다.
"""
from __future__ import annotations

import csv
import os

SCOPE_SPECIFIC = "SPECIFIC"
SCOPE_ALL_INDUSTRIES = "ALL_INDUSTRIES"
SCOPE_UNRESOLVED_REVIEW = "UNRESOLVED_REVIEW"

# 2026-09-12e: scope_decision이 "왜" 그 값이 됐는지 구분하는 근거 태그.
# orchestrator가 이 값으로 "Rule이 진짜 명시적 전업종 근거를 찾았는가"와
# "그냥 아무 근거도 없었는가"를 구분한다 — 둘 다 build_scope_fields()에서는
# codes==[]일 때 나오지만 의미가 다르다(전자만 진짜 ALL_INDUSTRIES 근거).
BASIS_EXPLICIT_ALL_INDUSTRIES = "EXPLICIT_ALL_INDUSTRIES"
BASIS_EXPLICIT_UNRESOLVED = "EXPLICIT_UNRESOLVED"
BASIS_NO_EVIDENCE = "NO_EVIDENCE"
BASIS_STRUCTURAL_ANOMALY = "STRUCTURAL_ANOMALY"
BASIS_RULE_CANDIDATE = "RULE_CANDIDATE"

# candidate_source: 최종 ksic_codes가 어디서 왔는지 추적하는 provenance 태그.
SOURCE_RULE = "RULE"
SOURCE_RULE_VERIFIED_BY_ML = "RULE_VERIFIED_BY_ML"
SOURCE_RULE_VERIFIED_BY_LLM = "RULE_VERIFIED_BY_LLM"
SOURCE_LLM_RESOLVER = "LLM_RESOLVER"

ROLE_SUPPORT_TARGET = "SUPPORT_TARGET"
ROLE_EXCLUSION = "EXCLUSION"
ROLE_REFERENCE_OR_EXAMPLE = "REFERENCE_OR_EXAMPLE"
ROLE_THIRD_PARTY = "THIRD_PARTY"
ROLE_UNKNOWN = "UNKNOWN"
# [2026-09-13 Resolver R1 evidence gate 추가] 사업명/사업목적/기술분야처럼 이
# 공고가 "무엇에 관한" 사업인지 설명하는 근거일 뿐, "누가 신청 가능한지"를
# 제한하는 eligibility 근거가 아닌 경우. 예: "AI 도입 지원사업"은 SUBJECT_ONLY,
# "지원대상: AI 소프트웨어 개발업체"는 SUPPORT_TARGET.
ROLE_SUBJECT_ONLY = "SUBJECT_ONLY"
# [2026-09-13 V2.1 Verifier evidence gate 추가] "우선 모집분야/우대 조건"처럼
# 특정 업종을 우선순위·가점 대상으로만 언급할 뿐, 실제 신청자격(누가 지원
# 가능한지)을 그 업종으로 제한하지 않는 경우. 실측(PBLN_126301): "대상:
# 일본시장 진출을 희망하는 기업"(업종 무관)인데 "우선 모집분야: 화장품‧뷰티
# 등"을 SUPPORT_TARGET으로 오인해 화장품 제조업(20423)으로 잘못 확정한 사례.
ROLE_PRIORITY_OR_PREFERENCE = "PRIORITY_OR_PREFERENCE"

# 이 값을 넘으면 authoritative(직접코드) 자동확정 자격을 강등한다.
MAX_AUTHORITATIVE_CODES = 5
# 이 값 이상이면 매칭 방식/재보정과 무관하게 무조건 검토로 보낸다.
# (실측 사례: 참고용 코드표 하나에서 90개 코드가 잡혀 HIGH 오탐이 된 경우)
HARD_BLOCK_CODES = 20

CALIBRATION_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "통합_2073", "최종검증", "4차",
    "confidence_calibration_table.csv",
)

# rule_detectors.classify_occurrence_role / explicit_match 가 실제로 만들어내는
# reason 문자열 -> (evidence_role, tag). 문자열은 코드 수정 없이 grep으로 확인한
# 실제 값이다. tag는 재보정 테이블의 키로 쓰인다.
_REASON_TAGS: list[tuple[str, tuple[str, str]]] = [
    ("기업·업체·사업주 직접 표현", (ROLE_SUPPORT_TARGET, "strong_biz_expr")),
    ("지원대상/신청자격/지원업종 문맥의 직접 코드", (ROLE_SUPPORT_TARGET, "strong_direct_code")),
    ("붙임·별표 코드표", (ROLE_SUPPORT_TARGET, "strong_appendix")),
    ("영위기업/해당업종 직접 선언", (ROLE_SUPPORT_TARGET, "medium_영위선언")),
    # 아래는 근접 창(650자)만으로 판정하는 가장 느슨한 positive 신호 —
    # 2026-09-12 실측에서 오탐의 핵심 원인.
    ("지원대상/신청자격/지원업종 문맥", (ROLE_SUPPORT_TARGET, "weak_generic_proximity")),
    ("KSIC/업종코드 표에 직접 명시", (ROLE_REFERENCE_OR_EXAMPLE, "weak_table_near_header")),
    ("KSIC 코드와 공식 업종명이 함께 직접 명시", (ROLE_REFERENCE_OR_EXAMPLE, "weak_table_near_header")),
    ("국세청 업종코드 헤더에 직접 명시", (ROLE_REFERENCE_OR_EXAMPLE, "weak_table_near_header")),
]

# tag별 보수성 순위(작을수록 더 보수적으로 취급). 여러 후보가 섞이면 가장
# 보수적인 태그를 대표값으로 쓴다(하나라도 약하면 전체를 못 믿는다).
_TAG_ORDER = {
    "weak_generic_proximity": 0,
    "weak_table_near_header": 0,
    "unknown": 0,
    "other": 0,
    "medium_영위선언": 1,
    "code_direct_noreason": 1,
    "strong_biz_expr": 2,
    "strong_appendix": 2,
    "strong_direct_code": 3,
}


def _extract_reason_strings(evidence: dict) -> list[str]:
    if not isinstance(evidence, dict):
        return []
    out: list[str] = []
    ev_list = evidence.get("evidence")
    if isinstance(ev_list, list):
        out.extend(str(e.get("reason", "")) for e in ev_list if isinstance(e, dict))
    det_list = evidence.get("탐지상세")
    if isinstance(det_list, list):
        out.extend(
            str(d.get("reason", "")) for d in det_list
            if isinstance(d, dict) and d.get("role") == "positive"
        )
    return out


def classify_candidate_tags(evidence: dict) -> list[tuple[str, str]]:
    """근거 dict에서 (evidence_role, tag) 목록을 뽑는다.

    reason 문자열을 못 찾으면(예: authoritative 직접코드인데 개별 reason이
    비어있는 구버전 경로) 최대한 보수적으로 UNKNOWN/REFERENCE로 분류한다.
    """
    reasons = _extract_reason_strings(evidence)
    if not reasons:
        if evidence.get("authoritative"):
            return [(ROLE_REFERENCE_OR_EXAMPLE, "code_direct_noreason")]
        return [(ROLE_UNKNOWN, "unknown")]

    out = []
    for r in reasons:
        for needle, tagval in _REASON_TAGS:
            if needle in r:
                out.append(tagval)
                break
        else:
            out.append((ROLE_UNKNOWN, "other"))
    return out or [(ROLE_UNKNOWN, "unknown")]


def weakest_role_tag(tags: list[tuple[str, str]]) -> tuple[str, str]:
    if not tags:
        return (ROLE_UNKNOWN, "unknown")
    return min(tags, key=lambda t: _TAG_ORDER.get(t[1], 0))


def candidate_count_bucket(n: int) -> str:
    if n <= 0:
        return "0"
    if n == 1:
        return "1"
    if n <= 5:
        return "2-5"
    if n <= 19:
        return "6-19"
    return "20+"


_calibration: dict | None = None


def _load_calibration() -> dict:
    global _calibration
    if _calibration is not None:
        return _calibration
    table: dict[tuple[str, str, str], dict] = {}
    if os.path.exists(CALIBRATION_CSV):
        with open(CALIBRATION_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = (row["method"], row["tag"], row["count_bucket"])
                table[key] = {
                    "n": int(row["n"]),
                    "accuracy": float(row["accuracy"]),
                    "final_confidence": row["final_confidence"],
                }
    _calibration = table
    return _calibration


def reload_calibration() -> None:
    """테스트/재생성 후 캐시를 강제로 비운다."""
    global _calibration
    _calibration = None


def lookup_calibration(method: str, tag: str, count_bucket: str) -> dict | None:
    table = _load_calibration()
    row = table.get((method, tag, count_bucket))
    if row:
        return row
    # count_bucket을 무시하고 method+tag만으로 재시도(표본 부족 버킷 스무딩).
    candidates = [v for (m, t, _cb), v in table.items() if m == method and t == tag]
    if candidates:
        # 표본 수가 가장 많은 병합 버킷을 대표값으로.
        return max(candidates, key=lambda v: v["n"])
    return None


def build_scope_fields(result: dict | None) -> dict:
    """decide_industry() 원시 결과(dict 또는 None) -> 게이팅 신호 dict.

    반환 키: match_strength, scope_decision, scope_verified,
    auto_accept_eligible, final_confidence (+특정업종일 때
    candidate_evidence_role/candidate_evidence_tag/candidate_count).
    """
    if result is None:
        return {
            "match_strength": "",
            "scope_decision": SCOPE_ALL_INDUSTRIES,
            "scope_verified": False,
            "auto_accept_eligible": False,
            "final_confidence": "",
            "scope_basis": BASIS_NO_EVIDENCE,
        }

    raw_conf = str(result.get("ksic_confidence") or "")
    codes = result.get("확정코드") or []
    stage = str(result.get("확정단계") or "")
    status = str(result.get("ksic_status") or stage)
    evidence = result.get("근거") if isinstance(result.get("근거"), dict) else {}

    if not codes:
        if "업종무관" in status:
            # 명시적 업종무관(override/HIGH)은 실측 100% 정확 — 그대로 유지.
            verified = raw_conf == "HIGH"
            return {
                "match_strength": raw_conf,
                "scope_decision": SCOPE_ALL_INDUSTRIES,
                "scope_verified": verified,
                "auto_accept_eligible": verified,
                "final_confidence": raw_conf,
                "scope_basis": BASIS_EXPLICIT_ALL_INDUSTRIES,
            }
        if "특정불가" in status:
            return {
                "match_strength": raw_conf,
                "scope_decision": SCOPE_UNRESOLVED_REVIEW,
                "scope_verified": False,
                "auto_accept_eligible": False,
                "final_confidence": raw_conf,
                "scope_basis": BASIS_EXPLICIT_UNRESOLVED,
            }
        return {
            "match_strength": raw_conf,
            "scope_decision": SCOPE_ALL_INDUSTRIES,
            "scope_verified": False,
            "auto_accept_eligible": False,
            "final_confidence": raw_conf,
            "scope_basis": BASIS_NO_EVIDENCE,
        }

    # --- 특정 코드가 있는 경우: 실측 역전이 발생한 지점 ---
    n = len(codes)
    method = evidence.get("매칭방식", "")
    conflict = bool(evidence.get("positive_exclusion_conflict"))

    if n >= HARD_BLOCK_CODES:
        return {
            "match_strength": raw_conf,
            "scope_decision": SCOPE_UNRESOLVED_REVIEW,
            "scope_verified": False,
            "auto_accept_eligible": False,
            "final_confidence": "LOW",
            "candidate_evidence_role": ROLE_REFERENCE_OR_EXAMPLE,
            "candidate_evidence_tag": "table_reference_anomaly",
            "candidate_count": n,
            "scope_basis": BASIS_STRUCTURAL_ANOMALY,
        }

    tags = classify_candidate_tags(evidence)
    role, tag = weakest_role_tag(tags)
    count_bucket = candidate_count_bucket(n)

    calib = lookup_calibration(method, tag, count_bucket)
    if calib:
        final_conf = calib["final_confidence"]
    else:
        # 재보정 테이블에 없는 조합은 보수적으로 한 단계 강등.
        final_conf = "MED" if raw_conf == "HIGH" else raw_conf

    auto_ok = (
        final_conf == "HIGH"
        and role == ROLE_SUPPORT_TARGET
        and not conflict
        and n <= MAX_AUTHORITATIVE_CODES
    )

    return {
        "match_strength": raw_conf,
        "scope_decision": SCOPE_SPECIFIC,
        "scope_verified": auto_ok,
        "auto_accept_eligible": auto_ok,
        "final_confidence": final_conf,
        "candidate_evidence_role": role,
        "candidate_evidence_tag": tag,
        "candidate_count": n,
        "scope_basis": BASIS_RULE_CANDIDATE,
    }


def evidence_window(text: str, result: dict | None, max_len: int = 1200) -> str:
    """근거(evidence) span 중심의 문맥 window를 뽑는다.

    ML 임베딩 모델(G/H, scripts/48) 입력용. 우선순위:
    1) 근거 evidence/탐지상세의 시작~종료 span을 감싸는 구간(±200자)
    2) 지원대상/신청자격/모집대상 헤더 근처 구간
    3) 원문 앞부분 fallback
    """
    text = str(text or "")
    if not text.strip():
        return ""

    spans: list[tuple[int, int]] = []
    evidence = result.get("근거") if isinstance(result, dict) and isinstance(result.get("근거"), dict) else {}
    for key in ("evidence", "탐지상세"):
        items = evidence.get(key)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    s = it.get("시작", it.get("start"))
                    e = it.get("종료", it.get("end"))
                    if isinstance(s, int) and isinstance(e, int):
                        spans.append((s, e))

    if spans:
        start = max(0, min(s for s, _ in spans) - 200)
        end = min(len(text), max(e for _, e in spans) + 200)
        window = text[start:end]
        return window[:max_len]

    import re as _re
    m = _re.search(r"지원\s*대상|신청\s*자격|모집\s*대상|참여\s*대상|융자\s*대상", text)
    if m:
        start = max(0, m.start() - 50)
        return text[start:start + max_len]

    return text[:max_len]


def normalize_final_result(
    scope_decision: str,
    codes: list[str],
    names: list[str],
    auto_accept_eligible: bool,
    *,
    rule_codes: list[str] | None = None,
    rule_names: list[str] | None = None,
    candidate_source: str = SOURCE_RULE,
) -> dict:
    """최종 결과 조립의 단일 검문소 — orchestrator의 모든 routing 분기가 반드시
    이 함수를 통과한다(2026-09-12c, 상태불일치 버그 수정).

    버그: ML REJECT_SPECIFIC 등에서 ``scope_decision``만 바꾸고 ``ksic_codes``를
    안 비워서(또는 그 반대) "SPECIFIC인데 ksic_codes==[]" 같은 모순 상태가
    나갔다(``ml_llm_orchestration_case_audit.csv`` 11/110건 확인). 이 함수가
    강제하는 불변조건:

    1. ALL_INDUSTRIES        -> ksic_codes/ksic_names == []
    2. SPECIFIC + codes 없음 -> ALL_INDUSTRIES로 강등(코드 없는 SPECIFIC은 모순)
    3. UNRESOLVED_REVIEW     -> 최종 ksic_codes/ksic_names는 비우고, Rule 원본
                                후보는 candidate_ksic_codes/candidate_ksic_names에만 보존
    4. auto_accept_eligible==True는 SPECIFIC/ALL_INDUSTRIES에서만 허용
       (UNRESOLVED_REVIEW면 무조건 False로 강제)
    5. needs_human_review == not auto_accept_eligible (파생값, 별도 상태 없음)

    Rule 원본 후보(rule_codes/rule_names)는 감사용으로 항상
    candidate_ksic_codes/candidate_ksic_names에 보존한다(scope와 무관하게).

    2026-09-12e: ``candidate_source``(provenance)를 추가했다 — 최종
    ``ksic_codes``가 어디서 왔는지(RULE/RULE_VERIFIED_BY_ML/
    RULE_VERIFIED_BY_LLM/LLM_RESOLVER) 구분한다. 순수 추가 필드이며 기존
    불변조건 1~5는 전혀 바뀌지 않는다.
    """
    codes = [str(c) for c in (codes or [])]
    names = [str(n) for n in (names or [])]
    scope = scope_decision or SCOPE_ALL_INDUSTRIES

    if scope == SCOPE_SPECIFIC and not codes:
        scope = SCOPE_ALL_INDUSTRIES  # 코드 없는 SPECIFIC은 모순 상태이므로 강등

    if scope != SCOPE_SPECIFIC:
        codes, names = [], []

    if scope == SCOPE_UNRESOLVED_REVIEW:
        auto_accept_eligible = False

    service_category = "특정업종대상" if (scope == SCOPE_SPECIFIC and codes) else "전업종노출"

    return {
        "scope_decision": scope,
        "service_category": service_category,
        "ksic_codes": codes,
        "ksic_names": names,
        "candidate_ksic_codes": [str(c) for c in (rule_codes or [])],
        "candidate_ksic_names": [str(n) for n in (rule_names or [])],
        "candidate_source": candidate_source,
        "auto_accept_eligible": bool(auto_accept_eligible),
        "needs_human_review": not bool(auto_accept_eligible),
    }


def route_after_rule(result: dict) -> dict:
    """Rule 이후 ML게이트/LLM 라우팅 정책의 dry-run 스텁.

    실제 notice_gate.py/llm_match.py 호출은 하지 않는다(운영 기본값 유지).
    "다음에 어디로 보내야 하는가"의 스키마만 문서화한다 — predict.py 기본
    경로에는 연결하지 않음.
    """
    if result.get("auto_accept_eligible"):
        return {"route": "AUTO_ACCEPT"}
    if result.get("scope_decision") == SCOPE_UNRESOLVED_REVIEW:
        return {"route": "LLM_VERIFIER_OR_HUMAN"}
    if result.get("scope_decision") == SCOPE_SPECIFIC:
        return {"route": "ML_GATE"}
    return {"route": "HUMAN_REVIEW"}
