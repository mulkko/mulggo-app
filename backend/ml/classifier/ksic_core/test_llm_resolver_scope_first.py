# -*- coding: utf-8 -*-
"""LLM Resolver v2(scope-first: R1 범위판단 -> R2 세부유형판단 -> R3 코드생성) 회귀 테스트.

57건 실측 진단(resolver_57case_diagnostic_report.md)에서 확인된 "자유응답은
반드시 업종 하나를 답해야 한다"는 구조적 압력을 없애기 위한 재설계다.
실제 LLM은 호출하지 않는다 — ``ksic_core.llm_match._call_llm``만 mock한다.

실행: python -m unittest ksic_core.test_llm_resolver_scope_first -v
"""
from __future__ import annotations

import os

os.environ["OPENAI_API_KEY"] = ""
os.environ["GOOGLE_API_KEY"] = ""

import json
import unittest
from unittest.mock import patch

from ksic_core import llm_match, llm_resolver, rule_detectors


class TestResolveScopeFirst(unittest.TestCase):
    # R1이 ALL_INDUSTRIES면 R2/R3(코드생성) 없이 즉시 반환.
    def test_r1_all_industries_short_circuits(self):
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({"scope": "ALL_INDUSTRIES", "reasoning": "업종 무관 명시"})
            out = llm_match.resolve_scope_first("업종 무관, 전 업종 지원")
        self.assertEqual(out["scope"], "ALL_INDUSTRIES")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 1)  # R1만 호출됨

    # R1이 UNRESOLVED_REVIEW면 R2/R3 없이 즉시 반환.
    def test_r1_unresolved_review_short_circuits(self):
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({"scope": "UNRESOLVED_REVIEW", "reasoning": "근거 없음"})
            out = llm_match.resolve_scope_first("신청서류는 붙임 참조")
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 1)

    # R1==SPECIFIC(evidence gate 통과), R2==OPEN_ENDED_MULTI(개방형 나열) -> 코드 생성 안 하고 UNRESOLVED_REVIEW.
    def test_r2_open_ended_multi_never_generates_codes(self):
        text = "외식업, 이미용업, 세탁업 등 개인서비스업종 지원"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "개인서비스업종", "reasoning": "업종 언급 있음"}),
                json.dumps({"scope_type": "OPEN_ENDED_MULTI", "reasoning": "등으로 열린 나열"}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["scope_type"], "OPEN_ENDED_MULTI")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 2)  # R3(자유응답)까지 안 감

    # R1==SPECIFIC(evidence gate 통과), R2==UNRESOLVED_REVIEW(OR조건 등) -> 코드 생성 안 함.
    def test_r2_unresolved_review_never_generates_codes(self):
        text = "중소기업 또는 업종 무관 소상공인 대상"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "", "reasoning": "업종 언급 있음"}),
                json.dumps({"scope_type": "UNRESOLVED_REVIEW", "reasoning": "OR조건 중 업종무관 대안 존재"}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 2)

    # R2==BROAD_SECTOR_AMBIGUOUS -> R3 진입 금지(신규, Phase 2).
    def test_r2_broad_sector_ambiguous_never_generates_codes(self):
        text = "해양수산 관련 기업 대상 지원사업"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "해양수산", "reasoning": "관련 분야 언급"}),
                json.dumps({"scope_type": "BROAD_SECTOR_AMBIGUOUS", "reasoning": "여러 KSIC에 걸친 광역 분야"}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["scope_type"], "BROAD_SECTOR_AMBIGUOUS")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 2)  # R3 미호출

    # R1==SPECIFIC(evidence gate 통과), R2==SINGLE_INDUSTRY -> R3(기존 로직 재사용)로 실제 코드 생성.
    def test_r2_single_industry_generates_code_via_existing_r3(self):
        text = "신청대상: 제조업 영위 기업만 신청 가능"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "제조업", "reasoning": "제조업 명시"}),
                json.dumps({"scope_type": "SINGLE_INDUSTRY", "reasoning": "단일 업종"}),
                json.dumps({"industries": [
                    {"name": "제조업", "quote": "제조업 영위 기업만 신청 가능",
                     "reasoning": "신청자격에 제조업 명시"}
                ]}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "SPECIFIC")
        self.assertEqual(out["scope_type"], "SINGLE_INDUSTRY")
        self.assertEqual(out["확정코드"], ["C"])
        self.assertEqual(mock_call.call_count, 3)

    # R1==SPECIFIC(evidence gate 통과), R2==MULTI_INDUSTRY -> R3가 여러 개 반환.
    def test_r2_multi_industry_generates_multiple_codes(self):
        text = "신청대상: 제조업 영위 기업 또는 도매 및 소매업 영위 기업"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "제조업/도매 및 소매업", "reasoning": "복수 업종 명시"}),
                json.dumps({"scope_type": "MULTI_INDUSTRY", "reasoning": "제조업 또는 도소매업"}),
                json.dumps({"industries": [
                    {"name": "제조업", "quote": "제조업 영위 기업", "reasoning": "명시"},
                    {"name": "도매 및 소매업", "quote": "도매 및 소매업 영위 기업", "reasoning": "명시"},
                ]}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "SPECIFIC")
        self.assertCountEqual(out["확정코드"], ["C", "G"])

    # [Phase 2 신규] SPECIFIC인데 eligibility_quote가 비어있으면 evidence gate가 차단.
    def test_evidence_gate_blocks_specific_without_quote(self):
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({"scope": "SPECIFIC", "eligibility_quote": "",
                                                  "evidence_role": "SUPPORT_TARGET", "reasoning": "근거 없음인데 SPECIFIC"})
            out = llm_match.resolve_scope_first("아무 산업 얘기나 하는 텍스트")
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(mock_call.call_count, 1)  # R2/R3 진입 안 함

    # [Phase 2 신규] quote가 원문에 실제로 없으면(할루시네이션) 차단.
    def test_evidence_gate_blocks_specific_with_hallucinated_quote(self):
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({
                "scope": "SPECIFIC", "eligibility_quote": "원문에 없는 지어낸 문장입니다",
                "evidence_role": "SUPPORT_TARGET", "reasoning": "환각"})
            out = llm_match.resolve_scope_first("실제 원문은 이것과 전혀 다른 내용")
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")

    # [Phase 2 신규] quote는 있지만 evidence_role이 SUPPORT_TARGET이 아니면(예: SUBJECT_ONLY) 차단.
    def test_evidence_gate_blocks_subject_only_role(self):
        text = "AI 도입 지원사업 참여기업 모집"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({
                "scope": "SPECIFIC", "eligibility_quote": "AI 도입 지원사업",
                "evidence_role": "SUBJECT_ONLY", "industry_expression": "AI",
                "reasoning": "사업명일 뿐 신청자격 아님"})
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")

    # [Phase 2 신규] evidence gate를 제대로 통과하는 정상 케이스(기존 true recovery 보호).
    def test_evidence_gate_allows_valid_support_target(self):
        text = "지원대상: 여행업 등록 사업체"
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": "지원대상: 여행업 등록 사업체",
                            "evidence_role": "SUPPORT_TARGET", "industry_expression": "여행업",
                            "reasoning": "신청자격에 여행업 명시"}),
                json.dumps({"scope_type": "SINGLE_INDUSTRY", "reasoning": "단일 업종"}),
                json.dumps({"industries": [{"name": "여행사업", "quote": "지원대상: 여행업 등록 사업체",
                                            "reasoning": "여행업 명시"}]}),
            ]
            out = llm_match.resolve_scope_first(text)
        self.assertEqual(out["scope"], "SPECIFIC")
        self.assertTrue(out["확정코드"])

    # [Phase 2 신규, 테스트 9] open_ended_list_detected=True인데 LLM이 SINGLE_INDUSTRY로
    # 답하면 deterministic guard가 코드 레벨에서 강제로 차단한다(prompt에 맡기지 않음).
    # PBLN_125620 실측 사례(risk_signal은 켜졌지만 LLM이 무시)를 재현한다.
    def test_deterministic_guard_blocks_single_when_open_ended_flag_set(self):
        text = "외식업, 이미용업, 세탁업 등 개인서비스업종 지원"
        risk_signals = rule_detectors.detect_resolver_risk_signals(text)
        self.assertTrue(risk_signals["open_ended_list_detected"])
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "개인서비스업종", "reasoning": "업종 언급 있음"}),
                # LLM이 risk_note를 보고도(참고만 하라는 지시라서) 그대로 SINGLE_INDUSTRY로 답함
                json.dumps({"scope_type": "SINGLE_INDUSTRY", "reasoning": "이미용업으로 확정"}),
            ]
            out = llm_match.resolve_scope_first(text, risk_signals=risk_signals)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["확정코드"], [])
        self.assertEqual(mock_call.call_count, 2)  # R3(코드생성) 진입 자체가 코드로 차단됨

    # [Phase 2 버그 재현+수정 확인] R2가 MULTI_INDUSTRY라고 답해도 R3가 이름 중
    # 하나만 remap에 성공하면 최종 코드가 1개로 좁혀진다 — 이 경로도 차단해야
    # 한다(실측 PBLN_125620: R2 라벨만 보는 가드는 이 경로를 놓쳤었다).
    def test_deterministic_guard_blocks_multi_narrowed_to_single_by_r3(self):
        text = "외식업, 이미용업, 세탁업 등 개인서비스업종 지원"
        risk_signals = rule_detectors.detect_resolver_risk_signals(text)
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "개인서비스업종", "reasoning": "업종 언급 있음"}),
                json.dumps({"scope_type": "MULTI_INDUSTRY", "reasoning": "여러 업종 나열"}),
                # R3: 3개 이름을 냈지만 KSIC 정확매칭은 하나만 성공한다고 가정
                json.dumps({"industries": [
                    {"name": "음식점업", "quote": "외식업", "reasoning": "명시"},
                    {"name": "존재하지않는업종명", "quote": "이미용업", "reasoning": "명시"},
                    {"name": "존재하지않는업종명2", "quote": "세탁업", "reasoning": "명시"},
                ]}),
            ]
            out = llm_match.resolve_scope_first(text, risk_signals=risk_signals)
        self.assertEqual(out["scope"], "UNRESOLVED_REVIEW")
        self.assertEqual(out["확정코드"], [])

    # deterministic guard는 open_ended_list_detected가 없을 땐(false) 개입하지 않는다.
    def test_deterministic_guard_does_not_block_when_flag_absent(self):
        text = "신청대상: 제조업 영위 기업만 신청 가능"
        risk_signals = rule_detectors.detect_resolver_risk_signals(text)
        self.assertFalse(risk_signals["open_ended_list_detected"])
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.side_effect = [
                json.dumps({"scope": "SPECIFIC", "eligibility_quote": text, "evidence_role": "SUPPORT_TARGET",
                            "industry_expression": "제조업", "reasoning": "제조업 명시"}),
                json.dumps({"scope_type": "SINGLE_INDUSTRY", "reasoning": "단일 업종"}),
                json.dumps({"industries": [{"name": "제조업", "quote": text, "reasoning": "명시"}]}),
            ]
            out = llm_match.resolve_scope_first(text, risk_signals=risk_signals)
        self.assertEqual(out["scope"], "SPECIFIC")
        self.assertEqual(out["확정코드"], ["C"])

    # risk_signals가 프롬프트에 참고 문구로 실제로 들어가는지 확인(내용 신뢰 강제는 아님).
    def test_risk_signals_are_injected_into_r1_prompt(self):
        risk_signals = rule_detectors.detect_resolver_risk_signals(
            "외식업, 이미용업, 세탁업 등 개인서비스업종 지원"
        )
        self.assertTrue(risk_signals["open_ended_list_detected"])
        with patch("ksic_core.llm_match._call_llm") as mock_call:
            mock_call.return_value = json.dumps({"scope": "UNRESOLVED_REVIEW", "reasoning": "x"})
            llm_match.resolve_scope_first("외식업, 이미용업, 세탁업 등 개인서비스업종 지원",
                                           risk_signals=risk_signals)
        prompt_sent = mock_call.call_args[0][0]
        self.assertIn("개방형 나열", prompt_sent)


class TestResolverWithScopeFirst(unittest.TestCase):
    # llm_resolver.resolve()가 resolve_scope_first의 ALL_INDUSTRIES를 그대로 전달.
    def test_resolver_passes_through_all_industries(self):
        def fake_fn(text, risk_signals=None):
            return {"scope": "ALL_INDUSTRIES", "scope_type": None, "확정코드": [], "확정업종명": [],
                    "근거": {}, "r1_reasoning": "업종 무관 명시", "r2_reasoning": ""}
        out = llm_resolver.resolve("업종 무관 지원", call_fn=fake_fn)
        self.assertEqual(out["resolver_status"], "RUN")
        self.assertEqual(out["resolver_decision"], "ALL_INDUSTRIES")
        self.assertEqual(out["resolver_ksic_codes"], [])

    # SPECIFIC인데 코드가 비어있으면(방어적 상황) UNRESOLVED_REVIEW로 수렴.
    def test_resolver_specific_without_codes_falls_back_to_review(self):
        def fake_fn(text, risk_signals=None):
            return {"scope": "SPECIFIC", "scope_type": "SINGLE_INDUSTRY", "확정코드": [], "확정업종명": [],
                    "근거": {}, "r1_reasoning": "", "r2_reasoning": ""}
        out = llm_resolver.resolve("dummy", call_fn=fake_fn)
        self.assertEqual(out["resolver_decision"], "UNRESOLVED_REVIEW")


if __name__ == "__main__":
    unittest.main()
