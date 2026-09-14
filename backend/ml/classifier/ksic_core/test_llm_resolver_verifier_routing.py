# -*- coding: utf-8 -*-
"""LLM Resolver/Verifier 역할 분리 + orchestrator 라우팅 리팩터링 회귀 테스트.

리팩터링 프롬프트의 12개 테스트 시나리오를 그대로 구현한다. 외부 LLM은
전부 mock/stub으로만 부른다 — 실제 API는 호출하지 않는다.

실행: python -m unittest ksic_core.test_llm_resolver_verifier_routing -v
"""
from __future__ import annotations

import os

# 방어적 조치(2026-09-12e 사고 재발 방지) — 저장소에 .env가 있으면 이 파일이
# import하는 ksic_core 모듈들이 실제 API 키를 읽어들일 수 있다. import보다
# 먼저 빈 문자열로 못박아 어떤 테스트도 실제 과금 호출을 내지 않게 한다.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import unittest
from unittest.mock import patch

import pandas as pd

from ksic_core import llm_resolver, llm_verifier, ml_gate_runtime, orchestrator, scope_policy
from ksic_core.predict import predict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV = os.path.join(ROOT, "data", "outputs", "full_raw_texts_1589.csv")

# Whitelist를 통과 못하는 약한 name/synonym 매칭 텍스트 (candidate_count>=1).
WEAK_PROXIMITY_TEXT = (
    "2026년 지역 소상공인 지원사업 안내입니다. " * 3
    + "지원대상: 소규모 사업체 중 여행업 관련 업체를 지원합니다. 신청 서류는 자율 양식입니다. "
    + "문의사항은 담당부서로 연락 바랍니다. 접수 기간은 공고일로부터 30일입니다."
)

# Rule 후보가 전혀 없는(candidate_count==0) 일반 문서.
NO_CANDIDATE_TEXT = (
    "2026년 지역 소상공인 지원사업 안내입니다. " * 3
    + "신청 서류는 자율 양식입니다. 문의사항은 담당부서로 연락 바랍니다. "
    + "접수 기간은 공고일로부터 30일입니다. 세부내용은 아래와 같습니다."
)

ATTACHMENT_MISSING_TEXT = (
    "본 사업의 지원 업종은 붙임2 참조 바랍니다. 신청 서류는 자율 양식입니다."
)


def _real_text(notice_id: str) -> str:
    df = pd.read_csv(RAW_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    row = df[df["공고ID"] == notice_id]
    assert not row.empty
    return row.iloc[0]["원문"]


class TestLLMResolverVerifierRouting(unittest.TestCase):
    # Test 1: Rule이 정확한 특정업종 후보 생성 -> whitelist 통과 -> Resolver 미호출
    def test_1_rule_exact_candidate_whitelist_pass_no_resolver(self):
        with patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            out = predict("지원대상: 제조기업 중 상시근로자 50인 미만 기업을 대상으로 한다.")
            self.assertFalse(mock_resolver.called)
        self.assertEqual(out["ksic_codes"], ["C"])
        self.assertTrue(out["auto_accept_eligible"])
        self.assertEqual(out["resolver_status"], "NOT_RUN")

    # Test 2: Rule 후보 없음 + 명시적 "전 업종" -> ALL_INDUSTRIES, Resolver 미호출
    def test_2_no_candidate_explicit_all_industries_no_resolver(self):
        with patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            out = predict("지원대상 : 전 업종, 상시근로자 10인 미만 중소기업")
            self.assertFalse(mock_resolver.called)
        self.assertEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertEqual(out["ksic_codes"], [])
        self.assertEqual(out["resolver_status"], "NOT_RUN")

    # Test 3: Rule 후보 없음 + 명시적 업종무관 근거 없음 + 문서 사용가능 -> Resolver 호출
    def test_3_no_candidate_no_explicit_evidence_calls_resolver(self):
        with patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_resolver.return_value = dict(llm_resolver._empty("RUN", "no basis"))
            mock_resolver.return_value["resolver_decision"] = "UNRESOLVED_REVIEW"
            predict(NO_CANDIDATE_TEXT, use_llm_fallback=True)
            self.assertTrue(mock_resolver.called)

    # Test 4: Rule 후보 없음 + "붙임2 참조" + 붙임 없음 -> Resolver가 억지 확정
    # 하지 않고 UNRESOLVED_REVIEW (실제로는 attachment_missing이 먼저 걸려
    # Resolver 자체가 호출되지 않는다 — 불필요한 API 호출 방지).
    def test_4_attachment_missing_no_forced_confirmation(self):
        with patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            out = predict(ATTACHMENT_MISSING_TEXT, use_llm_fallback=True)
            self.assertFalse(mock_resolver.called)
        self.assertTrue(out["attachment_missing"])
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["ksic_codes"], [])

    # Test 5: Rule 후보 있음 -> ML KEEP -> Rule 후보 유지
    def test_5_ml_keep_preserves_rule_candidate(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.95, "ml_decision": "KEEP_SPECIFIC"}
            out = predict(WEAK_PROXIMITY_TEXT)
        self.assertGreaterEqual(len(out["ksic_codes"]), 1)
        self.assertEqual(out["candidate_source"], "RULE_VERIFIED_BY_ML")

    # Test 6: Rule 후보 있음 -> ML REJECT -> 단순히 ALL_INDUSTRIES로 바로 확정
    # 하지 않음 -> Resolver 또는 적절한 fallback(UNRESOLVED_REVIEW) 진입
    def test_6_ml_reject_does_not_immediately_confirm_all_industries(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC"}
            out = predict(WEAK_PROXIMITY_TEXT)
        self.assertNotEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")

    # Test 7: Rule 후보 있음 -> ML UNCERTAIN -> Candidate Verifier 호출(게이트 켜짐)
    def test_7_ml_uncertain_calls_verifier(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_verify:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN"}
            mock_verify.return_value = dict(llm_verifier._unavailable("test"))
            predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertTrue(mock_verify.called)

    # Test 8: Candidate Verifier — Rule=[C,E], C=SUPPORTED, E=UNSUPPORTED -> final=C
    def test_8_verifier_keeps_only_supported_candidate(self):
        def fake_fn(text, candidates):
            return {
                "verdicts": {
                    "C": {"verdict": "SUPPORTED", "quote": "제조업 영위기업", "reasoning": "직접 명시"},
                    "E": {"verdict": "UNSUPPORTED", "quote": "", "reasoning": "근거 없음"},
                },
                "suggested_refinement": [],
            }
        out = llm_verifier.verify("제조업 영위기업 대상", ["C", "E"], ["제조업", "환경업"], call_fn=fake_fn)
        self.assertEqual(out["llm_verified_codes"], ["C"])
        self.assertNotIn("E", out["llm_verified_codes"])
        self.assertEqual(out["llm_decision"], "SPECIFIC")

    # Test 9: Resolver가 새 KSIC(75210)를 생성 -> final SPECIFIC 가능,
    # candidate_source=LLM_RESOLVER, auto_accept_eligible=False, needs_review=True
    def test_9_resolver_recovers_new_code_never_auto_accepted(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC"}
            mock_resolver.return_value = {
                "resolver_status": "RUN", "resolver_decision": "SINGLE_INDUSTRY",
                "resolver_ksic_codes": ["75210"], "resolver_ksic_names": ["여행사업"],
                "resolver_evidence": {}, "resolver_reason": "test",
            }
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
        self.assertEqual(out["scope_decision"], "SPECIFIC")
        self.assertEqual(out["ksic_codes"], ["75210"])
        self.assertEqual(out["candidate_source"], "LLM_RESOLVER")
        self.assertFalse(out["auto_accept_eligible"])
        self.assertTrue(out["needs_review"])

    # Test 10: LLM API unavailable -> predict() 예외 없음 -> 보수적 fallback
    def test_10_llm_api_unavailable_no_exception(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN"}
            try:
                out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)  # 키 없음(neutralized)
            except Exception as e:  # noqa: BLE001
                self.fail(f"predict()가 예외를 던짐: {e}")
        self.assertEqual(out["llm_status"], "UNAVAILABLE")
        self.assertTrue(out["needs_review"])

    # Test 11: 빈 문자열/#NAME?/#VALUE!/#REF!/#N/A -> ALL_INDUSTRIES 자동확정 금지
    def test_11_corrupted_input_never_auto_confirms_all_industries(self):
        for corrupted in ("", "#NAME?", "#VALUE!", "#REF!", "#N/A"):
            with self.subTest(corrupted=corrupted):
                out = predict(corrupted)
                self.assertTrue(out["needs_review"], f"{corrupted!r} -> needs_review는 항상 True여야 함")
                self.assertFalse(out["auto_accept_eligible"])
                # ALL_INDUSTRIES로 "자동확정"되지 않는다 = auto_accept_eligible=False로
                # 이미 보장됨(scope_decision이 ALL_INDUSTRIES/UNRESOLVED_REVIEW 무엇이든
                # 사람 검토 없이 서비스에 나가지 않는다는 뜻).
                self.assertEqual(out["ksic_codes"], [])

    # Test 12: 한 predict() 요청 안에서 Resolver/Verifier 중복 호출 없음
    def test_12_no_duplicate_llm_calls_within_one_request(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_verify, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN"}
            mock_verify.return_value = dict(llm_verifier._unavailable("test"))
            predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertEqual(mock_verify.call_count, 1)
            self.assertEqual(mock_resolver.call_count, 0)  # UNCERTAIN 경로는 Verifier만, Resolver 안 부름

        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_verify, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC"}
            mock_resolver.return_value = dict(llm_resolver._empty("RUN", "no basis"))
            mock_resolver.return_value["resolver_decision"] = "UNRESOLVED_REVIEW"
            predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertEqual(mock_resolver.call_count, 1)
            self.assertEqual(mock_verify.call_count, 0)  # REJECT 경로는 Resolver만, Verifier 안 부름

        # legacy decide_industry 내부 fallback도 predict() 경로에서는 호출되지
        # 않는다. decide_industry.py는 `from ksic_core.llm_match import
        # match_ksic_by_llm`로 참조를 자기 네임스페이스에 들여왔으므로,
        # 실제로 호출될 위치인 ksic_core.decide_industry.match_ksic_by_llm을
        # patch해야 한다(ksic_core.llm_match.match_ksic_by_llm을 patch하면
        # 이미 들여온 참조는 안 바뀜).
        with patch("ksic_core.decide_industry.match_ksic_by_llm") as mock_legacy:
            predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertFalse(mock_legacy.called)

    # Test 13 (2026-09-12g, Resolver v2): Resolver가 R1에서 명시적 업종무관
    # 근거를 스스로 찾아 ALL_INDUSTRIES를 반환하면 그대로 반영하되,
    # candidate_source=LLM_RESOLVER로 남아 auto_accept는 여전히 False.
    def test_13_resolver_confirmed_all_industries_never_auto_accepted(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {"ml_model_name": "t", "ml_status": "RUN",
                                     "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC"}
            mock_resolver.return_value = {
                "resolver_status": "RUN", "resolver_decision": "ALL_INDUSTRIES",
                "resolver_ksic_codes": [], "resolver_ksic_names": [],
                "resolver_evidence": {}, "resolver_reason": "업종 무관 명시 발견",
            }
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
        self.assertEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertEqual(out["ksic_codes"], [])
        self.assertEqual(out["candidate_source"], "LLM_RESOLVER")
        self.assertFalse(out["auto_accept_eligible"])
        self.assertTrue(out["needs_review"])


if __name__ == "__main__":
    unittest.main()
