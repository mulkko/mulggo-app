# -*- coding: utf-8 -*-
"""Candidate Verifier evidence gate 회귀 테스트 — V2.1(2026-09-13).

Frozen V2 최종평가 T1 16개 오답 재분류에서 확인된 실측 사례(PBLN_126301:
"우선 모집분야: 화장품‧뷰티 등"을 SUPPORT_TARGET으로 오인해 화장품
제조업(20423)을 SPECIFIC으로 잘못 확정)를 재현하고 수정을 확인한다.

실제 LLM은 호출하지 않는다 — ``ksic_core.llm_match._call_llm``만 mock한다.

실행: python -m unittest ksic_core.test_verifier_evidence_gate -v
"""
from __future__ import annotations

import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import json
import unittest
from unittest.mock import patch

from ksic_core import llm_match, llm_verifier, orchestrator


def verdict_response(code: str, verdict: str, evidence_role: str, quote: str, reasoning: str = "x") -> str:
    return json.dumps({
        "verdicts": [{"code": code, "verdict": verdict, "evidence_role": evidence_role,
                      "quote": quote, "reasoning": reasoning}],
        "suggested_refinement": [],
    })


class TestVerifierEvidenceGate(unittest.TestCase):
    # Test 1: evidence_role=REFERENCE_OR_EXAMPLE인 SUPPORTED는 승격 금지.
    def test_1_reference_context_blocks_supported(self):
        text = "참고 산업분류표: 제조업, 서비스업 등 다양한 업종 예시가 있습니다."
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("C", "SUPPORTED", "REFERENCE_OR_EXAMPLE", "제조업")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "C", "name": "제조업"}])
        self.assertEqual(out["verdicts"]["C"]["verdict"], "UNCERTAIN")

    # Test 2: evidence_role=EXCLUSION인 SUPPORTED는 승격 금지(동일 quote라도).
    def test_2_exclusion_context_blocks_supported(self):
        text = "단순 주류 유통·판매업 및 주점업은 해당하지 않음"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("5621", "SUPPORTED", "EXCLUSION", "주점업")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "5621", "name": "주점업"}])
        self.assertEqual(out["verdicts"]["5621"]["verdict"], "UNCERTAIN")

    # Test 3: evidence_role=SUPPORT_TARGET + 실제 원문 quote -> SPECIFIC 허용.
    def test_3_real_support_target_allows_specific(self):
        text = "지원대상: 여행업 등록 사업체만 신청 가능합니다."
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("75210", "SUPPORTED", "SUPPORT_TARGET",
                                                        "지원대상: 여행업 등록 사업체")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "75210", "name": "여행사업"}])
        self.assertEqual(out["verdicts"]["75210"]["verdict"], "SUPPORTED")

    # Test 4: 참고용 산업분류표(REFERENCE) -> SUPPORT_TARGET 자동 승격 금지
    # (실제 배포 경로: call_fn 주입 없이 기본 verify_candidates_with_llm을 탄다 —
    # 게이트가 llm_match 레벨에 있으므로 이 경로로만 검증 가능하다).
    def test_4_reference_table_never_auto_promoted_default_path(self):
        text = "참고 산업분류표: 제조업, 서비스업 등"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("C", "SUPPORTED", "REFERENCE_OR_EXAMPLE", "제조업")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "C", "name": "제조업"}])
        self.assertEqual(out["verdicts"]["C"]["verdict"], "UNCERTAIN")

    # Test 5: "지원대상 업종은 다음 표와 같음" -> 그 표는 SUPPORT_TARGET으로 사용 가능.
    def test_5_explicitly_labeled_target_table_allowed(self):
        text = "지원대상 업종은 다음 표와 같음: 제조업(C)"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("C", "SUPPORTED", "SUPPORT_TARGET",
                                                        "지원대상 업종은 다음 표와 같음")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "C", "name": "제조업"}])
        self.assertEqual(out["verdicts"]["C"]["verdict"], "SUPPORTED")

    # Test: PRIORITY_OR_PREFERENCE(우선 모집분야) -> 승격 금지. 실측 재현(PBLN_126301).
    def test_priority_or_preference_blocks_supported(self):
        text = "대상: 일본시장 진출을 희망하는 기업. 우선 모집분야: 화장품‧뷰티, 미용기기 등"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = verdict_response("20423", "SUPPORTED", "PRIORITY_OR_PREFERENCE",
                                                        "우선 모집분야: 화장품‧뷰티, 미용기기 등")
            out = llm_match.verify_candidates_with_llm(text, [{"code": "20423", "name": "화장품 제조업"}])
        self.assertEqual(out["verdicts"]["20423"]["verdict"], "UNCERTAIN")

    # Test 6: state integrity 유지(orchestrator 전체 경로, mock verifier).
    def test_6_state_integrity_preserved_when_verifier_downgrades(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_verify:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN"}
            mock_verify.return_value = {
                "llm_status": "RUN", "llm_decision": "UNRESOLVED_REVIEW",
                "llm_verified_codes": [], "llm_verified_names": [],
                "llm_evidence_quote": "", "llm_reason": "", "llm_candidate_consistent": False,
                "llm_raw_confidence": None, "llm_verdicts_detail": {}, "llm_suggested_refinement": [],
            }
            rule_result = {"확정코드": ["C"], "확정업종명": ["제조업"], "scope_decision": "SPECIFIC",
                            "scope_basis": "RULE_CANDIDATE", "auto_accept_eligible": False}
            out = orchestrator.orchestrate("dummy text", rule_result, use_llm_fallback=True)
        if out["scope_decision"] == "SPECIFIC":
            self.assertTrue(out["ksic_codes"])
        if out["scope_decision"] == "ALL_INDUSTRIES":
            self.assertEqual(out["ksic_codes"], [])
        if out["scope_decision"] == "UNRESOLVED_REVIEW":
            self.assertEqual(out["ksic_codes"], [])

    # Test 7: LLM unavailable에서도 예외 없음.
    def test_7_llm_unavailable_no_exception(self):
        text = "지원대상: 여행업 등록 사업체"
        try:
            out = llm_verifier.verify(text, ["75210"], ["여행사업"])  # 키 없음(neutralized)
        except Exception as e:  # noqa: BLE001
            self.fail(f"verify()가 예외를 던짐: {e}")
        self.assertEqual(out["llm_status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
