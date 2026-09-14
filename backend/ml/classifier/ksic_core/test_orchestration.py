# -*- coding: utf-8 -*-
"""ML Gate + LLM Verifier orchestration 회귀 테스트 (요청사항 11, 1~13 시나리오).

외부 LLM은 mock/stub으로만 부른다 — 실제 OpenAI 호출은 하지 않는다(그래도
llm_verifier가 API 키 없음을 예외 없이 처리하는지는 진짜로 확인한다, 테스트 11).

실행: python -m unittest ksic_core.test_orchestration -v
"""
from __future__ import annotations

import os

# 방어적 조치(2026-09-12e 사고 재발 방지): 저장소에 .env가 있으면 아래 ksic_core
# import 시점에 llm_verifier/llm_resolver가 load_dotenv(override=False)로 실제
# API 키를 읽어들인다. 이 테스트 파일은 use_llm_fallback=True 시나리오도
# 다루므로, import보다 먼저 키를 빈 문자열로 못박아 절대 실제 API가 나가지
# 않게 한다(override=False라 이미 세팅된 빈 문자열은 .env로 덮어써지지 않음).
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import unittest
from unittest.mock import patch

import pandas as pd

from ksic_core import llm_resolver, llm_verifier, ml_gate_runtime, orchestrator, scope_policy
from ksic_core.predict import predict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV = os.path.join(ROOT, "data", "outputs", "full_raw_texts_1589.csv")

# ML Gate가 호출되게 만드는 문서: name/synonym 근접 매칭이라 Whitelist는 통과 못함.
WEAK_PROXIMITY_TEXT = (
    "2026년 지역 소상공인 지원사업 안내입니다. " * 3
    + "지원대상: 소규모 사업체 중 여행업 관련 업체를 지원합니다. 신청 서류는 자율 양식입니다. "
    + "문의사항은 담당부서로 연락 바랍니다. 접수 기간은 공고일로부터 30일입니다."
)


def _real_text(notice_id: str) -> str:
    df = pd.read_csv(RAW_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    row = df[df["공고ID"] == notice_id]
    assert not row.empty
    return row.iloc[0]["원문"]


class TestOrchestration(unittest.TestCase):
    # 1. 명시적 업종무관 Whitelist 통과 -> ALL_INDUSTRIES 자동확정, ML/LLM 미호출
    def test_01_explicit_all_industries_skips_ml_llm(self):
        out = predict("지원대상 : 업종 무관, 상시근로자 10인 미만 중소기업")
        self.assertEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertFalse(out["needs_review"])
        self.assertEqual(out["ml_status"], "NOT_RUN")
        self.assertEqual(out["llm_status"], "NOT_RUN")

    # 2. 직접 KSIC + SUPPORT_TARGET + 소수 코드 -> SPECIFIC 자동확정, ML/LLM 미호출
    def test_02_whitelisted_specific_skips_ml_llm(self):
        out = predict("지원대상: 제조기업 중 상시근로자 50인 미만 기업을 대상으로 한다.")
        self.assertEqual(out["ksic_codes"], ["C"])
        self.assertEqual(out["scope_decision"], "SPECIFIC")
        self.assertFalse(out["needs_review"])
        self.assertEqual(out["ml_status"], "NOT_RUN")
        self.assertEqual(out["llm_status"], "NOT_RUN")

    # 3. name/synonym 기반 후보 + Whitelist 미통과 -> ML Gate 호출
    def test_03_non_whitelisted_specific_calls_ml_gate(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN",
            }
            predict(WEAK_PROXIMITY_TEXT)
            self.assertTrue(mock_ml.called)

    # 4. ML KEEP -> Rule KSIC 후보 유지
    def test_04_ml_keep_specific_preserves_rule_codes(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.95, "ml_decision": "KEEP_SPECIFIC",
            }
            out = predict(WEAK_PROXIMITY_TEXT)
            self.assertEqual(out["ml_decision"], "KEEP_SPECIFIC")
            self.assertTrue(len(out["ksic_codes"]) >= 1)
            self.assertTrue(out["needs_review"])  # Whitelist 미통과라 여전히 검토

    # 5. (2026-09-12e 재설계) ML REJECT만으로는 더 이상 곧장 ALL_INDUSTRIES가
    #    되지 않는다 — "후보 기각"과 "업종무관 확정"은 다른 사실이다(spec §2/§8).
    #    게이트를 명시적으로 끄면(use_llm_fallback=False) Resolver도 안 부르고
    #    UNRESOLVED_REVIEW로 보낸다. (2026-09-12f: predict() 기본값이 True로
    #    바뀌어서 "기본값"이 아니라 명시적으로 꺼야 이 경로를 검증할 수 있다.)
    def test_05_ml_reject_does_not_auto_confirm_all_industries(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC",
            }
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=False)
            self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
            self.assertEqual(out["ksic_codes"], [])
            self.assertEqual(out["final_reason"], "ml_reject_llm_fallback_disabled")
            self.assertEqual(out["resolver_status"], "NOT_RUN")  # Resolver 호출 자체를 안 함
            self.assertTrue(out["needs_review"])

    # 5b. use_llm_fallback=True + Resolver도 못 찾음 -> 여전히 ALL_INDUSTRIES로
    #     확정하지 않고 UNRESOLVED_REVIEW (spec Test 6).
    def test_05b_ml_reject_with_resolver_finding_nothing_stays_review(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC",
            }
            mock_resolver.return_value = dict(llm_resolver._empty("RUN", "no basis"))
            mock_resolver.return_value["resolver_decision"] = "UNRESOLVED_REVIEW"
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertTrue(mock_resolver.called)
            self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
            self.assertEqual(out["ksic_codes"], [])
            self.assertNotEqual(out["scope_decision"], "ALL_INDUSTRIES")

    # 5c. use_llm_fallback=True + Resolver가 새 KSIC를 복구 -> SPECIFIC,
    #     candidate_source=LLM_RESOLVER, auto_accept_eligible=False (spec Test 9).
    def test_05c_ml_reject_with_resolver_recovering_specific(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_resolver.resolve") as mock_resolver:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.05, "ml_decision": "REJECT_SPECIFIC",
            }
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

    # 6. ML UNCERTAIN + use_llm_fallback=True -> Candidate Verifier 호출
    def test_06_ml_uncertain_calls_verifier_when_fallback_enabled(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_llm:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN",
            }
            mock_llm.return_value = dict(llm_verifier._unavailable("test"))
            predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=True)
            self.assertTrue(mock_llm.called)

    # 6b. ML UNCERTAIN + use_llm_fallback=False(명시적으로 끔) -> Verifier 호출
    # 자체를 안 함. (2026-09-12f) predict()의 기본값이 True로 바뀌어서 "기본값"
    # 대신 명시적으로 False를 넘겨 게이트-꺼짐 경로를 계속 검증한다.
    def test_06b_ml_uncertain_skips_verifier_when_fallback_disabled(self):
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml, \
             patch("ksic_core.llm_verifier.verify") as mock_llm:
            mock_ml.return_value = {
                "ml_model_name": "test", "ml_status": "RUN",
                "ml_valid_probability": 0.5, "ml_decision": "UNCERTAIN",
            }
            out = predict(WEAK_PROXIMITY_TEXT, use_llm_fallback=False)
            self.assertFalse(mock_llm.called)
            self.assertEqual(out["llm_status"], "NOT_RUN")
            self.assertEqual(out["final_reason"], "llm_fallback_disabled_conservative_keep")
            self.assertTrue(out["needs_review"])

    # 7. LLM이 후보 밖 KSIC를 제안해도 그 코드는 최종 채택되지 않고
    #    suggested_refinement로만 분리된다 (2026-09-12d candidate verifier 재설계).
    def test_07_llm_new_code_goes_to_suggestion_not_final(self):
        def fake_fn(text, candidates):
            self.assertEqual(candidates, [{"code": "C", "name": "제조업"}])
            return {
                "verdicts": {"C": {"verdict": "UNSUPPORTED", "quote": "", "reasoning": "무관"}},
                "suggested_refinement": [{"code": "F", "name": "건설업", "quote": "", "reasoning": "참고용"}],
            }
        out = llm_verifier.verify("dummy", ["C"], ["제조업"], call_fn=fake_fn)
        self.assertEqual(out["llm_verified_codes"], [])
        self.assertNotIn("F", out["llm_verified_codes"])
        self.assertFalse(out["llm_candidate_consistent"])  # C가 UNSUPPORTED로 기각됨
        self.assertEqual([s["code"] for s in out["llm_suggested_refinement"]], ["F"])

    # 8. attachment_missing=True -> LLM 미호출, UNRESOLVED_REVIEW
    def test_08_attachment_missing_skips_llm(self):
        text = "본 사업의 지원대상 업종은 [별표1] 한국표준산업분류 코드표를 참조하시기 바랍니다."
        with patch("ksic_core.llm_verifier.verify") as mock_llm:
            out = predict(text)
            self.assertFalse(mock_llm.called)
        self.assertTrue(out["attachment_missing"])
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["llm_status"], "NOT_RUN")

    # 9. candidate_count>=20 또는 table_reference_anomaly -> ML 미호출, 자동확정 불가
    def test_09_large_candidate_table_skips_ml_and_blocks_auto_accept(self):
        text = _real_text("PBLN_000000000122893")
        with patch("ksic_core.ml_gate_runtime.run_ml_gate") as mock_ml:
            out = predict(text)
            self.assertFalse(mock_ml.called)
        self.assertTrue(out["structural_anomaly"])
        self.assertFalse(out["auto_accept_eligible"])
        self.assertTrue(out["needs_review"])

    # 10. ML 모델 파일 없음 -> 예외 없이 ml_status=UNAVAILABLE
    def test_10_missing_ml_artifact_is_unavailable_not_exception(self):
        orig_path = ml_gate_runtime.ARTIFACT_PATH
        orig_art, orig_err = ml_gate_runtime._artifact, ml_gate_runtime._load_error
        ml_gate_runtime.ARTIFACT_PATH = os.path.join(ROOT, "no_such_dir", "no_such_file.joblib")
        ml_gate_runtime._artifact = None
        ml_gate_runtime._load_error = None
        try:
            result = ml_gate_runtime.run_ml_gate("아무 텍스트", {"확정코드": ["C"]})
            self.assertEqual(result["ml_status"], "UNAVAILABLE")
            self.assertIsNone(result["ml_decision"])
        finally:
            ml_gate_runtime.ARTIFACT_PATH = orig_path
            ml_gate_runtime._artifact, ml_gate_runtime._load_error = orig_art, orig_err

    # 11. LLM API key 없음 -> 예외 없이 llm_status=UNAVAILABLE (실제 llm_match 경로, mock 아님)
    def test_11_missing_api_key_is_unavailable_not_exception(self):
        had_key = os.environ.pop("OPENAI_API_KEY", None)
        try:
            out = llm_verifier.verify("지원대상: 여행업", ["70"], ["여행사업"])
            self.assertEqual(out["llm_status"], "UNAVAILABLE")
            self.assertIsNone(out["llm_decision"])
        finally:
            if had_key is not None:
                os.environ["OPENAI_API_KEY"] = had_key

    # 12. 기존 JSON 필드와 CLI/batch 출력 호환성 유지
    def test_12_backward_compatible_json_fields(self):
        out = predict("지원대상: 제조기업")
        for key in ("service_category", "ksic_codes", "ksic_names", "stage", "confidence",
                    "needs_review", "excluded", "evidence", "schema_version"):
            self.assertIn(key, out)
        self.assertIn(out["service_category"], ("특정업종대상", "전업종노출"))

    # 13. G/H embedding 불가 시 runtime이 정상적으로 fallback
    def test_13_embedding_unavailable_runtime_falls_back(self):
        import joblib
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            fake_path = os.path.join(td, "fake_gate.joblib")
            joblib.dump({"model_name": "G(test)", "feature_mode": "embed", "embed_model_name": "fake/none"}, fake_path)

            orig_path = ml_gate_runtime.ARTIFACT_PATH
            orig_art, orig_err = ml_gate_runtime._artifact, ml_gate_runtime._load_error
            ml_gate_runtime.ARTIFACT_PATH = fake_path
            ml_gate_runtime._artifact = None
            ml_gate_runtime._load_error = None
            try:
                with patch("ksic_core.ml_gate_runtime._get_embedder", return_value=None):
                    result = ml_gate_runtime.run_ml_gate("지원대상: 여행업", {"확정코드": ["70"]})
                self.assertEqual(result["ml_status"], "UNAVAILABLE")
            finally:
                ml_gate_runtime.ARTIFACT_PATH = orig_path
                ml_gate_runtime._artifact, ml_gate_runtime._load_error = orig_art, orig_err


if __name__ == "__main__":
    unittest.main()
