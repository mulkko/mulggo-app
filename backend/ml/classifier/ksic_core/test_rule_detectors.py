# -*- coding: utf-8 -*-
"""rule_detectors.py의 위험신호 탐지 회귀 테스트 — Resolver Phase 2(2026-09-13).

절대 원칙: 코드는 rule_detectors.py 자체만 실행한다(LLM 없음, 결정론적).
새 API 호출 없음.

실행: python -m unittest ksic_core.test_rule_detectors -v
"""
from __future__ import annotations

import re
import unittest

from ksic_core import rule_detectors


class TestNoRestrictionPatternBoundary(unittest.TestCase):
    """전\\s*업종 정규식 경계 버그(Resolver Phase 1에서 발견) 재현/수정 확인."""

    def _matches(self, text: str) -> bool:
        pattern = rule_detectors.NO_RESTRICTION_PATTERNS[1]  # "(?<![가-힣])전\s*업종"
        return bool(re.search(pattern, text))

    def test_explicit_all_industries_positive(self):
        for text in ("전 업종", "전업종 대상", "전 업종 지원 가능", "지원대상: 전업종"):
            with self.subTest(text=text):
                self.assertTrue(self._matches(text), f"{text!r}는 매칭돼야 함")

    def test_compound_word_false_positive_rejected(self):
        # 버그 재현 사례: "불건전업종" 내부의 "전"+"업종"이 우연히 매칭되면 안 됨.
        for text in ("불건전업종은 지원 제외", "도박 등 불건전 업종 제외"):
            with self.subTest(text=text):
                self.assertFalse(self._matches(text), f"{text!r}는 매칭되면 안 됨(합성어 오탐)")


class TestOrConditionMixedScope(unittest.TestCase):
    def test_mixed_or_bare_entity_vs_named_industry_detected(self):
        # 실측 사례(PBLN_118093)와 동일한 구조: 한쪽은 업종 무관 일반 기업,
        # 한쪽만 실제 KSIC 업종명("제조업").
        text = "신청일 현재 서초구에 주사무소를 둔 중소기업 또는 서초구에 공장등록 된 제조업 영위 기업"
        self.assertTrue(rule_detectors._or_condition_with_open_scope(text))

    def test_both_branches_named_industries_not_flagged(self):
        # 양쪽 다 실제 업종명이면 "한쪽만 업종"이 아니므로 mixed-OR이 아니다.
        text = "지원대상: 제조업 영위 기업 또는 도매 및 소매업 영위 기업"
        self.assertFalse(rule_detectors._or_condition_with_open_scope(text))

    def test_no_or_connector_not_flagged(self):
        text = "제조업 및 정보통신업 영위기업만 신청 가능"
        self.assertFalse(rule_detectors._or_condition_with_open_scope(text))

    def test_explicit_no_restriction_near_or_still_detected(self):
        text = "업종 무관 소상공인 또는 특정 요건을 갖춘 예비창업자"
        self.assertTrue(rule_detectors._or_condition_with_open_scope(text))


class TestDetectResolverRiskSignals(unittest.TestCase):
    def test_open_ended_list_flag(self):
        sig = rule_detectors.detect_resolver_risk_signals("외식업, 이미용업, 세탁업 등 개인서비스업종 지원")
        self.assertTrue(sig["open_ended_list_detected"])

    def test_or_condition_flag_uses_fixed_detector(self):
        sig = rule_detectors.detect_resolver_risk_signals(
            "신청일 현재 서초구에 주사무소를 둔 중소기업 또는 서초구에 공장등록 된 제조업 영위 기업"
        )
        self.assertTrue(sig["or_condition_with_open_scope_detected"])

    def test_explicit_no_restriction_not_fooled_by_compound_word(self):
        sig = rule_detectors.detect_resolver_risk_signals("도박 등 불건전 업종은 매출채권팩토링 지원 제외")
        self.assertFalse(sig["explicit_no_restriction_present"])


if __name__ == "__main__":
    unittest.main()
