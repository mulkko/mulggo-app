# -*- coding: utf-8 -*-
"""scope_policy(HIGH confidence 역전 수정) 회귀 테스트.

pytest 없이 unittest만 쓴다(레포에 pytest 설정이 없어 stdlib로 통일).
실행: python -m unittest ksic_core.test_scope_policy -v
"""
from __future__ import annotations

import os

# 방어적 조치(2026-09-12e 사고 재발 방지) — 상세 사유는 test_orchestration.py 참고.
os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import unittest

import pandas as pd

from ksic_core.predict import predict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_CSV = os.path.join(ROOT, "data", "outputs", "full_raw_texts_1589.csv")


def _real_text(notice_id: str) -> str:
    df = pd.read_csv(RAW_CSV, dtype=str, encoding="utf-8-sig").fillna("")
    row = df[df["공고ID"] == notice_id]
    assert not row.empty, f"{notice_id} not found in {RAW_CSV}"
    return row.iloc[0]["원문"]


class TestScopeGating(unittest.TestCase):
    def test_1_single_direct_target_auto_accepts(self):
        """지원대상 문맥의 강한 기업표현(synonym) 단일 코드는 자동확정된다."""
        text = "지원대상: 제조기업 중 상시근로자 50인 미만 기업을 대상으로 한다."
        out = predict(text)
        self.assertEqual(out["ksic_codes"], ["C"])
        self.assertEqual(out["scope_decision"], "SPECIFIC")
        self.assertTrue(out["auto_accept_eligible"], out)
        self.assertFalse(out["needs_review"])

    def test_2_explicit_all_industries_auto_accepts(self):
        """명시적 업종무관 선언은 자동확정(ALL_INDUSTRIES)."""
        text = "지원대상 : 업종 무관, 상시근로자 10인 미만 중소기업"
        out = predict(text)
        self.assertEqual(out["ksic_codes"], [])
        self.assertEqual(out["scope_decision"], "ALL_INDUSTRIES")
        self.assertTrue(out["auto_accept_eligible"], out)
        self.assertFalse(out["needs_review"])

    def test_3_background_mention_not_auto_accepted(self):
        """실제 회귀 사례(PBLN_125827): 배경 서술의 '전문대학'을 지원대상으로
        오인해 HIGH 자동확정됐던 버그. 신정책에서는 검토로 가야 한다."""
        text = _real_text("PBLN_000000000125827")
        out = predict(text)
        self.assertFalse(out["auto_accept_eligible"], out)
        self.assertTrue(out["needs_review"])

    def test_4_excluded_industry_not_in_positive_codes(self):
        """제외업종 문맥의 업종명은 확정코드에 들어가면 안 된다(기존 동작 유지 확인)."""
        text = "지원대상: 제조기업\n지원 제외 업종: 여행업"
        out = predict(text)
        self.assertIn("C", out["ksic_codes"])
        excluded_names = [e.get("name") for e in out["excluded"]]
        self.assertTrue(any(n and "여행" in n for n in excluded_names), out["excluded"])
        self.assertNotIn("70", out["ksic_codes"])

    def test_5_and_6_large_reference_table_blocked(self):
        """실제 회귀 사례(PBLN_122893): 참고용 코드표에서 90개 코드가 잡혀
        HIGH·authoritative=True로 자동확정됐던 버그. 20개 이상은 무조건 검토."""
        text = _real_text("PBLN_000000000122893")
        out = predict(text)
        # 2026-09-12c: 최종 ksic_codes는 UNRESOLVED_REVIEW에서 비운다(상태불일치
        # 수정, scope_policy.normalize_final_result). 원본 90개 후보는 감사용
        # candidate_ksic_codes에만 남는다.
        self.assertEqual(out["ksic_codes"], [])
        self.assertGreaterEqual(len(out["candidate_ksic_codes"]), 20)
        self.assertEqual(out["scope_decision"], "UNRESOLVED_REVIEW")
        self.assertFalse(out["auto_accept_eligible"])
        self.assertTrue(out["needs_review"])

    def test_7_external_reference_without_inline_table_stays_in_review(self):
        """별표를 참조만 하고 본문에 실제 코드표가 없으면 특정업종으로 확정하지 않는다."""
        text = "본 사업의 지원대상 업종은 [별표1] 한국표준산업분류 코드표를 참조하시기 바랍니다."
        out = predict(text)
        self.assertEqual(out["ksic_codes"], [])
        self.assertTrue(out["needs_review"])
        self.assertFalse(out["auto_accept_eligible"])

    def test_8_multiple_genuine_targets_recognized_as_specific(self):
        """복수 업종이 실제 지원대상으로 명시되면 둘 다 잡히고 SPECIFIC으로 분류된다."""
        text = "지원대상 : 제조기업 및 건설업체"
        out = predict(text)
        self.assertEqual(set(out["ksic_codes"]), {"C", "F"})
        self.assertEqual(out["scope_decision"], "SPECIFIC")

    def test_hard_block_never_auto_accepts_20_plus(self):
        """scope_policy 단위 테스트: 후보 20개 이상은 화이트리스트를 절대 못 넘는다."""
        from ksic_core import scope_policy

        fake_result = {
            "확정코드": [str(i) for i in range(20)],
            "확정단계": "복수산업",
            "근거": {"매칭방식": "KSIC 코드 직접 명시", "authoritative": True},
            "ksic_confidence": "HIGH",
        }
        fields = scope_policy.build_scope_fields(fake_result)
        self.assertFalse(fields["auto_accept_eligible"])
        self.assertEqual(fields["scope_decision"], "UNRESOLVED_REVIEW")


if __name__ == "__main__":
    unittest.main()
