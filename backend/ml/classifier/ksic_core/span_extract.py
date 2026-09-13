"""2차 ML용 문맥 스팬 추출.

공고 원문에서 '업종을 가리키는 표현'이 나온 모든 위치를 스팬으로 뽑고,
그 스팬의 문맥 텍스트 + 1차 규칙엔진이 판정한 역할(weak label)을 함께 낸다.

역할 라벨 (span role) — 6종:
  지원대상   : 이 업종이 지원 대상 (규칙 role=positive)
  지원제외   : 이 업종은 제외      (role=excluded / partial_exclusion)
  제외예외   : 제외지만 예외 재허용 (role=exclusion_exception)
  제3자      : 협력·수행·구매·투자기관 등 신청기업 업종 아님 (role=non_target, 역할성 reason)
  참고예시   : 규모기준표·체크리스트·예시 나열 (role=non_target, 참고성 reason)
  무관       : 업종 언급이나 지원조건과 무관/확정불가 (role=neutral)

1차 규칙엔진 판정을 그대로 weak label로 쓰고, 사람 라벨(164 Gold 등)이 있으면
scripts/20_build_ml_span_dataset.py 에서 덮어써 dev/test 셋을 만든다.
"""
from __future__ import annotations

import re

from ksic_core.explicit_match import (
    SAFE_SYNONYMS, GENERIC_NAME_BLOCKLIST, NAME_LEVEL_ORDER,
    _load_ksic_index, _load_index_terms, _load_code_to_info_index,
)
from ksic_core.rule_detectors import (
    extract_explicit_ksic_details, extract_nts_codes_details,
    classify_occurrence_role,
)

CTX_BEFORE = 180
CTX_AFTER = 140

# non_target reason -> 제3자 / 참고예시 구분
_THIRD_PARTY_HINT = re.compile(
    r"협력|수행|구매|투자|시공|공급기|주관|운영기관|평가|시험기관|인증기관|연계기관|"
    r"바이어|판매채널|입점|숙박업소|직무|학력|전공|부서|기관명"
)


def _role_to_label(role: str, reason: str) -> str:
    if role == "positive":
        return "지원대상"
    if role in ("excluded", "partial_exclusion"):
        return "지원제외"
    if role == "exclusion_exception":
        return "제외예외"
    if role == "non_target":
        return "제3자" if _THIRD_PARTY_HINT.search(reason or "") else "참고예시"
    return "무관"   # neutral


def _window(text: str, s: int, e: int) -> str:
    seg = text[max(0, s - CTX_BEFORE): min(len(text), e + CTX_AFTER)]
    return re.sub(r"\s+", " ", seg).strip()


def _iter_name_occurrences(text: str):
    """공식 KSIC 명칭 + 안전동의어 + 색인어의 모든 등장 위치."""
    index = _load_ksic_index()
    names = []
    for level in NAME_LEVEL_ORDER:
        for name, code in index[level].items():
            if name in GENERIC_NAME_BLOCKLIST or len(name) < 3:
                continue
            names.append((name, code, "공식명"))
    for phrase, (official_names, _) in SAFE_SYNONYMS.items():
        names.append((phrase, official_names[0] if official_names else "", "동의어"))
    for term, entries in _load_index_terms().items():
        names.append((term, entries[0][0] if entries else "", "색인어"))

    names.sort(key=lambda x: -len(x[0]))
    occupied: list[tuple[int, int]] = []
    for name, code, kind in names:
        for m in re.finditer(re.escape(name), text):
            s, e = m.start(), m.end()
            if any(a <= s and e <= b for a, b in occupied):
                continue
            occupied.append((s, e))
            yield name, code, kind, s, e


def extract_industry_spans(text: str, 공고id: str = "") -> list[dict]:
    """원문 → 업종 표현 스팬 리스트."""
    if not text or not str(text).strip():
        return []
    text = str(text)
    valid = set(_load_code_to_info_index())
    out: list[dict] = []
    seen: set[tuple] = set()

    # 1) 직접 KSIC 코드
    for d in extract_explicit_ksic_details(text, valid_codes=valid):
        key = ("code", d["code"], d["start"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "공고ID": 공고id, "트리거유형": "ksic_code", "트리거값": d["code"],
            "start": d["start"], "end": d["end"],
            "span_text": _window(text, d["start"], d["end"]),
            "rule_role": d["role"], "rule_reason": d["reason"],
            "span_label": _role_to_label(d["role"], d["reason"]),
        })

    # 2) 국세청 코드
    for d in extract_nts_codes_details(text):
        key = ("nts", d["code"], d["start"])
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "공고ID": 공고id, "트리거유형": "nts_code", "트리거값": d["code"],
            "start": d["start"], "end": d["end"],
            "span_text": _window(text, d["start"], d["end"]),
            "rule_role": d["role"], "rule_reason": d["reason"],
            "span_label": _role_to_label(d["role"], d["reason"]),
        })

    # 3) 업종명 / 동의어 / 색인어
    for name, code, kind, s, e in _iter_name_occurrences(text):
        key = ("name", name, s)
        if key in seen:
            continue
        seen.add(key)
        role, reason = classify_occurrence_role(
            text, s, e, candidate_text=name, candidate_kind="name"
        )
        out.append({
            "공고ID": 공고id, "트리거유형": kind, "트리거값": name, "매핑코드": code,
            "start": s, "end": e,
            "span_text": _window(text, s, e),
            "rule_role": role, "rule_reason": reason,
            "span_label": _role_to_label(role, reason),
        })

    out.sort(key=lambda x: x["start"])
    for i, sp in enumerate(out):
        sp["span_id"] = f"{공고id}_{i:03d}"
    return out
