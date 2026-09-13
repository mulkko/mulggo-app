# -*- coding: utf-8 -*-
"""최종 상태 불변조건 회귀 테스트 (2026-09-12c).

버그: orchestrator가 ML REJECT_SPECIFIC 등에서 ksic_codes는 비웠는데
scope_decision은 예전 값(SPECIFIC)으로 남겨서 "SPECIFIC인데 코드 없음" 같은
모순 상태가 나갔다(`ml_llm_orchestration_case_audit.csv` 11/110건 확인됨).
`scope_policy.normalize_final_result()`가 모든 분기의 최종 조립을 맡는 단일
검문소가 됐는지 확인한다.

실행: python -m unittest ksic_core.test_final_state_consistency -v
"""
from __future__ import annotations

import os

# 방어적 조치(2026-09-12e 사고 재발 방지) — 상세 사유는 test_orchestration.py 참고.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import unittest
from unittest.mock import patch

from ksic_core import scope_policy
from ksic_core.predict import predict

WEAK_PROXIMITY_TEXT = (
    "2026년 지역 소상공인 지원사업 안내입니다. " * 3
    + "지원대상: 소규모 사업체 중 여행업 관련 업체를 지원합니다. 신청 서류는 자율 양식입니다. "
    + "문의사항은 담당부서로 연락 바랍니다. 접수 기간은 공고일로부터 30일입니다."
)


def _assert_consistent(tc: unittest.TestCase, out: dict):
    """모든 predict() 결과가 지켜야 할 상태 불변조건(스펙 §2)."""
    if out["scope_decision"] == "ALL_INDUSTRIES":
        tc.assertEqual(out["service_category"], "전업종노출")
        tc.assertEqual(out["ksic_codes"], [])
        tc.assertEqual(out["ksic_names"], [])
    elif out["scope_decision"] == "SPECIFIC":
        tc.assertEqual(out["service_category"], "특정업종대상")
        tc.assertGreaterEqual(len(out["ksic_codes"]), 1)
        tc.assertEqual(len(out["ksic_codes"]), len(out["ksic_names"]))
    else:  # UNRESOLVED_REVIEW
        tc.assertTrue(out["needs_review"])
        tc.assertFalse(out["auto_accept_eligible"])
        tc.assertEqual(out["ksic_codes"], [])

    if out["auto_accept_eligible"]:
        tc.assertFalse(out["needs_review"])
        tc.assertIn(out["scope_decision"], ("SPECIFIC", "ALL_INDUSTRIES"))
    else:
        tc.assertTrue(out["needs_review"])


class TestFinalStateConsistency(unittest.TestCase):
    # A. (2026-09-12e 재설계) ML REJECT만으로는 더 이상 ALL_INDUSTRIES가 되지
    # 않는다 — "후보 기각" ≠ "업종무관 확정"(리팩터링 spec §2/§8). 기본 게이트
    # (use_llm_fallback=False)에서는 UNRESOLVED_REVIEW로 가되, 상태 불변조건
    # (codes==[], service_category=전업종노출)은 여전히 지켜져야 한다.
    def test_A_ml_reject_alone_is_clean_unresolved_review_not_all_industries(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC"}
            out = predict(WEAK_PROXIMITY_TEXT)
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["ksic_codes"], [])
        self.assertEqual(out["ksic_names"], [])
        self.assertEqual(out["service_category"], "전업종노출")  # UNRESOLVED_REVIEW도 이 값으로 수렴(하위호환)
        _assert_consistent(self, out)

    # B. ML KEEP -> SPECIFIC, codes>=1
    def test_B_ml_keep_is_clean_specific(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.95, "ml_decision": "KEEP_SPECIFIC"}
            out = predict(WEAK_PROXIMITY_TEXT)
        self.assertEqual(out["scope_decision"], "SPECIFIC")
        self.assertGreaterEqual(len(out["ksic_codes"]), 1)
        _assert_consistent(self, out)

    # C. ML UNCERTAIN + use_llm_fallback=False(명시적으로 끔) -> Verifier 호출
    # 자체를 안 함(2026-09-12e) -> 모순 없이 보수적 유지. (2026-09-12f)
    # predict()의 기본값이 True로 바뀌어서 "기본값"이 아니라 명시적으로
    # False를 넘겨 게이트-꺼짐 경로를 계속 검증한다.
    def test_C_ml_uncertain_llm_unavailable_is_consistent(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN"}
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=False)
        self.assertEqual(out["llm_status"], "NOT_RUN")
        _assert_consistent(self, out)
        self.assertTrue(out["needs_review"])

    # D. structural_anomaly -> UNRESOLVED_REVIEW, codes=[], candidate_ksic_codes에 원본 보존
    def test_D_structural_anomaly_moves_codes_to_candidate_field(self):
        import pandas as pd
        import os
        raw = pd.read_csv(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "outputs", "full_raw_texts_1589.csv"),
            dtype=str, encoding="utf-8-sig",
        ).fillna("")
        text = raw[raw["공고ID"] == "PBLN_000000000122893"].iloc[0]["원문"]
        out = predict(text)
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["ksic_codes"], [])
        self.assertFalse(out["auto_accept_eligible"])
        self.assertTrue(out["needs_review"])
        self.assertGreaterEqual(len(out["candidate_ksic_codes"]), 20)  # 원본 Rule 후보는 감사용으로 보존
        _assert_consistent(self, out)

    # E. attachment_missing -> UNRESOLVED_REVIEW, LLM 0회
    def test_E_attachment_missing_is_clean_unresolved_review(self):
        text = "본 사업의 지원대상 업종은 [별표1] 한국표준산업분류 코드표를 참조하시기 바랍니다."
        with patch("ksic_core.llm_verifier.verify") as mock_llm:
            out = predict(text)
            self.assertFalse(mock_llm.called)
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertIn(out["llm_status"], ("NOT_RUN",))
        _assert_consistent(self, out)

    # F. Whitelist 자동확정 -> auto_accept_eligible True면 needs_review False
    def test_F_whitelist_auto_accept_implies_no_review(self):
        out = predict("지원대상: 제조기업 중 상시근로자 50인 미만 기업을 대상으로 한다.")
        self.assertTrue(out["auto_accept_eligible"])
        self.assertFalse(out["needs_review"])
        _assert_consistent(self, out)

    def test_normalize_final_result_downgrades_codeless_specific(self):
        """단위 테스트: SPECIFIC인데 codes가 비면 강제로 ALL_INDUSTRIES로 강등된다."""
        out = scope_policy.normalize_final_result("SPECIFIC", [], [], False)
        self.assertEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertEqual(out["ksic_codes"], [])

    def test_normalize_final_result_preserves_candidates_for_review(self):
        out = scope_policy.normalize_final_result(
            "UNRESOLVED_REVIEW", ["C"], ["제조업"], False,
            rule_codes=["C", "F"], rule_names=["제조업", "건설업"],
        )
        self.assertEqual(out["ksic_codes"], [])
        self.assertEqual(out["candidate_ksic_codes"], ["C", "F"])
        self.assertFalse(out["auto_accept_eligible"])


if __name__ == "__main__":
    unittest.main()
