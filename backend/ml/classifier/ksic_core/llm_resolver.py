# -*- coding: utf-8 -*-
"""LLM Fallback Resolver.

2026-09-12e 리팩터링으로 신설. Candidate Verifier(``llm_verifier.py``)와
역할이 다르다 — Verifier는 "Rule 후보가 맞는지" 검증만 하고, Resolver는
**Rule/ML/Verifier가 특정업종을 전혀 못 찾았을 때 KSIC 마스터 전체를 대상으로
새로 찾아보는** 최후 수단이다.

2026-09-12g: 57건 실측 진단(resolver_57case_diagnostic_report.md) 결과 순
회귀 15건 중 상당수가 "자유응답은 반드시 업종 하나를 답해야 한다"는 구조적
압력에서 나왔다는 게 확인되어, 내부 호출을 자유생성 단일 함수
(``match_ksic_by_llm``)에서 범위 우선 3단계(``llm_match.resolve_scope_first``:
R1 범위판단 → R2 세부유형판단 → R3 코드생성, R3는 기존 로직 그대로 재사용)로
바꿨다. 또한 Rule이 이미 아는 위험 신호(``rule_detectors.detect_resolver_risk_signals``)
를 ``risk_signals``로 전달받아 프롬프트 참고용으로 넘긴다.

안전 정책(변경 금지): Resolver가 새로 찾은 코드는 SPECIFIC으로 최종 반영될
수 있지만, ``auto_accept_eligible``은 호출부(orchestrator)가 항상 False로
강제한다 — 이 모듈 자체는 그 강제를 하지 않는다(orchestrator의 책임이며,
이 파일은 순수하게 "Resolver가 뭘 찾았는지"만 보고한다). Resolver는 이제
``ALL_INDUSTRIES``도 스스로 판단해 반환할 수 있다(R1의 명시적 업종무관
근거 발견) — 이 경우도 auto_accept_eligible 강제는 동일하게 적용된다.

API 키가 없거나 호출이 실패해도 예외를 던지지 않고 ``resolver_status``로만
알린다. 테스트에서는 ``call_fn``을 주입해 실제 API를 호출하지 않고 mock할
수 있다(``resolve(text, call_fn=lambda t, risk_signals=None: {...})``).
"""
from __future__ import annotations

import os

try:  # .env가 있으면 조용히 로드(없어도, 실패해도 무해). 키 값은 절대 로그하지 않는다.
    from dotenv import load_dotenv
    load_dotenv(override=False)
except Exception:  # noqa: BLE001
    pass

try:
    from ksic_core.llm_match import resolve_scope_first as _default_call_fn
except Exception:  # 모듈/의존성 자체가 없는 환경
    _default_call_fn = None


def _preflight_unavailable_reason() -> str | None:
    """호출 전에 빠르게 확인한다. ``llm_match._check_has_basis()``는 API 호출
    실패도 내부적으로 삼켜 '근거 없음'(None)으로 되돌리므로(2026-09-12 감사
    문서 §1-4에서 확인), 여기서 미리 확인하지 않으면 '키 없음'과 '진짜 근거
    없음'을 구분할 수 없다 — ``llm_verifier.py``의 동일 패턴을 그대로 재사용."""
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


def _empty(status: str, reason: str) -> dict:
    return {
        "resolver_status": status,
        "resolver_decision": None,
        "resolver_ksic_codes": [],
        "resolver_ksic_names": [],
        "resolver_evidence": [],
        "resolver_reason": reason,
    }


def resolve(text: str, *, call_fn=None, risk_signals: dict | None = None) -> dict:
    """Rule이 후보를 못 찾았을 때(또는 ML/Verifier가 전부 기각했을 때) 호출.

    ``risk_signals``는 ``rule_detectors.detect_resolver_risk_signals(text)``의
    출력을 그대로 전달하면 된다(orchestrator 책임) — 없으면 신호 없이 호출.

    반환 키: resolver_status(NOT_RUN 값은 호출부에서만 씀, 여기선 RUN/
    UNAVAILABLE/ERROR만 반환) / resolver_decision(SINGLE_INDUSTRY|
    MULTI_INDUSTRY|UNRESOLVED_REVIEW|ALL_INDUSTRIES|None) /
    resolver_ksic_codes / resolver_ksic_names / resolver_evidence /
    resolver_reason.

    v2(scope-first)부터 Resolver는 스스로 ``ALL_INDUSTRIES``를 판단해 반환할
    수 있다(R1이 원문에서 명시적 업종무관 근거를 직접 찾은 경우) — 이 경우도
    orchestrator가 ``auto_accept_eligible``을 항상 False로 강제하는 원칙은
    동일하게 적용된다.
    """
    fn = call_fn if call_fn is not None else _default_call_fn
    if fn is None:
        return _empty("UNAVAILABLE", "llm_match 모듈을 불러올 수 없음(의존성 없음)")

    if call_fn is None:  # 주입된 mock/stub은 사전점검을 건너뛴다(테스트용).
        reason = _preflight_unavailable_reason()
        if reason:
            return _empty("UNAVAILABLE", reason)

    try:
        raw = fn(text, risk_signals=risk_signals)
    except Exception as e:  # OPENAI_API_KEY 없음, 네트워크 오류 등 무엇이든
        return _empty("ERROR", f"{type(e).__name__}: {e}")

    if not isinstance(raw, dict):
        return _empty("ERROR", f"예상치 못한 llm_match 반환 타입: {type(raw).__name__}")

    scope = raw.get("scope")
    codes = [str(c) for c in (raw.get("확정코드") or [])]
    names = [str(n) for n in (raw.get("확정업종명") or [])]
    evidence = raw.get("근거") if isinstance(raw.get("근거"), dict) else {}
    reason_text = " / ".join(x for x in (raw.get("r1_reasoning", ""), raw.get("r2_reasoning", "")) if x)

    if scope == "ALL_INDUSTRIES":
        return {
            "resolver_status": "RUN", "resolver_decision": "ALL_INDUSTRIES",
            "resolver_ksic_codes": [], "resolver_ksic_names": [],
            "resolver_evidence": evidence, "resolver_reason": reason_text,
        }

    if scope == "SPECIFIC" and codes:
        decision = "MULTI_INDUSTRY" if len(codes) > 1 else "SINGLE_INDUSTRY"
        return {
            "resolver_status": "RUN", "resolver_decision": decision,
            "resolver_ksic_codes": codes, "resolver_ksic_names": names,
            "resolver_evidence": evidence, "resolver_reason": reason_text,
        }

    # scope == "UNRESOLVED_REVIEW", 또는 SPECIFIC인데 R3가 코드를 못 찾음,
    # 또는 예상치 못한 scope 값(형식 위반) — 전부 검토로 수렴(안전한 쪽).
    return {
        "resolver_status": "RUN", "resolver_decision": "UNRESOLVED_REVIEW",
        "resolver_ksic_codes": [], "resolver_ksic_names": [],
        "resolver_evidence": evidence, "resolver_reason": reason_text or "LLM이 업종 범위를 확정하지 못함",
    }
