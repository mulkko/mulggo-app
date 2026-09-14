# -*- coding: utf-8 -*-
"""Rule evidence-role(EXCLUSION/REFERENCE/THIRD_PARTY/SUPPORT_TARGET) 판정
회귀 테스트 — ML Gate FP 9건 진단(ml_gate_false_positive_report.md)에서
확인된 두 가지 실제 버그를 재현하고 수정을 확인한다.

절대 원칙: notice ID/특정 문구를 조건문에 하드코딩하지 않는다 — 정규식
경계(section boundary clustering, 부정 표현 확장)만 일반화해서 고쳤다.

실행: python -m unittest ksic_core.test_evidence_role -v
"""
from __future__ import annotations

import unittest

from ksic_core import decide_industry, rule_detectors


class TestOccurrenceRoleClassification(unittest.TestCase):
    # 1. "[별표] 지원 제외 업종" 뒤 업종 목록 -> excluded
    def test_appendix_exclusion_table_classified_as_excluded(self):
        text = (
            "1. 사업개요\n지원대상: 관내 소상공인\n"
            "붙임 1 소상공인 지원에 관한 조례 [별표] 지원 제외대상\n"
            "해당 기업의 주된 업종 분류기호\n"
            "46331 주류 도매업\n46333 담배 도매업\n"
        )
        pos = text.find("46331")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("46331"), candidate_text="46331", candidate_kind="code"
        )
        self.assertEqual(role, "excluded")

    # 1-b. 실측 재현: 두 붙임 제목이 한 줄로 깨져 붙는 경우(붙임1=제외, 붙임2=무관 참고표)
    def test_appendix_exclusion_survives_adjacent_flattened_boundary(self):
        text = (
            "지원대상: 관내 소상공인\n"
            "붙임 1 소상공인 지원에 관한 조례 [별표] 지원 제외대상 붙임 2 소상공인 업종별 평균매출액 및 상시근로자 기준\n"
            "해당 기업의 주된 업종 분류기호 매출액 기준\n"
            "46331 주류 도매업 1. 코크스 제조업 C19\n"
        )
        pos = text.find("46331")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("46331"), candidate_text="46331", candidate_kind="code"
        )
        # 다른 가드(_looks_like_strong_reference_section)가 먼저 "non_target"으로
        # 잡을 수도 있다 — 어느 쪽이든 positive 후보로 새지만 않으면 안전하다.
        # 실제 문서 단위 검증은 test_124699_no_longer_all_19_codes_kept_as_support_target에서 한다.
        self.assertIn(role, ("excluded", "non_target"))
        self.assertNotEqual(role, "positive")

    # 2. "주점업은 해당하지 않음" -> excluded
    def test_negation_trailing_phrase_classified_as_excluded(self):
        text = "◦ (양조기업) 주류를 직접 제조·생산하는 기업 - 단순 주류 유통·판매업 및 주점업은 해당하지 않음"
        pos = text.find("주점업")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("주점업"), candidate_text="주점업", candidate_kind="name"
        )
        self.assertEqual(role, "excluded")

    # 3. "지원대상: 여행업 등록 사업체" -> positive(SUPPORT_TARGET에 대응)
    def test_support_target_still_recognized(self):
        text = "지원대상: 여행업 등록 사업체만 신청 가능합니다."
        pos = text.find("여행업")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("여행업"), candidate_text="여행업", candidate_kind="name"
        )
        self.assertEqual(role, "positive")

    # 4. "예: 제조업, 서비스업" -> non_target(참고/예시)
    def test_reference_example_classified_non_target(self):
        text = "지원 가능 업종 예시: 제조업, 서비스업 등 다양한 업종이 참여할 수 있습니다."
        pos = text.find("제조업")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("제조업"), candidate_text="제조업", candidate_kind="name"
        )
        self.assertIn(role, ("non_target", "neutral"))

    # 5. "수행기관은 정보통신업체" -> non_target(제3자)
    def test_third_party_role_classified_non_target(self):
        text = "본 사업의 수행기관은 정보통신업체인 (주)OO시스템이 맡는다."
        pos = text.find("정보통신업체")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("정보통신업체"), candidate_text="정보통신업체", candidate_kind="name"
        )
        self.assertIn(role, ("non_target", "neutral"))

    # 회귀 방지: 정상 SUPPORT_TARGET(신청대상 문맥의 명시적 코드)은 계속 positive.
    def test_direct_code_under_target_header_still_positive(self):
        text = "지원업종: 아래 코드에 해당하는 사업자\n10111 도축업"
        pos = text.find("10111")
        role, reason = rule_detectors.classify_occurrence_role(
            text, pos, pos + len("10111"), candidate_text="10111", candidate_kind="code"
        )
        self.assertEqual(role, "positive")


class TestEndToEndFPCasesFixed(unittest.TestCase):
    """ml_gate_false_positive_report.md에서 확인한 실측 FP 2건이
    Rule 단계에서부터 candidate_evidence_role이 바뀌는지 확인(재호출 없이
    결정론적 decide_industry만 재실행, LLM 없음)."""

    def setUp(self):
        import pandas as pd
        import os
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        raw = pd.read_csv(os.path.join(root, "data", "outputs", "full_raw_texts_1589.csv"),
                           dtype=str, encoding="utf-8-sig").fillna("")
        self.text_map = dict(zip(raw["공고ID"], raw["원문"]))

    def test_124699_no_longer_all_19_codes_kept_as_support_target(self):
        text = self.text_map["PBLN_000000000124699"]
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        codes = (out or {}).get("확정코드") or []
        # 수정 전: 19개 제외업종 코드가 그대로 확정코드로 살아남았다.
        # 수정 후: 최소한 그 excluded 코드들은 확정코드에서 빠져야 한다.
        excluded_examples = {"46331", "46333", "5621"}
        self.assertFalse(excluded_examples & set(codes),
                          f"제외업종 코드가 여전히 확정코드에 남아있음: {set(codes) & excluded_examples}")

    def test_125715_jujeomeop_no_longer_positive_candidate(self):
        text = self.text_map["PBLN_000000000125715"]
        out = decide_industry.decide_industry(text, use_llm_fallback=False, return_scope_result=True)
        codes = (out or {}).get("확정코드") or []
        self.assertNotIn("5621", codes, "명시적으로 제외된 주점업(5621)이 여전히 후보로 남아있음")


if __name__ == "__main__":
    unittest.main()
