# -*- coding: utf-8 -*-
"""Rule → Whitelist → ML Gate → LLM(Verifier/Resolver) 최종 오케스트레이션.

2026-09-12e 리팩터링 — LLM 역할을 두 갈래로 명시적으로 분리했다.

  Candidate Verifier (ksic_core.llm_verifier)
    Rule이 이미 낸 후보 각각을 SUPPORTED/UNSUPPORTED/UNCERTAIN으로 검증만
    한다. 최종 채택 코드는 항상 Rule 후보의 부분집합이다.

  Fallback Resolver (ksic_core.llm_resolver)
    Rule이 후보를 하나도 못 찾았거나(그리고 명시적 전업종 근거·첨부누락도
    아닐 때), 또는 ML/Verifier가 Rule 후보를 전부 기각했을 때(그리고 여전히
    명시적 전업종 근거·첨부누락이 아닐 때) 마지막 수단으로 호출된다. KSIC
    마스터 전체를 대상으로 새 코드를 찾아낼 수 있다. Resolver가 찾은 코드는
    SPECIFIC으로 확정될 수 있지만 ``auto_accept_eligible``은 항상 False로
    강제한다(LLM 단독 자동확정 통로를 만들지 않는다).

핵심 원칙 변경(2026-09-12e): "Rule/ML/Verifier가 특정업종 후보를 못 찾거나
기각했다"는 사실 자체는 "이 공고가 전업종이다"의 증거가 아니다. 이전 버전은
`ML REJECT_SPECIFIC + document_sufficient` 또는 `Verifier 전원 UNSUPPORTED +
document_sufficient`만으로 곧장 ALL_INDUSTRIES를 확정했는데, 이는 "후보
기각"과 "업종무관 확정"을 혼동한 것이었다. 이제 그 두 경우는 먼저
Resolver에게 최후 기회를 준 뒤에도 아무것도 못 찾으면 UNRESOLVED_REVIEW로
보낸다 — ALL_INDUSTRIES는 오직 Rule이 명시적 근거를 찾았을 때
(``scope_policy.build_scope_fields``의 ``scope_basis ==
"EXPLICIT_ALL_INDUSTRIES"``)만 유지된다.

candidate provenance: 최종 결과에 ``candidate_source``를 추가해 코드의
출처를 구분한다 — "RULE"(Rule이 처음 만듦, 또는 코드 없음) /
"RULE_VERIFIED_BY_ML"(ML이 Rule 후보를 KEEP) / "RULE_VERIFIED_BY_LLM"
(Candidate Verifier가 Rule 후보 일부를 SUPPORTED로 확인) / "LLM_RESOLVER"
(Resolver가 새로 찾음).

``use_llm_fallback``(predict()에서 전달)은 이제 decide_industry() 내부의
legacy fallback이 아니라 **이 orchestrator의 Resolver/Verifier 실제 API
호출 여부**를 게이팅한다(predict.py 참고) — 기본값 False에서는 API 키가
있어도 실제 호출이 전혀 나가지 않는다. ML Gate는 이 플래그와 무관하게
항상 동작한다(로컬 추론이라 외부 API 호출/비용 문제가 없음).

역할 경계(변경 금지):
  Rule          = KSIC 후보 생성 + 명백한 문맥 판정 (ksic_core.decide_industry)
  Whitelist     = 자동확정 자격 심사 (ksic_core.scope_policy)
  ML Gate       = Rule 특정업종 후보가 유효한지 이진 판정. 코드를 새로 만들지 않음
  LLM Verifier  = Rule 후보 검증. 후보 밖 코드를 채택하지 않음
  LLM Resolver  = Rule/ML/Verifier가 실패했을 때만 새 KSIC를 탐색
  UNRESOLVED_REVIEW = 명시적 전업종 근거도, 특정업종 확정도 못 한 상태
                       (핵심 자료 누락 포함)

안전 원칙: Whitelist를 통과하지 못하면 ML/LLM이 뭐라고 하든
``needs_review``는 계속 True다. ML/LLM은 새로운 자동확정 통로가 아니라
검토 큐에 넘길 최종 코드셋/사유를 다듬는 역할만 한다(과거 confidence==HIGH
역전 사고를 반복하지 않기 위한 보수적 설계) — Resolver가 새로 찾은 코드도
예외 없이 이 원칙을 따른다.

``predict.py``가 유일한 호출부다. ``decide_industry()`` 직접 호출은
rule-only baseline 평가용으로만 쓴다(기존 scripts/29 등).
"""
from __future__ import annotations

from ksic_core import document_sufficiency, llm_resolver, llm_verifier, ml_gate_runtime, rule_detectors, scope_policy

_NOT_RUN_ML = {
    "ml_model_name": None, "ml_status": "NOT_RUN",
    "ml_valid_probability": None, "ml_decision": None,
}
_NOT_RUN_LLM = {
    "llm_status": "NOT_RUN", "llm_decision": None,
    "llm_verified_codes": [], "llm_verified_names": [],
    "llm_evidence_quote": "", "llm_reason": "",
    "llm_candidate_consistent": True, "llm_raw_confidence": None,
    "llm_verdicts_detail": {}, "llm_suggested_refinement": [],
}
_NOT_RUN_RESOLVER = {
    "resolver_status": "NOT_RUN", "resolver_decision": None,
    "resolver_ksic_codes": [], "resolver_ksic_names": [],
    "resolver_evidence": [], "resolver_reason": "",
}


def _run_resolver_or_review(text: str, use_llm_fallback: bool, reason_prefix: str,
                             risk_signals: dict | None = None):
    """Resolver를 호출하거나(게이트 켜졌을 때) UNRESOLVED_REVIEW로 보낸다.

    "Resolver도 못 찾았다"는 것 자체가 ALL_INDUSTRIES 근거가 아니므로(§8),
    실패/미호출/미발견 전부 UNRESOLVED_REVIEW로 수렴한다. Resolver v2(scope-first)
    부터는 Resolver 스스로 명시적 업종무관 근거를 찾아 ALL_INDUSTRIES를 반환할
    수 있는데, 이는 "후보를 못 찾음"과는 다른 경우(R1이 원문에서 실제 근거를
    찾은 경우)라 그대로 ALL_INDUSTRIES로 반영한다 — 다만 출처는 LLM_RESOLVER로
    남겨 auto_accept가 강제로 False가 되도록 한다(orchestrate() 끝의
    normalize_final_result 참고).

    반환: (codes, names, scope, candidate_source, final_reason, resolver_out)
    """
    if not use_llm_fallback:
        return ([], [], scope_policy.SCOPE_UNRESOLVED_REVIEW, scope_policy.SOURCE_RULE,
                f"{reason_prefix}_llm_fallback_disabled", dict(_NOT_RUN_RESOLVER))

    resolver_out = llm_resolver.resolve(text, risk_signals=risk_signals)
    if resolver_out["resolver_status"] != "RUN":
        return ([], [], scope_policy.SCOPE_UNRESOLVED_REVIEW, scope_policy.SOURCE_RULE,
                f"{reason_prefix}_resolver_unavailable", resolver_out)

    decision = resolver_out["resolver_decision"]
    codes = resolver_out["resolver_ksic_codes"]
    if decision in ("SINGLE_INDUSTRY", "MULTI_INDUSTRY") and codes:
        return (codes, resolver_out["resolver_ksic_names"], scope_policy.SCOPE_SPECIFIC,
                scope_policy.SOURCE_LLM_RESOLVER, f"{reason_prefix}_resolver_recovered_specific", resolver_out)

    if decision == "ALL_INDUSTRIES":
        return ([], [], scope_policy.SCOPE_ALL_INDUSTRIES, scope_policy.SOURCE_LLM_RESOLVER,
                f"{reason_prefix}_resolver_confirmed_all_industries", resolver_out)

    # UNRESOLVED_REVIEW / 코드 없음 — 전부 검토로.
    return ([], [], scope_policy.SCOPE_UNRESOLVED_REVIEW, scope_policy.SOURCE_RULE,
            f"{reason_prefix}_resolver_no_recovery", resolver_out)


def orchestrate(text: str, rule_result: dict | None, *, use_llm_fallback: bool = False) -> dict:
    """decide_industry(..., return_scope_result=True) 결과를 받아 최종 판정을 낸다.

    모든 routing 분기는 함수 끝에서 딱 한 번 ``scope_policy.normalize_final_result()``
    를 통과한다 — "SPECIFIC인데 ksic_codes==[]" 같은 상태 모순을 여기 한 곳에서
    막는다. 분기 도중에는 (codes, names, scope, candidate_source, reason) 제안값만
    계산하고, 실제 ``ksic_codes``/``scope_decision``/``service_category``/
    ``auto_accept_eligible``/``needs_human_review``/``candidate_source``는
    전부 정규화 함수의 출력이다.

    ``use_llm_fallback=False``(기본값)면 Resolver/Verifier 둘 다 실제 API를
    시도하지 않는다(호출 자체를 안 함, ``llm_status``/``resolver_status``는
    ``NOT_RUN``으로 남는다) — API 키가 있어도 호출 안 나감. ML Gate는 이
    플래그와 무관하게 항상 동작한다.

    반환 키: document_sufficient, attachment_missing, structural_anomaly,
    ml_model_name/ml_status/ml_valid_probability/ml_decision,
    llm_status/llm_decision/llm_verified_codes/llm_verified_names/
    llm_evidence_quote/llm_reason/llm_candidate_consistent/llm_raw_confidence/
    llm_verdicts_detail/llm_suggested_refinement,
    resolver_status/resolver_decision/resolver_ksic_codes/resolver_ksic_names/
    resolver_evidence/resolver_reason,
    scope_decision, service_category, ksic_codes, ksic_names,
    candidate_ksic_codes, candidate_ksic_names, candidate_source,
    auto_accept_eligible, needs_human_review, final_reason
    """
    result = rule_result or {}
    codes = [str(c) for c in (result.get("확정코드") or [])]
    names = [str(n) for n in (result.get("확정업종명") or [])]
    scope_decision = result.get("scope_decision") or scope_policy.SCOPE_ALL_INDUSTRIES
    scope_basis = result.get("scope_basis") or scope_policy.BASIS_NO_EVIDENCE
    auto_accept = bool(result.get("auto_accept_eligible"))
    candidate_count = len(codes)
    structural_anomaly = candidate_count >= scope_policy.HARD_BLOCK_CODES

    doc_flags = document_sufficiency.build_document_flags(text, result)
    document_sufficient = doc_flags["document_sufficient"]
    attachment_missing = doc_flags["attachment_missing"]
    risk_signals = rule_detectors.detect_resolver_risk_signals(text)

    ml_out = dict(_NOT_RUN_ML)
    llm_out = dict(_NOT_RUN_LLM)
    resolver_out = dict(_NOT_RUN_RESOLVER)
    # 분기 도중의 "제안값" — 아직 최종이 아니다. 끝에서 normalize_final_result가 확정한다.
    proposed_codes, proposed_names, proposed_scope = codes, names, scope_decision
    proposed_auto_accept = auto_accept
    candidate_source = scope_policy.SOURCE_RULE
    final_reason = "whitelist_auto_accept"

    if auto_accept:
        pass  # Whitelist가 이미 확정. ML/LLM 미호출.

    elif attachment_missing:
        proposed_scope = scope_policy.SCOPE_UNRESOLVED_REVIEW
        final_reason = "attachment_missing"

    elif structural_anomaly:
        proposed_scope = scope_policy.SCOPE_UNRESOLVED_REVIEW
        final_reason = "structural_anomaly"

    elif scope_decision == scope_policy.SCOPE_SPECIFIC and candidate_count >= 1:
        ml_out = ml_gate_runtime.run_ml_gate(text, result)

        if ml_out["ml_status"] != "RUN":
            final_reason = f"ml_{ml_out['ml_status'].lower()}_fallback_review"

        elif ml_out["ml_decision"] == "KEEP_SPECIFIC":
            candidate_source = scope_policy.SOURCE_RULE_VERIFIED_BY_ML
            final_reason = "ml_keep_specific"

        elif ml_out["ml_decision"] == "REJECT_SPECIFIC":
            # "현재 Rule 후보가 유효한 특정업종인가"에 대한 부정일 뿐,
            # "이 공고가 전업종이다"의 증거가 아니다(§2/§8). has_positive_codes
            # 단락평가를 우회해(target_scope_complete) 첨부누락 여부를 다시
            # 확인한 뒤에만 Resolver에게 최후 기회를 준다.
            recheck = document_sufficiency.target_scope_complete(text)
            if not recheck["target_scope_complete"]:
                proposed_scope = scope_policy.SCOPE_UNRESOLVED_REVIEW
                final_reason = "ml_reject_document_incomplete_review"
            else:
                (proposed_codes, proposed_names, proposed_scope,
                 candidate_source, final_reason, resolver_out) = _run_resolver_or_review(
                    text, use_llm_fallback, "ml_reject", risk_signals=risk_signals
                )

        else:  # UNCERTAIN
            if not use_llm_fallback:
                # 게이트 꺼짐 — Verifier 호출 자체를 안 함. Rule 후보 보수적 유지
                # (기존 "llm_unavailable_conservative_keep"과 동일한 결과값,
                # 다만 실제로 호출을 "시도했다가 실패"한 게 아니라 "안 함"이므로
                # 별도 사유 태그로 구분한다).
                final_reason = "llm_fallback_disabled_conservative_keep"
            else:
                llm_out = llm_verifier.verify(text, codes, names)
                if llm_out["llm_status"] != "RUN":
                    final_reason = "llm_unavailable_conservative_keep"
                elif llm_out["llm_decision"] == "SPECIFIC":
                    proposed_codes = llm_out["llm_verified_codes"]
                    proposed_names = llm_out["llm_verified_names"]
                    candidate_source = scope_policy.SOURCE_RULE_VERIFIED_BY_LLM
                    final_reason = "llm_verified_specific"
                elif llm_out["llm_decision"] == "ALL_INDUSTRIES":
                    # 전 후보 UNSUPPORTED = "이 후보들은 아니다"일 뿐, 전업종
                    # 확정 근거가 아니다(§8) — Resolver에게 최후 기회를 준다.
                    recheck = document_sufficiency.target_scope_complete(text)
                    if not recheck["target_scope_complete"]:
                        proposed_scope = scope_policy.SCOPE_UNRESOLVED_REVIEW
                        final_reason = "llm_all_unsupported_document_incomplete_review"
                    else:
                        (proposed_codes, proposed_names, proposed_scope,
                         candidate_source, final_reason, resolver_out) = _run_resolver_or_review(
                            text, use_llm_fallback, "verifier_rejected", risk_signals=risk_signals
                        )
                else:  # UNRESOLVED_REVIEW (일부 UNCERTAIN 검증, 또는 응답 파싱 실패)
                    proposed_scope = scope_policy.SCOPE_UNRESOLVED_REVIEW
                    final_reason = "llm_candidate_mismatch_review"

    else:
        # Rule 후보 없음(candidate_count==0). scope_decision은 build_scope_fields가
        # 이미 ALL_INDUSTRIES 또는 UNRESOLVED_REVIEW(특정불가)로 정해둔 상태다.
        if candidate_count != 0:
            final_reason = "rule_only"  # 구조상 도달 안 함(build_scope_fields 불변식상
            # scope_decision==SPECIFIC이면 항상 candidate_count>=1) — 방어적으로 유지.
        elif scope_basis == scope_policy.BASIS_EXPLICIT_ALL_INDUSTRIES:
            # Rule이 실제로 "전 업종/업종 무관" 같은 명시적 근거를 찾은 경우만
            # ALL_INDUSTRIES를 그대로 유지한다. Resolver는 부르지 않는다(Test 2).
            final_reason = "explicit_all_industries"
        elif not document_sufficient:
            # 텍스트 자체가 짧거나 깨져서(#NAME? 등) 판단이 불가능한 경우.
            # Resolver를 불러도 의미 있는 답을 못 낼 가능성이 커 호출하지 않는다.
            final_reason = "rule_only_review"
        else:
            # Case 1/3: 명시적 전업종 근거 없음 + 첨부누락 아님 + 문서 사용가능.
            # "Rule이 후보를 못 찾았다"는 그 자체로 ALL_INDUSTRIES 근거가
            # 아니므로(§2), Resolver에게 마지막 기회를 준다.
            (proposed_codes, proposed_names, proposed_scope,
             candidate_source, final_reason, resolver_out) = _run_resolver_or_review(
                text, use_llm_fallback, "no_rule_candidate", risk_signals=risk_signals
            )

    normalized = scope_policy.normalize_final_result(
        proposed_scope, proposed_codes, proposed_names, proposed_auto_accept,
        rule_codes=codes, rule_names=names, candidate_source=candidate_source,
    )

    return {
        "document_sufficient": document_sufficient,
        "attachment_missing": attachment_missing,
        "structural_anomaly": structural_anomaly,
        **ml_out,
        **llm_out,
        **resolver_out,
        **normalized,
        "final_reason": final_reason,
    }
