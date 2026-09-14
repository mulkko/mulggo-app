# -*- coding: utf-8 -*-
"""LLM Verifier runtime adapter.

2026-09-12d 재설계: LLM은 자유생성 분류기가 아니라 **candidate verifier**로
동작한다 — ``llm_match.verify_candidates_with_llm()``을 호출해 Rule/ML이
이미 낸 후보(candidate_codes) 각각을 SUPPORTED/UNSUPPORTED/UNCERTAIN으로
검증받고, 그 verdict로 후보의 유지·제거만 결정한다. 최종 채택 코드
(``llm_verified_codes``)는 항상 원래 후보의 부분집합이다 — LLM이 새로
제안한 코드나 더 세밀한 코드는 ``llm_suggested_refinement``라는 별도
필드로만 나가고 자동으로 최종코드에 섞이지 않는다.

이전 설계(자유응답 + 문자열 완전일치 필터)의 문제: Rule 후보가 대분류
알파벳처럼 넓은 코드(예: "C")이고 LLM이 그보다 세밀한 코드(예: "285")로
답하면, 계층적으로는 호환되는 정답인데도 문자열이 다르다는 이유만으로
전부 폐기됐다(T1 실측 PBLN_126209). 그렇다고 "계층 호환되면 자동 채택"으로
바꾸면 LLM이 무슨 이름을 대든 같은 대분류이기만 하면 통과되어 버려
위험하다 — 그래서 계층 호환 여부는 참고 정보로만 남기고(각 제안에
``hierarchy_compatible_with_candidate`` 플래그), 최종 채택 여부는 절대
쓰지 않는다.

API 키가 없거나 모듈을 못 불러오거나 호출이 실패해도 예외를 던지지
않고 ``llm_status``로만 알린다 — 서비스가 LLM 장애로 죽으면 안 된다.

테스트에서는 ``call_fn``을 주입해 실제 API를 호출하지 않고 mock할 수 있다.
새 call_fn 시그니처: ``call_fn(text, candidates) -> {"verdicts": {...},
"suggested_refinement": [...]} | None`` (candidates는
``[{"code":..., "name":...}, ...]``).
"""
from __future__ import annotations

import os

try:  # .env가 있으면 조용히 로드(없어도, 실패해도 무해). 키 값은 절대 로그하지 않는다.
    from dotenv import load_dotenv
    load_dotenv(override=False)
except Exception:  # noqa: BLE001
    pass

try:
    from ksic_core.llm_match import verify_candidates_with_llm as _default_call_fn
except Exception:  # 모듈/의존성 자체가 없는 환경
    _default_call_fn = None

try:
    from ksic_core.hierarchy import is_same_industry as _is_same_industry
except Exception:  # noqa: BLE001
    _is_same_industry = None


def _preflight_unavailable_reason() -> str | None:
    """호출 전에 빠르게 확인. llm_match._check_has_basis()는 API 호출 실패도
    내부적으로 잡아서 '근거 없음'(None)으로 되돌리기 때문에, 여기서 미리
    확인하지 않으면 'API 키 없음'과 '진짜 근거 없음'을 구분할 수 없다."""
    try:
        from ksic_core import llm_match
    except Exception as e:  # noqa: BLE001
        return f"llm_match import 실패: {type(e).__name__}: {e}"
    provider = getattr(llm_match, "LLM_PROVIDER", "openai")
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY 미설정"
    if provider == "gemini" and not os.environ.get("GOOGLE_API_KEY"):
        return "GOOGLE_API_KEY 미설정"
    return None


def _empty_result(status: str, decision, reason: str) -> dict:
    return {
        "llm_status": status,
        "llm_decision": decision,
        "llm_verified_codes": [],
        "llm_verified_names": [],
        "llm_evidence_quote": "",
        "llm_reason": reason,
        "llm_candidate_consistent": True,
        "llm_raw_confidence": None,
        "llm_verdicts_detail": {},
        "llm_suggested_refinement": [],
    }


def _unavailable(reason: str) -> dict:
    return _empty_result("UNAVAILABLE", None, reason)


def _error(reason: str) -> dict:
    out = _unavailable(reason)
    out["llm_status"] = "ERROR"
    return out


def verify(text: str, candidate_codes: list[str] | None, candidate_names: list[str] | None,
           *, call_fn=None) -> dict:
    """Rule 후보(candidate_codes)를 LLM이 검증한다. 최종 채택 코드는 항상
    이 후보의 부분집합이다 — 새 코드/세분화 코드는 절대 채택하지 않고
    ``llm_suggested_refinement``로만 보고한다."""
    fn = call_fn if call_fn is not None else _default_call_fn
    if fn is None:
        return _unavailable("llm_match 모듈을 불러올 수 없음(의존성 없음)")

    codes = [str(c) for c in (candidate_codes or [])]
    names = [str(n) for n in (candidate_names or [])]
    if not codes:
        return _unavailable("검증할 Rule 후보가 없음")

    if call_fn is None:  # 주입된 mock/stub은 사전점검을 건너뛴다(테스트용).
        reason = _preflight_unavailable_reason()
        if reason:
            return _unavailable(reason)

    candidates = [{"code": c, "name": n} for c, n in zip(codes, names)]
    try:
        raw = fn(text, candidates)
    except Exception as e:  # OPENAI_API_KEY 없음, 네트워크 오류 등 무엇이든
        return _error(f"{type(e).__name__}: {e}")

    if raw is None or not isinstance(raw, dict):
        # 파싱 실패 등 — 후보를 확신 있게 버릴 근거도 없으므로 보수적으로 검토行.
        return _empty_result("RUN", "UNRESOLVED_REVIEW", "LLM 응답 파싱 실패 — 후보 판정 불가")

    verdicts = raw.get("verdicts") or {}
    supported = [c for c in codes if verdicts.get(c, {}).get("verdict") == "SUPPORTED"]
    unsupported = [c for c in codes if verdicts.get(c, {}).get("verdict") == "UNSUPPORTED"]
    uncertain = [c for c in codes if verdicts.get(c, {}).get("verdict") == "UNCERTAIN"]

    kept_codes = supported
    kept_names = [n for c, n in zip(codes, names) if c in supported]

    if kept_codes:
        decision = "SPECIFIC"
    elif uncertain:
        # 확신 있게 기각(UNSUPPORTED)된 것도, 확신 있게 채택된 것도 없음 — 검토로.
        decision = "UNRESOLVED_REVIEW"
    else:
        # 후보 전부 UNSUPPORTED — LLM이 명확히 "이 후보들은 아니다"라고 판단.
        decision = "ALL_INDUSTRIES"

    quote = " / ".join(v.get("quote", "") for v in verdicts.values() if v.get("quote"))
    reason = " / ".join(f"{c}:{v.get('verdict', '')}" for c, v in verdicts.items())

    suggestions = []
    for s in raw.get("suggested_refinement") or []:
        item = dict(s)
        # 계층 호환 여부는 참고 정보로만 남긴다 — 이 값으로 자동채택하지 않는다.
        compat = None
        if _is_same_industry is not None and item.get("code"):
            compat = any(_is_same_industry(item["code"], c) for c in codes)
        item["hierarchy_compatible_with_candidate"] = compat
        suggestions.append(item)

    return {
        "llm_status": "RUN",
        "llm_decision": decision,
        "llm_verified_codes": kept_codes,
        "llm_verified_names": kept_names,
        "llm_evidence_quote": quote,
        "llm_reason": reason,
        # 후보 중 하나라도 기각(UNSUPPORTED)됐으면 False — "LLM이 Rule 후보를
        # 전부 그대로 인정했는가"라는 기존 필드 의미를 유지.
        "llm_candidate_consistent": len(unsupported) == 0,
        "llm_raw_confidence": None,  # candidate verifier 구조엔 단일 confidence 개념이 없음
        "llm_verdicts_detail": verdicts,
        "llm_suggested_refinement": suggestions,
    }
