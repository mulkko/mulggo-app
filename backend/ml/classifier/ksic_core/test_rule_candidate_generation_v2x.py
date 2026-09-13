# -*- coding: utf-8 -*-
"""V2.x Rule candidate-generation 회귀 테스트 — "원전기업" 색인어 추가
(`data/processed/ksic_index_terms.csv`)가 실측 RULE_CANDIDATE_MISS
(PBLN_125902)를 고치는지, 그리고 기존 정상 케이스를 안 망치는지 확인한다.

실행: python -m unittest ksic_core.test_rule_candidate_generation_v2x -v
"""
from __future__ import annotations

import unittest

from ksic_core import decide_industry


class TestNuclearIndexTerm(unittest.TestCase):
    def test_1_wonjeon_gieop_now_generates_candidate(self):
        text = "지원대상: 부산시 내 소재 원전기업(선정기업 기술공유대학사업 협력기업 참여 必)"
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        self.assertIn("35111", out.get("확정코드") or [])

    def test_2_normal_manufacturing_case_unaffected(self):
        text = "지원대상: 제조기업 중 상시근로자 50인 미만 기업을 대상으로 한다."
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        self.assertEqual(out.get("확정코드"), ["C"])

    def test_3_unrelated_text_no_false_trigger(self):
        text = "지원대상: 관내 소상공인 중 카드수수료 지원을 희망하는 사업자"
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        self.assertNotIn("35111", (out or {}).get("확정코드") or [])

    def test_4_wonjeon_haeche_different_context_not_confused(self):
        # "원전해체"(decommissioning)는 "원전기업"과 다른 표현 — 색인어 exact match만
        # 허용되므로("원전기업" 문자열 자체가 있어야 함) 여기서 오탐 안 남을 확인.
        text = "지원대상: 원전해체 산업 진출을 준비 중인 기업"
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        codes = (out or {}).get("확정코드") or []
        self.assertNotIn("35111", codes)


if __name__ == "__main__":
    unittest.main()
