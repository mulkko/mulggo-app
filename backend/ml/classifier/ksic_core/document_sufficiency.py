# -*- coding: utf-8 -*-
"""문서 완전성 판정 — document_sufficient / attachment_missing.

orchestration(스코프 정책 다음 단계)에서 ML/LLM을 부를지, 아니면 원문 자체가
불완전해 기계적으로 판단할 수 없는 UNRESOLVED_REVIEW로 보낼지를 가른다.

이 판정은 순수 텍스트 휴리스틱이다 — 원문 안에 "별표/붙임/첨부가 실제 지원
업종 목록의 근거"라고 스스로 지목하는데 그 목록이 본문에 없으면
attachment_missing=True. 그 외 텍스트 길이/깨짐 여부로 document_sufficient를
판정한다.
"""
from __future__ import annotations

import re

MIN_SUFFICIENT_LEN = 80

_ATTACHMENT_REF_PATTERN = re.compile(
    r"(?:별표|붙임|별첨|첨부)\s*\d*[^\n]{0,30}(?:업종|대상)[^\n]{0,20}(?:참조|따름|의함|기준|한함|해당)"
    r"|(?:업종|대상)[^\n]{0,20}(?:별표|붙임|별첨|첨부)\s*\d*[^\n]{0,20}(?:참조|따름|의함|기준|한함|해당)"
)
_GARBLED_PATTERN = re.compile(r"[□▨�]{3,}")


def attachment_missing(text: str, has_positive_codes: bool) -> bool:
    """별표/붙임/첨부를 업종 근거로 지목했는데 실제 코드/업종이 본문에 없으면 True.

    본문에서 이미 실제 코드/업종을 찾았다면(has_positive_codes) 그 참조는
    이미 해소된 것이므로 누락이 아니다.
    """
    if not text or has_positive_codes:
        return False
    return bool(_ATTACHMENT_REF_PATTERN.search(text))


def document_sufficient(text: str, *, attachment_missing_flag: bool) -> bool:
    """본문만으로 판단을 시도해도 되는 최소 조건."""
    if not text or len(text.strip()) < MIN_SUFFICIENT_LEN:
        return False
    if attachment_missing_flag:
        return False
    if _GARBLED_PATTERN.search(text):
        return False
    return True


def build_document_flags(text: str, result: dict | None) -> dict:
    """decide_industry() 결과와 원문으로 document_sufficient/attachment_missing을 계산."""
    codes = (result or {}).get("확정코드") or []
    missing = attachment_missing(text, has_positive_codes=bool(codes))
    sufficient = document_sufficient(text, attachment_missing_flag=missing)
    return {"document_sufficient": sufficient, "attachment_missing": missing}


def target_scope_complete(text: str) -> dict:
    """Rule의 확정코드 유무와 무관하게, 원문 자체가 업종범위 판단에 완전한지
    다시 검사한다.

    ``attachment_missing()``은 ``has_positive_codes=True``면 무조건 False를
    반환한다(감사 2026-09-12 문서 §2-2 사실 3 참고) — Rule이 코드를 찾았다는
    사실만으로 "그 첨부 참조는 이미 해소됐다"고 보기 때문이다. 하지만 ML
    Gate나 Candidate Verifier가 그 코드를 사후에 기각(REJECT/전원 UNSUPPORTED)
    하면, "코드가 있었다"는 전제 자체가 더 이상 유효하지 않다. 이 함수는 그
    시점에 ``has_positive_codes=False``로 강제 재계산해 첨부/별표 누락 여부를
    다시 확인한다 — 기존 ``attachment_missing()``/``document_sufficient()``
    로직 자체는 수정하지 않고 그대로 재사용한다.
    """
    missing_recheck = attachment_missing(text, has_positive_codes=False)
    text_usable = document_sufficient(text, attachment_missing_flag=False)
    complete = document_sufficient(text, attachment_missing_flag=missing_recheck)
    return {
        "document_text_usable": text_usable,
        "attachment_missing_recheck": missing_recheck,
        "target_scope_complete": complete,
    }
