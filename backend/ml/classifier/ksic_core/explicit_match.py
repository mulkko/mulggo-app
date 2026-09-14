"""결정적 KSIC 매칭.

공개 함수
---------
- match_ksic_by_name(text)
- match_ksic_by_code(text)
- match_ksic_by_nts_code(text)

설계 원칙
---------
* '등장'이 아니라 '지원대상 문맥'에서만 이름 매칭을 확정한다.
* 직접 명시 KSIC는 원문 코드 수준을 그대로 보존한다. 부모/자식 코드를
  자동 생성하지 않는다.
* 국세청 코드 1:N 크로스워크는 자동 HIGH가 아니라 LOW/사람검토로 남긴다.
* 석유화학→20111, 블록체인→58222 같은 의미 확장형 동의어는 제거했다.
  검증 메모에서 과잉추론으로 확인된 유형이기 때문이다.
"""

from __future__ import annotations

import csv
import os
import re
from collections import defaultdict

from ksic_core.rule_detectors import (
    classify_occurrence_role,
    extract_explicit_ksic_details,
    extract_nts_codes_details,
)


KSIC_CLEAN_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "ksic_clean_v2.csv"
)
NTS_TO_KSIC_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "nts_to_ksic.csv"
)
# G1: KSIC 색인어(예시업종) 사전. 공식명·안전동의어로 못 잡는 구어체 표현
# (게임기업, 승강기 부품, 커피전문점 등)을 지원대상 문맥에서만, 최대 MED로 매칭.
INDEX_TERMS_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "ksic_index_terms.csv"
)
# G2: 소상공인 정책자금 표준 제외업종 목록(2024 중기부 공고). 공고가 이 표를
# 인용했는데 규칙이 표 안 코드를 '지원업종'으로 오추출하는 것을 교정한다.
POLICY_EXCLUSION_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "seeds", "policy_exclusion_industries.csv"
)

NAME_LEVEL_ORDER = ["세세분류", "세분류", "소분류", "중분류", "대분류"]
LEVEL_TO_COLUMNS = {
    "세세분류": ("KSIC_세세분류명", "KSIC_코드"),
    "세분류": ("KSIC_세분류명", "KSIC_세분류코드"),
    "소분류": ("KSIC_소분류명", "KSIC_소분류코드"),
    "중분류": ("KSIC_중분류명", "KSIC_중분류코드"),
    "대분류": ("KSIC_대분류명", "KSIC_대분류코드"),
}
LEVEL_RANK = {level: i for i, level in enumerate(NAME_LEVEL_ORDER)}

# 업종명 정규화 레이어(1): 업종명 바로 뒤에 붙는 각주기호는 매칭에서 무시한다.
# PBLN_121442: "제조업* 영위 사업장" — "제조업" 뒤 "*" 때문에 매칭 자체는
# 실패하지 않지만(부분일치라 원래도 찾아짐), 각주가 붙는 문서 전반에서 뒤
# 문맥이 밀리는 걸 막기 위해 매칭 패턴 자체에 흡수시킨다. 사전은 안 건드리고
# 매칭 시점에 패턴에 덧붙이는 방식이라 원문 위치(start/end)는 그대로 보존됨.
FOOTNOTE_SUFFIX_CHARS = "*※†‡¹²³⁴⁵⁶⁷⁸⁹⁰"
FOOTNOTE_SUFFIX_PATTERN = "[" + re.escape(FOOTNOTE_SUFFIX_CHARS) + "]*"


def _name_pattern(literal: str) -> str:
    """업종명 리터럴을 각주기호 허용 패턴으로 감싼다(정규화 레이어 1-1)."""
    return re.escape(literal) + FOOTNOTE_SUFFIX_PATTERN


# 문자열 부분일치 자체가 위험한 실제 사례. 강한 target 문맥이 있어도 이 명칭은
# 공식명 exact match보다 별도 표현/직접코드/LLM으로 처리하는 편이 안전하다.
GENERIC_NAME_BLOCKLIST = {
    "전기업", "경찰", "검찰", "의원", "법원", "백화점",
    "대학교", "대학원", "면세점",
}

# 검증에서 안전하게 일반화 가능한 표현만 남긴다.
# 값은 (공식 KSIC 명칭 목록, 기본 신뢰도). 실제 채택은 반드시 positive 문맥이어야 한다.
SAFE_SYNONYMS = {
    "외식업": (["음식점업"], "HIGH"),
    "철강산업": (["1차 철강 제조업"], "MED"),
    "이·미용업": (["이용 및 미용업"], "HIGH"),
    "이‧미용업": (["이용 및 미용업"], "HIGH"),
    "제조창업기업": (["제조업"], "HIGH"),
    "제조기업": (["제조업"], "HIGH"),
    "디자인전문기업": (["전문 디자인업"], "HIGH"),
    "디자인 전문기업": (["전문 디자인업"], "HIGH"),
    "소프트웨어 개발업": (["소프트웨어 개발 및 공급업"], "HIGH"),
    "여행업": (["여행사업"], "HIGH"),
    "일반음식점": (["음식점업"], "HIGH"),
    # "-업" 생략형 축약 표현. PBLN_123056/122305: "지원대상 음식점"처럼 문서
    # 전체에서 "음식점업"(공식명)을 한 번도 안 쓰고 "음식점"만 반복해서 매칭 실패.
    "음식점": (["음식점업"], "HIGH"),
    # 휴게음식점은 음식점과 비알코올 음료점에 걸칠 수 있어 MED로 둔다.
    "휴게음식점": (["음식점업", "비알코올 음료점업"], "MED"),
    "중소 제조기업": (["제조업"], "HIGH"),
    "제조 중소기업": (["제조업"], "HIGH"),
    "제조생산 중소기업": (["제조업"], "HIGH"),
    "제조업 사업주": (["제조업"], "HIGH"),
    "제조업체": (["제조업"], "HIGH"),
    "제조업소": (["제조업"], "HIGH"),
    "식품제조․가공업": (["식료품 제조업"], "MED"),
    "식품제조·가공업": (["식료품 제조업"], "MED"),
    "식품제조가공업": (["식료품 제조업"], "MED"),

    # 54건 사람검수에서 반복 확인된 법정/사업대상 표현.
    "식품접객업소": (["음식점업", "비알코올 음료점업"], "MED"),
    "식품접객업": (["음식점업", "비알코올 음료점업"], "MED"),
    "제과점": (["제과점업"], "HIGH"),
    "위탁급식": (["기관 구내식당업"], "MED"),
    "집단급식소": (["기관 구내식당업"], "MED"),

    # 농·어업인 지원 공고: 농업을 작물재배+축산으로, 어업을 03으로 보존.
    # 세세분류까지 임의 확장하지 않고 소/중분류 수준으로 제한한다.
    "농․어업인": (["작물 재배업", "축산업", "어업"], "MED"),
    "농·어업인": (["작물 재배업", "축산업", "어업"], "MED"),
    "농어업인": (["작물 재배업", "축산업", "어업"], "MED"),

    # 관광진흥법상 신청업종 표현 중 KSIC 대응이 비교적 직접적인 것만 보수적으로 추가.
    "국제회의기획업": (["전시, 컨벤션 및 행사 대행업"], "MED"),
    "카지노업": (["카지노 운영업"], "HIGH"),
    "유원시설업": (["유원지 및 테마파크 운영업"], "MED"),
    "종합유원시설업": (["유원지 및 테마파크 운영업"], "MED"),
    "일반유원시설업": (["유원지 및 테마파크 운영업"], "MED"),
    "기타유원시설업": (["유원지 및 테마파크 운영업"], "MED"),
    "종합테마파크업": (["유원지 및 테마파크 운영업"], "HIGH"),
    "일반테마파크업": (["유원지 및 테마파크 운영업"], "HIGH"),
    "기타테마파크업": (["유원지 및 테마파크 운영업"], "HIGH"),
    "관광식당업": (["음식점업"], "MED"),
    "관광면세업": (["면세점"], "MED"),
    "관광사진업": (["사진 촬영 및 처리업"], "MED"),
    "여객자동차터미널시설업": (["여객 자동차 터미널 운영업"], "MED"),
    "관광공연장업": (["공연시설 운영업"], "MED"),
    "한옥체험업": (["민박업"], "MED"),
    "외국인관광 도시민박업": (["민박업"], "HIGH"),
    "관광펜션업": (["민박업"], "MED"),
    "휴양콘도미니엄업": (["휴양 콘도 운영업"], "HIGH"),
}

# 검증에서 '제품/기술 표현 속 대분류' 오탐이 반복된 이름들.
REQUIRE_STRONG_TARGET_NAMES = {
    "농업", "어업", "광업", "제조업", "건설업", "숙박업", "금융업", "보건업",
    "병원", "대학교", "대학원", "면세점",
}

_ksic_index = None
_code_to_info_index = None
_name_to_best_info = None
_nts_to_ksic_index = None
_index_terms = None
_index_term_pattern = None
_policy_exclusion = None

# 공고/시행령이 구(10차) KSIC 코드를 인용하는 경우의 크로스워크.
# G4: data/processed/ksic_legacy_map.csv(해설서 신구연계표 기반, 78건)에서 로드.
# 파일이 없으면 기존 하드코딩 1건으로 폴백(하위호환).
try:
    from ksic_core.rule_detectors import _load_legacy_map as _rd_load_legacy_map
    LEGACY_KSIC_CODE_ALIASES = dict(_rd_load_legacy_map()) or {"71393": "71392"}
except Exception:
    LEGACY_KSIC_CODE_ALIASES = {"71393": "71392"}


def _clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _load_ksic_index():
    global _ksic_index, _code_to_info_index, _name_to_best_info
    if _ksic_index is not None:
        return _ksic_index

    index = {level: {} for level in NAME_LEVEL_ORDER}
    code_index = {}
    name_best = {}

    with open(KSIC_CLEAN_CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    for level in NAME_LEVEL_ORDER:
        name_col, code_col = LEVEL_TO_COLUMNS[level]
        for row in rows:
            name = _clean(row.get(name_col))
            code = _clean(row.get(code_col))
            if not name or not code or code.lower() == "nan":
                continue
            index[level][name] = code
            # 동일 코드가 여러 레벨에 중복 로드되더라도 더 세밀한 레벨을 우선.
            prev = code_index.get(code)
            if prev is None or LEVEL_RANK[level] < LEVEL_RANK[prev[1]]:
                code_index[code] = (name, level)
            prev_name = name_best.get(name)
            if prev_name is None or LEVEL_RANK[level] < LEVEL_RANK[prev_name[1]]:
                name_best[name] = (code, level)

    _ksic_index = index
    _code_to_info_index = code_index
    _name_to_best_info = name_best
    return index


def _load_code_to_info_index():
    _load_ksic_index()
    return _code_to_info_index


def _resolve_official_name(name: str):
    _load_ksic_index()
    return _name_to_best_info.get(name)


def _excluded_record(code: str, name: str, kind: str, reason: str = ""):
    return {"코드": code, "명칭": name, "유형": kind, "사유": reason}


def _dedupe_excluded(items):
    out = []
    seen = set()
    for item in items:
        key = (item.get("코드"), item.get("유형"), item.get("명칭"))
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _build_stage(codes, levels):
    if not codes:
        return "확인불가"
    if len(codes) > 1:
        return "복수산업"
    return levels[0] if levels else "확인불가"


def _scan_direct_codes_with_official_name(text: str, code_index: dict[str, tuple[str, str]], include_short: bool = True):
    """숫자코드가 공식 KSIC 명칭과 같은 줄/근접구간에 함께 나오면 직접명시로 보강한다.

    * 4~5자리: 붙임 표에서 헤더가 멀거나 줄바꿈이 깨져도 복구용
    * 2~3자리: 연번과 충돌하므로 include_short=True일 때만, 공식명 동반 조건으로 허용
    """
    if not any(w in text for w in ["한국표준산업분류", "표준산업분류", "KSIC", "업종코드", "산업분류"]):
        return []
    out = []
    for m in re.finditer(r"(?<!\d)(\d{2,5})(?!\d)", text):
        code = m.group(1)
        if code not in code_index:
            continue
        if len(code) <= 3 and not include_short:
            continue
        name, level = code_index[code]
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.end())
        if line_end == -1:
            line_end = min(len(text), m.end() + 180)
        line = text[line_start:line_end]
        around = text[max(line_start, m.start()-70):min(len(text), line_end+150)]
        # 공백/가운뎃점 차이는 최소 정규화해서 비교
        norm_name = re.sub(r"\s+", "", name)
        norm_line = re.sub(r"\s+", "", line)
        norm_around = re.sub(r"\s+", "", around)
        if norm_name not in norm_line and norm_name not in norm_around:
            continue
        role, reason = classify_occurrence_role(text, m.start(), m.end(), candidate_text=code, candidate_kind="code")
        if role == "neutral":
            role, reason = "positive", "KSIC 코드와 공식 업종명이 함께 직접 명시"
        out.append({
            "code": code, "start": m.start(), "end": m.end(),
            "role": role, "reason": reason, "source": "code_with_official_name",
        })
    return out



def _scan_positive_appendix_table(text: str, code_index: dict[str, tuple[str, str]]):
    """붙임/별표의 '지원/해당 업종' 코드표를 행 시작 코드 기준으로 복구한다.

    2~3자리 코드(72, 85, 582 등)는 일반 본문 숫자와 충돌 위험이 커서
    이런 명시적 positive appendix/table 안에서만 허용한다.
    행번호 '10.'처럼 점/괄호가 바로 붙은 숫자는 제외한다.
    """
    out = []
    # 각 붙임/별표 섹션 경계
    marks = list(re.finditer(r"(?:붙임|븥임|별표)\s*\d+", text, flags=re.I))
    # [2026-09-13 수정] "붙임 1 ... 지원 제외대상 붙임 2 ... 평균매출액 기준"처럼
    # 2단 표가 한 줄로 깨져 서로 다른 붙임 제목이 붙어버리면(실측: PBLN_124699),
    # 뒤쪽 "붙임 2" 섹션은 자기 제목만 보고 제외표가 아니라고 판단해 앞쪽
    # 제외업종 목록을 그대로 positive로 흡수했다 — 인접 경계(같은 줄/문단
    # 간격)의 앞선 제목도 함께 확인해야 이 누락을 막는다.
    cluster_gap = 120
    for i, m in enumerate(marks):
        sec_end = marks[i+1].start() if i+1 < len(marks) else len(text)
        section = text[m.start():sec_end]
        header = section[:750]

        j = i
        while j > 0 and marks[j].start() - marks[j - 1].end() <= cluster_gap:
            j -= 1
        header_for_check = (text[marks[j].start():m.end()] + header) if j != i else header

        # 제외표는 절대 positive appendix로 취급하지 않는다.
        if re.search(r"(?:지원\s*)?제외\s*(?:업종|대상)|지원\s*제한", header_for_check, flags=re.I):
            continue

        positive_table = bool(
            re.search(r"(?:해당|지원|대상|관련).{0,35}(?:업종|KSIC|한국표준산업분류)", header, flags=re.I|re.S)
            or re.search(r"(?:분류코드|업종코드)", header, flags=re.I)
        )
        if not positive_table:
            continue

        for cm in re.finditer(r"(?m)^[ \t]*(\d{2,5})(?![ \t]*[.)）])(?=[ \t]|$)", section):
            raw = cm.group(1)
            code = raw
            mapped_from = None
            if code not in code_index and code in LEGACY_KSIC_CODE_ALIASES:
                mapped_from = code
                code = LEGACY_KSIC_CODE_ALIASES[code]
            if code not in code_index:
                continue

            abs_start = m.start() + cm.start(1)
            abs_end = m.start() + cm.end(1)
            name, level = code_index[code]
            out.append({
                "code": code,
                "start": abs_start,
                "end": abs_end,
                "role": "positive",
                "reason": "지원/해당 업종 붙임·별표 코드표",
                "source": "positive_appendix_table",
                "raw_code": mapped_from or raw,
            })
    return out


def _load_policy_exclusion():
    """{코드: 유형('전체'|'부분')}. G2. 소상공인 정책자금 표준 제외업종."""
    global _policy_exclusion
    if _policy_exclusion is not None:
        return _policy_exclusion
    out = {}
    if os.path.exists(POLICY_EXCLUSION_CSV_PATH):
        with open(POLICY_EXCLUSION_CSV_PATH, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                code = _clean(row.get("KSIC코드"))
                typ = _clean(row.get("유형")) or "전체"
                if code:
                    out[code] = typ
    _policy_exclusion = out
    return _policy_exclusion


def _policy_exclusion_type(code: str):
    """code 또는 그 상위코드가 표준 제외목록에 있으면 유형을 반환, 없으면 None."""
    pol = _load_policy_exclusion()
    if code in pol:
        return pol[code]
    for k, typ in pol.items():
        if len(k) >= 2 and code.startswith(k):   # 64 -> 64123 등 하위코드
            return typ
    return None


def _reclassify_policy_exclusions(text: str, positives: list, excluded: list, all_detail_codes):
    """공고가 '소상공인 정책자금 표준 제외업종 표'를 인용했는데 규칙이 그 표
    안의 코드를 '지원업종'으로 오추출한 경우 교정한다.

    (금융업·보험업·부동산업·보건업을 동시에 '지원대상'으로 삼는 공고는 없다.
     이건 거의 항상 [붙임] 제외업종 표에서 새어 나온 것이다.)

    발동 조건:
      - 문서 전체 KSIC 후보 중 표준 제외목록 코드가 5종 이상  (표 인용의 강한 신호)
        AND '정책자금 융자제외' 또는 '지원제외 업종' 표현 존재
      → positive 중 표준 제외목록에 해당하는 코드를 전부 제외로 옮긴다.
    """
    distinct_policy = {c for c in all_detail_codes if _policy_exclusion_type(c)}
    if len(distinct_policy) < 5:
        return
    if not re.search(
        r"정책자금.{0,20}(?:융자|지원)?\s*제외|융자제외\s*대상\s*업종|지원\s*제외\s*업종",
        text,
    ):
        return
    hit = [(c, n, lv) for (c, n, lv) in positives if _policy_exclusion_type(c)]
    if not hit:
        return
    # 지식산업 공고처럼 지원대상에 수십 개 업종을 나열하면서 그중 일부가
    # 우연히 제외목록과 겹치는 경우는 건드리지 않는다. positive가 거의 전부
    # 제외목록 코드일 때만(=진짜 제외표를 지원표로 착각한 경우) 교정한다.
    if not (len(positives) <= 3 or len(hit) >= len(positives) * 0.6):
        return
    hit_codes = {c for c, _, _ in hit}
    positives[:] = [(c, n, lv) for (c, n, lv) in positives if c not in hit_codes]
    for c, n, _lv in hit:
        typ = "전체제외" if _policy_exclusion_type(c) == "전체" else "부분제외"
        excluded.append(_excluded_record(
            c, n, typ, "소상공인 정책자금 표준 제외업종 목록 인용(G2)"
        ))


def match_ksic_by_code(text):
    """원문에 직접 명시된 KSIC를 추출한다.

    이 결과에 positive 코드가 하나라도 있으면 ``authoritative=True``다.
    decide_industry에서는 이 경우 이름매칭을 union하지 말고 원문 직접코드만
    사용해야 한다.
    """
    if not text or not str(text).strip():
        return None

    code_index = _load_code_to_info_index()
    text_str = str(text)
    details = extract_explicit_ksic_details(text_str, valid_codes=set(code_index.keys()))
    # 신청자격이 '세세분류 중 하나'라고 직접 못박힌 문서는 2~3자리 부모코드를
    # 표 설명용 열로 보고 최종 direct list에 추가하지 않는다.
    requires_five_digit = bool(re.search(r"(?:한국표준산업분류|KSIC).{0,45}세세분류|세세분류.{0,45}(?:한국표준산업분류|KSIC)", text_str, flags=re.I|re.S))
    details.extend(_scan_direct_codes_with_official_name(text_str, code_index, include_short=not requires_five_digit))
    details.extend(_scan_positive_appendix_table(text_str, code_index))
    # occurrence 기준 중복 제거
    dedup = []
    seen_detail = set()
    for d in sorted(details, key=lambda x: (x.get("start", 0), x.get("code", ""), x.get("role", ""))):
        key = (d.get("code"), d.get("start"), d.get("end"), d.get("role"))
        if key in seen_detail:
            continue
        seen_detail.add(key)
        dedup.append(d)
    details = dedup
    if not details:
        return None

    positives = []
    excluded = []
    role_by_code = defaultdict(set)

    for d in details:
        raw = d["code"]
        code = raw[:-1] if raw.endswith("*") else raw
        info = code_index.get(code)
        if not info:
            continue
        name, level = info
        role = d["role"]
        role_by_code[code].add(role)

        if role == "positive":
            if code not in [x[0] for x in positives]:
                positives.append((code, name, level))
        elif role == "excluded":
            excluded.append(_excluded_record(code, name, "전체제외", d["reason"]))
        elif role == "partial_exclusion":
            excluded.append(_excluded_record(code, name, "부분제외", d["reason"]))
        elif role == "exclusion_exception":
            # 제외업종 표의 예외는 '사업 전체 positive 업종'으로 승격하지 않는다.
            excluded.append(_excluded_record(code, name, "제외예외", d["reason"]))

    # G2: 표준 정책자금 제외업종표를 지원업종으로 오추출했으면 제외로 교정.
    _reclassify_policy_exclusions(
        text_str, positives, excluded,
        {(d["code"][:-1] if d["code"].endswith("*") else d["code"]) for d in details},
    )

    codes = [x[0] for x in positives]
    names = [x[1] for x in positives]
    levels = [x[2] for x in positives]

    # 같은 코드가 positive와 '실제 제외/부분제외'에 모두 등장하면 조건부 충돌.
    # 제외표의 '지원가능 예외'는 positive와 충돌하는 하드제외가 아니므로 conflict에서 제외.
    conflicts = sorted(
        code for code, roles in role_by_code.items()
        if "positive" in roles and bool(roles & {"excluded", "partial_exclusion"})
    )

    # positive 코드와 같은 코드의 제외 메타데이터는 downstream hard filter에
    # 들어가면 위험하므로 제외업종 목록에서는 빼고 근거에만 보존한다.
    conflict_records = []
    cleaned_excluded = []
    positive_set = set(codes)
    for item in _dedupe_excluded(excluded):
        if item.get("코드") in positive_set:
            if item.get("유형") == "제외예외":
                # 같은 positive 코드의 '지원가능 예외'는 별도 제외 메타데이터 불필요.
                continue
            if item.get("유형") in {"전체제외", "부분제외"}:
                conflict_records.append(item)
                continue
        cleaned_excluded.append(item)
    excluded = cleaned_excluded

    confidence = "LOW" if conflicts else ("HIGH" if codes else "LOW")

    return {
        "확정단계": _build_stage(codes, levels),
        "확정코드": codes,
        "확정업종명": names,
        "제외업종": _dedupe_excluded(excluded),
        "근거": {
            "매칭방식": "KSIC 코드 직접 명시",
            "authoritative": bool(codes),
            "탐지상세": details,
            "positive_exclusion_conflict": conflicts,
            "conflict_exclusion_records": conflict_records,
        },
        "ksic_confidence": confidence,
    }


def _scan_official_name_hits(text: str):
    index = _load_ksic_index()
    hits = []
    excluded = []

    # 가장 긴 이름, 가장 세밀한 레벨을 우선해 같은 위치의 상위명 중복을 줄인다.
    all_names = []
    for level in NAME_LEVEL_ORDER:
        for name, code in index[level].items():
            if name in GENERIC_NAME_BLOCKLIST:
                continue
            all_names.append((name, code, level))
    all_names.sort(key=lambda x: (-len(x[0]), LEVEL_RANK[x[2]], x[0]))

    occupied = []
    for name, code, level in all_names:
        for m in re.finditer(_name_pattern(name), text):
            start, end = m.start(), m.end()
            if any(s <= start and end <= e for s, e in occupied):
                continue

            role, reason = classify_occurrence_role(
                text, start, end, candidate_text=name, candidate_kind="name"
            )
            if role == "positive":
                # 범용 짧은 이름은 strong target 판정일 때만 들어오므로 여기서는 허용.
                hits.append((start, end, code, name, level, "exact", reason, "HIGH"))
                occupied.append((start, end))
            elif role == "excluded":
                excluded.append(_excluded_record(code, name, "전체제외", reason))
            elif role == "partial_exclusion":
                excluded.append(_excluded_record(code, name, "부분제외", reason))
            elif role == "exclusion_exception":
                excluded.append(_excluded_record(code, name, "제외예외", reason))
            # neutral/non_target은 HIGH 확정 후보로 사용하지 않는다.

    return hits, excluded


def _load_index_terms():
    """색인어 → [(code, level, conf), ...]. G1.

    색인어는 공식명보다 약한 근거라 자동 HIGH를 금지한다(최대 MED).
    CSV가 없으면 빈 dict → 기존 동작과 동일.
    """
    global _index_terms, _index_term_pattern
    if _index_terms is not None:
        return _index_terms
    terms: dict[str, list[tuple[str, str, str]]] = {}
    if os.path.exists(INDEX_TERMS_CSV_PATH):
        code_info = _load_code_to_info_index()
        with open(INDEX_TERMS_CSV_PATH, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                term = _clean(row.get("색인어"))
                code = _clean(row.get("KSIC코드"))
                conf = (_clean(row.get("신뢰도")) or "MED").upper()
                if len(term) < 3 or term in GENERIC_NAME_BLOCKLIST:
                    continue
                info = code_info.get(code)
                if not info:
                    continue
                conf = "MED" if conf == "HIGH" else conf  # 색인어는 HIGH 금지
                terms.setdefault(term, []).append((code, info[1], conf))
    _index_terms = terms
    # 긴 색인어를 먼저 두어 가장 구체적인 것이 매칭되게 한다.
    if terms:
        ordered = sorted(terms, key=len, reverse=True)
        _index_term_pattern = re.compile("|".join(_name_pattern(t) for t in ordered))
    else:
        _index_term_pattern = None
    return _index_terms


def _scan_index_term_hits(text: str):
    """색인어를 지원대상(positive) 문맥에서만 매칭. G1.

    수천 개 색인어를 개별 finditer 하면 느리므로 결합 정규식으로 한 번만 스캔한다.
    """
    terms = _load_index_terms()
    if not _index_term_pattern:
        return [], []
    hits, excluded = [], []
    code_info = _load_code_to_info_index()
    for m in _index_term_pattern.finditer(text):
        # 매칭 패턴이 각주기호를 허용하므로(정규화 레이어 1-1), 사전 조회 전에
        # 각주기호만 떼어낸 순수 색인어로 되돌린다.
        term = m.group(0).rstrip(FOOTNOTE_SUFFIX_CHARS)
        entries = terms.get(term)
        if not entries:
            continue
        role, reason = classify_occurrence_role(
            text, m.start(), m.end(), candidate_text=term, candidate_kind="name"
        )
        if role not in ("positive", "excluded", "partial_exclusion", "exclusion_exception"):
            continue
        for code, level, conf in entries:
            official = code_info.get(code, (term, level))[0]
            if role == "positive":
                hits.append((m.start(), m.end(), code, official, level, f"index:{term}", reason, conf))
            elif role == "excluded":
                excluded.append(_excluded_record(code, official, "전체제외", reason))
            elif role == "partial_exclusion":
                excluded.append(_excluded_record(code, official, "부분제외", reason))
            elif role == "exclusion_exception":
                excluded.append(_excluded_record(code, official, "제외예외", reason))
    return hits, excluded


def _scan_synonym_hits(text: str):
    hits = []
    excluded = []
    for phrase, (official_names, base_conf) in SAFE_SYNONYMS.items():
        for m in re.finditer(re.escape(phrase), text):
            role, reason = classify_occurrence_role(
                text, m.start(), m.end(), candidate_text=phrase, candidate_kind="name"
            )
            for official in official_names:
                info = _resolve_official_name(official)
                if not info:
                    continue
                code, level = info
                if role == "positive":
                    hits.append((m.start(), m.end(), code, official, level, f"synonym:{phrase}", reason, base_conf))
                elif role == "excluded":
                    excluded.append(_excluded_record(code, official, "전체제외", reason))
                elif role == "partial_exclusion":
                    excluded.append(_excluded_record(code, official, "부분제외", reason))
                elif role == "exclusion_exception":
                    excluded.append(_excluded_record(code, official, "제외예외", reason))
    return hits, excluded


def match_ksic_by_name(text):
    """KSIC 공식 명칭/안전한 동의어를 '지원대상 문맥'에서만 매칭한다."""
    if not text or not str(text).strip():
        return None
    text = str(text)

    exact_hits, excluded1 = _scan_official_name_hits(text)
    synonym_hits, excluded2 = _scan_synonym_hits(text)
    index_hits, excluded3 = _scan_index_term_hits(text)
    all_hits = exact_hits + synonym_hits + index_hits

    if not all_hits:
        if excluded1 or excluded2 or excluded3:
            return {
                "확정단계": "확인불가",
                "확정코드": [],
                "확정업종명": [],
                "제외업종": _dedupe_excluded(excluded1 + excluded2 + excluded3),
                "근거": {"매칭방식": "업종명 문맥 매칭", "positive_hit": False},
                "ksic_confidence": "LOW",
            }
        return None

    # 위치순으로 정리하고 동일 코드 중복 제거.
    all_hits.sort(key=lambda h: (h[0], LEVEL_RANK[h[4]], -len(h[3])))
    codes, names, levels, evidence = [], [], [], []
    confidences = []
    for start, end, code, name, level, source, reason, conf in all_hits:
        if code in codes:
            continue
        codes.append(code)
        names.append(name)
        levels.append(level)
        confidences.append(conf)
        evidence.append({
            "코드": code, "명칭": name, "레벨": level,
            "시작": start, "종료": end, "source": source, "reason": reason,
        })

    # 이름매칭의 상·하위 중복은 "상위코드가 exact 공식명으로 잡힌 경우"에만
    # 제거한다. 서로 다른 법정 지원유형을 안전한 동의어로 매핑한 경우
    # (예: 일반음식점→561, 제과점→56150)는 부모 561을 지우면 다른 음식점
    # 범위를 잃으므로 보존한다.
    source_by_code = {e["코드"]: e.get("source", "") for e in evidence}
    keep = [True] * len(codes)
    for i, c in enumerate(codes):
        if not c.isdigit() or source_by_code.get(c) != "exact":
            continue
        for j, d in enumerate(codes):
            if i == j or not d.isdigit():
                continue
            if len(d) > len(c) and d.startswith(c):
                keep[i] = False
                break
    codes = [c for c, k in zip(codes, keep) if k]
    names = [n for n, k in zip(names, keep) if k]
    levels = [lv for lv, k in zip(levels, keep) if k]

    # G2: 이름매칭도 표준 정책자금 제외업종표에서 이름(수의업/감정평가업 등)을
    # 주워 positive로 만들 수 있다. match_ksic_by_code와 동일 로직으로 교정.
    _pol_positives = list(zip(codes, names, levels))
    _pol_excluded: list = []
    _all_seen = set(codes) | {
        it.get("코드") for it in (excluded1 + excluded2 + excluded3)
    }
    _reclassify_policy_exclusions(text, _pol_positives, _pol_excluded, _all_seen)
    if len(_pol_positives) != len(codes):
        codes = [c for c, _, _ in _pol_positives]
        names = [n for _, n, _ in _pol_positives]
        levels = [lv for _, _, lv in _pol_positives]
        excluded3 = list(excluded3) + _pol_excluded

    keep_codes = set(codes)
    evidence = [e for e in evidence if e["코드"] in keep_codes]

    # positive 코드와 같은 코드의 제외 메타데이터는 hard-filter 목록에서 분리한다.
    excluded_all = _dedupe_excluded(excluded1 + excluded2 + excluded3)
    name_conflict_records = []
    cleaned_excluded = []
    for item in excluded_all:
        if item.get("코드") in keep_codes:
            if item.get("유형") == "제외예외":
                continue
            if item.get("유형") in {"전체제외", "부분제외"}:
                name_conflict_records.append(item)
                continue
        cleaned_excluded.append(item)
    excluded_all = cleaned_excluded

    # MED 동의어 또는 색인어가 하나라도 최종에 남으면 자동 HIGH로 두지 않는다.
    final_conf = "MED" if any(
        e["source"].startswith("index:")
        or (e["source"].startswith("synonym:")
            and SAFE_SYNONYMS[e["source"].split(":", 1)[1]][1] != "HIGH")
        for e in evidence
    ) else "HIGH"
    if name_conflict_records:
        final_conf = "LOW"

    return {
        "확정단계": _build_stage(codes, levels),
        "확정코드": codes,
        "확정업종명": names,
        "제외업종": excluded_all,
        "근거": {
            "매칭방식": "지원대상 문맥의 KSIC 업종명 매칭",
            "evidence": evidence,
            "authoritative": False,
            "positive_exclusion_conflict": sorted({x.get("코드") for x in name_conflict_records}),
            "conflict_exclusion_records": name_conflict_records,
        },
        "ksic_confidence": final_conf,
    }


def _load_nts_to_ksic_index():
    global _nts_to_ksic_index
    if _nts_to_ksic_index is not None:
        return _nts_to_ksic_index
    if not os.path.exists(NTS_TO_KSIC_CSV_PATH):
        _nts_to_ksic_index = {}
        return _nts_to_ksic_index

    index = defaultdict(list)
    with open(NTS_TO_KSIC_CSV_PATH, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            nts = _clean(row.get("국세청코드"))
            ksic = _clean(row.get("KSIC코드"))
            name = _clean(row.get("KSIC명"))
            if nts and ksic:
                index[nts].append((ksic, name))
    _nts_to_ksic_index = dict(index)
    return _nts_to_ksic_index


def match_ksic_by_nts_code(text):
    """국세청 업종코드 직접명시를 KSIC로 역변환한다.

    1:N 매핑이면 원문만으로 어느 KSIC인지 확정할 수 없으므로 LOW다.
    """
    if not text or not str(text).strip():
        return None
    nts_index = _load_nts_to_ksic_index()
    if not nts_index:
        return None

    details = extract_nts_codes_details(str(text))
    if not details:
        return None

    codes, names, levels = [], [], []
    excluded = []
    one_to_many = []

    code_info = _load_code_to_info_index()
    for d in details:
        mappings = nts_index.get(d["code"], [])
        if not mappings:
            continue
        if len(mappings) > 1 and d["role"] == "positive":
            one_to_many.append(d["code"])
        for ksic_code, ksic_name in mappings:
            info = code_info.get(ksic_code)
            level = info[1] if info else "세세분류"
            name = ksic_name or (info[0] if info else ksic_code)
            if d["role"] == "positive":
                if ksic_code not in codes:
                    codes.append(ksic_code)
                    names.append(name)
                    levels.append(level)
            elif d["role"] == "excluded":
                excluded.append(_excluded_record(ksic_code, name, "전체제외", d["reason"]))
            elif d["role"] == "partial_exclusion":
                excluded.append(_excluded_record(ksic_code, name, "부분제외", d["reason"]))
            elif d["role"] == "exclusion_exception":
                excluded.append(_excluded_record(ksic_code, name, "제외예외", d["reason"]))

    if not codes and not excluded:
        return None

    confidence = "LOW" if one_to_many else ("HIGH" if codes else "LOW")
    stage = "확인필요(국세청1:N)" if one_to_many else _build_stage(codes, levels)

    return {
        "확정단계": stage,
        "확정코드": codes,
        "확정업종명": names,
        "제외업종": _dedupe_excluded(excluded),
        "근거": {
            "매칭방식": "국세청 업종코드 역변환",
            "authoritative": bool(codes),
            "탐지상세": details,
            "1대N_국세청코드": sorted(set(one_to_many)),
        },
        "ksic_confidence": confidence,
    }
