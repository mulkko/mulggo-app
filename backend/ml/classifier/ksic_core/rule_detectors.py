"""KSIC/NTS 규칙 탐지기.

이 버전의 핵심 원칙
-------------------
1. 숫자나 업종명이 문서에 '등장'했다는 이유만으로 지원업종으로 확정하지 않는다.
2. 각 occurrence(등장 위치)를 따로 판정한다. ``text.find(code)`` 로 첫 등장만
   보는 방식은 사용하지 않는다.
3. 지원대상/신청자격/지원업종 문맥과 제외/예외/제3자/참고표 문맥을 분리한다.
4. 직접 명시된 KSIC는 단 1개여도 인정한다. 단, KSIC 헤더에서 멀리 떨어진
   숫자는 표 오염(지번/연도 등)을 막기 위해 추가 안전장치를 적용한다.
5. ``33409 중 ...`` 같은 부분제외와 '제외업종의 예외'는 일반 positive 업종으로
   뒤집지 않는다.

외부 호환성을 위해 ``extract_explicit_ksic`` 와 ``extract_nts_codes`` 는
기존처럼 ``[(code, is_excluded), ...]`` 형식도 제공한다. 더 정교한 판정이
필요한 호출부는 ``*_details`` 함수를 사용한다.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
import csv
import os
import re
from typing import Iterable


# ---------------------------------------------------------------------------
# 공통 문맥 패턴
# ---------------------------------------------------------------------------
KSIC_CONTEXT_WORDS = [
    "한국표준산업분류",
    "표준산업분류",
    "KSIC",
    "산업분류상",
    "업종코드",
    "산업분류코드",
]

NTS_CONTEXT_WORDS = [
    "국세청 업종코드",
    "국세청업종코드",
    "귀속 업종코드",
    "귀속업종코드",
]

# 명백한 신청기업 positive 문맥. 단순 '지원내용'은 넣지 않는다.
POSITIVE_TARGET_PATTERNS = [
    r"지원\s*대상",
    r"사업\s*대상",
    r"추진\s*대상",
    r"모집\s*대상",
    r"모집\s*업체",
    r"신청\s*대상",
    r"참여\s*대상",
    r"융자\s*대상",
    r"지원\s*업종",
    r"모집\s*업종",
    r"신청\s*업종",
    r"신청\s*자격",
    r"지원\s*자격",
    r"참여\s*자격",
    r"특화\s*산업\s*분야",
    r"관련\s*한국표준산업분류",
    r"관련\s*KSIC",
]

EXCLUSION_PATTERNS = [
    r"지원\s*제외",
    r"참여\s*제외",
    r"신청\s*제외",
    r"선정\s*제외",
    r"융자\s*제외",
    r"제외\s*업종",
    r"제외\s*대상",
    r"지원\s*제한",
    r"지원제한",
    # '제외' 대신 '제한'으로 표현하는 문서도 많다(융자제한/참여제한/제한기업 등).
    r"융자\s*제한",
    r"참여\s*제한",
    r"제한\s*업종",
    r"제한\s*대상",
    r"제한\s*기업",
]

# 제외 표 안의 '지원 가능 예외'는 전체 사업의 positive 업종이 아니다.
EXCLUSION_EXCEPTION_PATTERNS = [
    r"지원\s*가능",
    r"신청\s*가능",
    r"지원\s*대상\s*(?:에|으로)?\s*(?:도)?\s*포함",
    r"예외",
    r"다만",
    r"단\s*[,：:]",
]

# 신청기업 업종이 아닌 역할/주체. 검증 메모에서 반복된 실제 오탐 패턴을 반영.
NON_TARGET_ROLE_WORDS = [
    "시공자", "시공업체", "설치업체", "협력업체", "용역업체", "하도급", "위탁업체",
    "공급기업", "공급기관", "주관기관", "운영기관", "지원기관", "수행기관", "협력기관",
    "구매기관", "구매기업", "구매담당", "공공기관", "바이어", "투자기관", "평가기관",
    "시험기관", "인증기관", "연계기관", "병원 연계", "의료기관 연계",
    "판매채널", "유통채널", "입점처", "입점", "쇼룸", "면세점 입점",
    "숙박업소", "이용확인서", "방문기관",
    "인턴직무", "직무분야", "채용직무", "직무", "멘토",
    "학력", "전공", "졸업", "창작전담요원", "전담요원",
]

# 지원자격 참고표/산식/예시 등. '별표' 자체는 직접 KSIC표도 있을 수 있으므로 제외하지 않는다.
REFERENCE_CONTEXT_WORDS = [
    "예시", "예)", "(예)", "예 :", "예:",
    "참고자료", "참고표", "소기업 규모 기준", "평균 매출액", "평균매출액",
    "상시근로자 수 기준", "상시근로자수 기준",
    "산재보험료", "보험료율", "요율", "가점항목", "가점 사항", "평가항목",
    "체크리스트", "작성 예시", "분류기호 참고",
    "소상공인 기준", "소상공인의 범위", "연간매출액", "연간 매출액",
    "소기업 규모", "소기업 규모 기준", "법정 기준", "업종별 기준",
]

# "5인 미만"/"10인 미만"처럼 숫자를 고정해두면, 그 숫자가 아닌 지원대상
# 선언(예: "50인 미만 제조업 영위 사업장")은 못 잡고 놓치는 반면, 우연히
# 같은 숫자가 쓰인 단일 지원대상 선언은 "참고표"로 오판한다(PBLN_117167:
# "가구제조업 소공인 (상시근로자 수 10인 미만)"). 숫자를 정규식으로
# 일반화하되, "지원대상/신청대상/모집대상" 선언 자체에 붙은 단일 규모조건과
# 참고표 나열을 구분하기 위해 같은 문맥창에 target 헤더가 있으면(=이 숫자가
# 그 선언의 조건절일 가능성이 높음) 참고문맥 신호로 안 본다.
_SCALE_HEADCOUNT_PATTERN = re.compile(r"\d+\s*인\s*(?:미만|이하)")
_TARGET_HEADER_NEARBY = re.compile(r"(?:지원|신청|모집)\s*대상")

# 신규481 T2 오류분석(2026-09-12)에서 발견: "지원대상: 영세 소상공인" 뒤에
# 소상공인기본법상 "업종별 상시근로자 수" 정의표(도소매·서비스업 5명 /
# 광업·제조업·건설업·운수업 10명 미만 등)가 바로 붙는 경우, 이건 업종
# 무관하게 "소상공인 여부"만 가르는 법정 규모기준 정의라서, 위 "지원대상
# 선언에 붙은 단일 규모조건"(가구제조업 소공인 사례)과 다르다. 표 안에
# 언급된 광업/제조업/건설업 같은 업종명이 지원대상으로 오인되지 않도록,
# 이 정의 문구가 보이면 target 헤더 근접 여부와 무관하게 참고문맥으로 본다.
_INDUSTRY_AGNOSTIC_SIZE_DEFINITION = re.compile(r"업종별\s*상시근로자|그\s*외\s*업종\s*[:：]")


def _has_bare_scale_hint(local: str, paragraph: str) -> bool:
    """규모기준 숫자(예: '50인 미만')는 있는데, 같은 문맥창에 지원대상 헤더가
    전혀 없으면(=지원대상 선언과 무관하게 떨어진 숫자) 참고표 신호로 본다."""
    if _INDUSTRY_AGNOSTIC_SIZE_DEFINITION.search(local) or _INDUSTRY_AGNOSTIC_SIZE_DEFINITION.search(paragraph):
        return True
    if _TARGET_HEADER_NEARBY.search(local) or _TARGET_HEADER_NEARBY.search(paragraph):
        return False
    return bool(_SCALE_HEADCOUNT_PATTERN.search(local) or _SCALE_HEADCOUNT_PATTERN.search(paragraph))

# 이 문구가 속한 '참고N' 섹션은 KSIC가 직접 적혀 있어도 지원대상 표가 아니라
# 기업규모/정산/확인용 참고표다. direct-code positive 판정보다 우선해 차단한다.
STRONG_REFERENCE_SECTION_WORDS = [
    "소상공인 확인기준",
    "소상공인 기준",
    "소기업 규모 기준",
    "업종별 평균매출액 등의 소기업 규모 기준",
    "업종별 평균매출액",
    "업종별 평균 매출액",
    "지원금 정산서류 기준",
    "소공인 규모 기준",
]

# '제품/품목/기술' 문맥에서 농업/금융업 같은 짧은 대분류명이 나오면
# 신청기업 업종이 아니라 품목/기술 분야일 가능성이 높다.
PRODUCT_CONTEXT_WORDS = [
    "제품", "품목", "자재", "소재", "부품", "장비", "기술", "솔루션",
    "서비스 분야", "대상기술", "주요품목", "참여품목",
]

# "OO, OO 등 개인서비스업종" / "개인서비스요금에 해당하는 업종" 처럼 몇 개만
# 예시로 들거나 통계청 분류를 통째로 가리키는 개방형 표현. 착한가격업소류
# 공고에서 반복 확인된 패턴: "신청대상 : 음식점, 이·미용업 등 개인서비스업종"
# 라고 적어도, 실제 지정범위는 문서 자체의 붙임 예시표(볼링장/자동차학원/
# 컴퓨터수리 등 수십 개 업종)만큼 넓다. 같은 문서 안에 "모집업종: 외식업 :
# [수십 개 품목]"처럼 "등" 없이 같은 개념을 반복하는 경우도 있어 "등"은
# 필수로 두지 않는다. 명시된 몇 개 업종만 정답 코드로 뽑으면 실제보다 좁게
# 확정하는 오류가 된다.
OPEN_ENDED_CATCHALL_PATTERN = re.compile(r"개인\s*서비스\s*(?:업종|요금)")

# 업종무관을 명시적으로 확정할 수 있는 표현만 HIGH로 사용.
# [2026-09-13 수정] "전\s*업종"은 경계 처리가 없어 "불건전업종"처럼 무관한
# 합성어 내부의 "전"+"업종"까지 우연히 매칭했다(Resolver Phase 1 FP 추적 중
# 발견, test_rule_detectors.py::test_no_restriction_pattern_rejects_compound_word
# 로 재현). "전" 바로 앞에 한글 음절이 붙어있으면(공백 없이 합성어로 이어지면)
# 제외한다 — "전 업종"(공백)이나 문장/구 시작의 "전업종"은 그대로 인정한다.
NO_RESTRICTION_PATTERNS = [
    r"전\s*산업\s*분야",
    r"(?<![가-힣])전\s*업종",
    r"업종\s*무관",
    r"업종\s*제한\s*(?:없|없음|무)",
    r"특정\s*업종\s*제한\s*(?:없|없음)",
]

# 규칙이 의미 확장을 해서는 안 되는 넓은 기술/산업 표현.
BROAD_FIELD_TERMS = [
    "바이오헬스", "모빌리티", "스마트전자", "첨단부품", "탄소중립", "디지털전환",
    "신산업", "섬유 관련", "반도체·소부장", "반도체 소부장", "푸드테크", "핀테크",
]

# [2026-09-12g 추가] LLM Resolver v2(scope-first)용 위험 신호. OPEN_ENDED_CATCHALL_PATTERN은
# "개인서비스업종/요금" 문구 하나만 잡는 좁은 패턴이라(위 주석 참고), Resolver에게 넘길
# 일반화된 개방형 나열 탐지가 추가로 필요함 — "OO업, OO업종 등" 형태를 폭넓게 잡는다.
# 실측 검증(2026-09-12): "개인서비스 업종(외식업, 이미용업, 세탁업 등)" 매칭 확인,
# "제조업 및 정보통신업 영위기업"/"위조방지기술 도입지원 사업"/"수출 중소·중견기업"에는
# 오탐 없음 확인.
_OPEN_ENDED_LIST_GENERAL = re.compile(
    r"(?:[가-힣A-Za-z0-9]{2,12}(?:업종|업)\s*[,、·및]\s*){1,}[가-힣A-Za-z0-9]{2,12}(?:업종|업)\s*등"
)

# "A 또는 B"처럼 대안이 나뉘는 조건 중 하나가 업종무관/모호한 조건이면, Resolver가
# 자유응답 압력으로 하나의 업종만 고를 위험이 있다(57건 진단에서 확인된 or_condition_missed
# 실패 유형). 기존 NO_RESTRICTION_PATTERNS를 재사용해 "또는/혹은" 주변에 그런 표현이
# 있는지만 본다 — 새 판단 로직을 만들지 않는다.
_OR_CONNECTOR_PATTERN = re.compile(r"또는|혹은")
_OR_CLAUSE_WINDOW = 40


def _clause_names_ksic_industry(clause: str, ksic_names: set[str]) -> bool:
    """이 구절이 KSIC 마스터에 실제로 등재된 업종명을 포함하는지 본다.
    새 단어 목록을 만들지 않고 이미 존재하는 explicit_match의 KSIC 색인을
    그대로 재사용한다 — notice별 hardcoding이 아니라 공식 KSIC 명칭 기준."""
    return any(name in clause for name in ksic_names)


def _or_condition_with_open_scope(text: str) -> bool:
    """두 가지 위험을 함께 본다:
    1) OR 주변에 명시적 업종무관 문구가 있음(기존 로직, 그대로 유지)
    2) [2026-09-13 추가] "A 또는 B" 구조에서 한쪽 구절에는 KSIC 업종명이
       전혀 없고 다른 쪽에만 있는 "mixed OR" — 예: "중소기업 또는 공장등록
       된 제조업체"(한쪽은 업종 무관 일반 기업 지칭, 한쪽만 '제조업체').
       이런 구조에서 업종이 있는 쪽만 보고 전체를 그 업종으로 확정하면
       위험하다(Resolver Phase 1에서 실측 확인된 detector gap, notice ID나
       그 안의 특정 단어를 하드코딩하지 않고 기존 KSIC 마스터 명칭 재사용으로
       일반화했다)."""
    from ksic_core.explicit_match import _load_ksic_index, NAME_LEVEL_ORDER

    index = _load_ksic_index()
    ksic_names = {name for lvl in NAME_LEVEL_ORDER for name in index[lvl] if len(name) >= 3}

    for m in _OR_CONNECTOR_PATTERN.finditer(text):
        window = text[max(0, m.start() - 60):m.end() + 60]
        if any(re.search(p, window) for p in NO_RESTRICTION_PATTERNS):
            return True

        left = text[max(0, m.start() - _OR_CLAUSE_WINDOW):m.start()]
        right = text[m.end():m.end() + _OR_CLAUSE_WINDOW]
        left_has_industry = _clause_names_ksic_industry(left, ksic_names)
        right_has_industry = _clause_names_ksic_industry(right, ksic_names)
        if left_has_industry != right_has_industry:  # 한쪽만 업종명을 담고 있음
            return True
    return False


def detect_resolver_risk_signals(text: str) -> dict:
    """Rule이 이미 아는 위험 신호를 LLM Resolver에게 요약해서 넘긴다.

    Resolver의 최종 판단을 대신하지 않는다 — Rule이 이미 갖고 있는 함정
    어휘(개방형 나열, OR조건, 제외/참고문맥, 비대상 역할, 넓은 정책용어)를
    참고 신호로만 전달해서, Resolver가 원문을 처음부터 자유롭게 읽다가
    Rule이 이미 막아둔 실패를 반복하지 않게 한다."""
    return {
        "open_ended_list_detected": bool(
            OPEN_ENDED_CATCHALL_PATTERN.search(text) or _OPEN_ENDED_LIST_GENERAL.search(text)
        ),
        "or_condition_with_open_scope_detected": _or_condition_with_open_scope(text),
        "exclusion_mentioned": any(re.search(p, text) for p in EXCLUSION_PATTERNS),
        "reference_context_present": any(w in text for w in REFERENCE_CONTEXT_WORDS),
        "non_target_role_present": any(w in text for w in NON_TARGET_ROLE_WORDS),
        "broad_field_term_present": any(w in text for w in BROAD_FIELD_TERMS),
        "explicit_no_restriction_present": any(re.search(p, text) for p in NO_RESTRICTION_PATTERNS),
    }


# 코드 패턴: KSIC는 2~5자리로 제시되는 경우가 있음. 알파벳 대분류 접두사도 허용.
_ALPHA_NUMERIC_PATTERN = re.compile(r"\b([A-U])\s*[-:]?\s*(\d{2,5})\b", re.I)
_NUMERIC_CODE_PATTERN = re.compile(r"\b\d{4,5}\b")
_WILDCARD_CODE_PATTERN = re.compile(r"\b(\d{2,3})\s*\*")
_RANGE_PATTERN = re.compile(r"\b(\d{4,5})\s*[~∼〜–—-]\s*(\d{4,5})\b")
_NTS_CODE_PATTERN = re.compile(r"\b\d{6}\b")

NEAR_CONTEXT_WINDOW = 280
FAR_CONTEXT_WINDOW = 1600
FAR_CLUSTER_WINDOW = 220


@dataclass(frozen=True)
class CodeOccurrence:
    code: str
    start: int
    end: int
    role: str  # positive | excluded | partial_exclusion | exclusion_exception | non_target | neutral
    reason: str
    source: str = "ksic"

    def to_dict(self):
        return asdict(self)


def _last_match_pos(patterns: Iterable[str], text: str) -> int:
    last = -1
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            last = max(last, m.start())
    return last


def _last_positive_match_pos(text: str) -> int:
    """positive 패턴이 '지원제외 대상 업종' 내부에서 잡히는 것을 막는다."""
    last = -1
    for pat in POSITIVE_TARGET_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            around = text[max(0, m.start() - 18):min(len(text), m.end() + 6)]
            if "제외" in around or "제한" in around:
                continue
            last = max(last, m.start())
    return last


def _section_context_before(text: str, pos: int, max_chars: int = 9000) -> str:
    """붙임/별표 단위 표의 문맥을 유지한다. 긴 제외표에서 헤더가 1,400자보다
    멀어져도 같은 붙임 안이면 제외 상태를 유지하기 위함.

    [2026-09-13 수정] "붙임 1 ... 지원 제외대상 붙임 2 ... 평균매출액 기준"처럼
    서로 다른 붙임 제목이 표 2단 레이아웃이 한 줄로 깨지면서 붙어버리는
    경우(실측: PBLN_124699, 지원제외 [별표]와 소상공인 매출액기준표가
    한 줄에 합쳐짐), 가장 가까운 경계 하나만 앵커로 삼으면 그 직전 경계의
    제목(제외 헤더)을 통째로 잃는다. 경계끼리 짧은 간격(같은 줄/문단)으로
    몰려 있으면 그 군집의 첫 경계부터 살려서 반환한다."""
    start = max(0, pos - max_chars)
    chunk = text[start:pos]
    boundaries = list(re.finditer(r"(?:붙임|븥임|별표)\s*\d*", chunk, flags=re.I))
    if boundaries:
        cluster_gap = 120
        anchor = len(boundaries) - 1
        while anchor > 0 and boundaries[anchor].start() - boundaries[anchor - 1].end() <= cluster_gap:
            anchor -= 1
        return chunk[boundaries[anchor].start():]
    return chunk[-1800:]


def _local_context(text: str, start: int, end: int, before: int = 260, after: int = 160) -> str:
    return text[max(0, start - before): min(len(text), end + after)]


def _paragraph_before(text: str, pos: int, max_chars: int = 900) -> str:
    # 빈 줄이 없는 PDF/HWP 추출도 많아서 최대 길이 가드를 둔다.
    p = text.rfind("\n\n", max(0, pos - max_chars), pos)
    if p == -1:
        p = max(0, pos - max_chars)
    else:
        p += 2
    return text[p:pos]


def _nearest_context_distance(text: str, pos: int, words: Iterable[str], max_window: int) -> int | None:
    """후보 앞쪽의 가장 가까운 문맥어 거리(기존 의미 유지)."""
    start = max(0, pos - max_window)
    chunk = text[start:pos]
    best = None
    lower = chunk.lower()
    for word in words:
        idx = lower.rfind(word.lower())
        if idx >= 0:
            d = len(chunk) - idx
            if best is None or d < best:
                best = d
    return best


def _next_context_distance(text: str, pos: int, words: Iterable[str], max_window: int) -> int | None:
    """후보 뒤쪽에 KSIC 헤더가 이어지는 표(QR 메뉴판 같은 추출 순서) 대응."""
    end = min(len(text), pos + max_window)
    chunk = text[pos:end]
    lower = chunk.lower()
    best = None
    for word in words:
        idx = lower.find(word.lower())
        if idx >= 0:
            if best is None or idx < best:
                best = idx
    return best


def _looks_like_reference_context(text: str, start: int, end: int) -> bool:
    local = _local_context(text, start, end, before=220, after=120)
    paragraph = _paragraph_before(text, start, max_chars=650)
    if any(w in local or w in paragraph for w in REFERENCE_CONTEXT_WORDS):
        return True
    return _has_bare_scale_hint(local, paragraph)


def _strong_reference_section_before(text: str, pos: int, max_chars: int = 5000) -> str:
    """마지막 '참고N/첨부N/붙임N/별첨N' 경계부터 후보까지의 문맥을 반환한다.

    소상공인 규모기준표 같은 참고표가 실제 문서에서는 '참고'가 아니라
    '[첨부3] 소상공인 기준...'처럼 첨부/붙임/별첨으로 표시되는 경우가 많다.
    '참고'만 찾으면 이런 표를 못 잡아서, 표 안의 아무 KSIC 대분류(예: 보건업)나
    positive로 잘못 뽑히는 문제가 있었다.
    """
    start = max(0, pos - max_chars)
    chunk = text[start:pos]
    matches = list(re.finditer(r"\[?(?:참고|첨부|붙임|별첨)\]?\s*\d+", chunk, flags=re.I))
    if not matches:
        return ""
    return chunk[matches[-1].start():]


def _looks_like_strong_reference_section(text: str, start: int, end: int) -> bool:
    section = _strong_reference_section_before(text, start)
    if not section:
        return False
    prefix = section[:700]
    return any(w in prefix for w in STRONG_REFERENCE_SECTION_WORDS)


def _looks_like_embedded_false_compound(text: str, start: int, end: int, candidate_text: str | None) -> bool:
    """짧은 업종명이 다른 단어 내부에 들어간 대표 오탐을 차단한다."""
    if not candidate_text:
        return False
    before1 = text[start-1:start] if start > 0 else ""
    after1 = text[end:end+1]
    if candidate_text == "광업" and before1 == "관":
        return True  # 관광업
    if candidate_text == "금융업" and after1 == "법":
        return True  # 금융업법
    return False


def _sentence_context(text: str, start: int, end: int, max_chars: int = 220) -> str:
    """후보가 속한 문장/줄만 잘라낸다. 다음 문장의 '숙박업소/투자기관' 같은
    역할 단어가 앞 문장의 정상 지원업종을 오염시키는 것을 막는다."""
    left_bound = max(0, start - max_chars)
    right_bound = min(len(text), end + max_chars)
    prev_positions = [text.rfind(sep, left_bound, start) for sep in ["\n", ".", "。", ";", "；"]]
    left = max(prev_positions)
    left = left + 1 if left >= 0 else left_bound
    next_positions = []
    for sep in ["\n", ".", "。", ";", "；"]:
        p = text.find(sep, end, right_bound)
        if p >= 0:
            next_positions.append(p)
    right = min(next_positions) if next_positions else right_bound
    return text[left:right]


def _looks_like_non_target_role(text: str, start: int, end: int) -> bool:
    # 역할 단어는 동일 문장/줄에서만 강하게 본다.
    local = _sentence_context(text, start, end)
    return any(w in local for w in NON_TARGET_ROLE_WORDS)


def _looks_like_department_or_org_name(text: str, start: int, end: int, candidate_text: str | None) -> bool:
    """짧은 업종명이 부서/기관명 일부인 경우를 차단한다.
    예: '식품위생농업과'의 농업, '보건위생과'의 보건 등.
    """
    if not candidate_text:
        return False
    if candidate_text not in {"농업", "어업", "광업", "보건업", "금융업", "숙박업", "제조업", "건설업"}:
        return False
    after = text[end:min(len(text), end + 8)]
    before = text[max(0, start - 20):start]
    if re.match(r"\s*(?:과|팀|부|센터|본부|국|실|담당|담당자)", after):
        return True
    if any(w in before for w in ["문의", "담당", "부서"]):
        return True
    return False


def _is_partial_exclusion(text: str, start: int, end: int) -> bool:
    # '33409 중 ...'처럼 코드 전체가 아니라 일부만 제외하는 표기.
    after = text[end:min(len(text), end + 30)]
    before = text[max(0, start - 120):start]
    return bool(re.match(r"\s*중(?:\s|$|[\(（])", after)) and _last_match_pos(EXCLUSION_PATTERNS, before) >= 0


def classify_occurrence_role(
    text: str,
    start: int,
    end: int,
    *,
    candidate_text: str | None = None,
    candidate_kind: str = "code",
) -> tuple[str, str]:
    """한 번의 등장 위치가 신청기업의 지원업종 문맥인지 판정한다.

    가장 가까운 positive/exclusion 헤더를 비교하는 방식이라, 문서 앞쪽의
    '지원제외'가 2천자 뒤의 새로운 지원대상 표까지 오염시키는 문제를 줄인다.
    """
    text = str(text)
    local = _local_context(text, start, end, before=220, after=180)
    before = text[max(0, start - 1400):start]
    section_before = _section_context_before(text, start)

    # 강한 '참고N 기업규모/확인기준'은 direct-code 판정보다 우선한다.
    if _looks_like_strong_reference_section(text, start, end):
        return "non_target", "소상공인/소기업 규모·확인용 참고표 문맥"

    if candidate_kind == "name" and _looks_like_embedded_false_compound(
        text, start, end, candidate_text
    ):
        return "non_target", "다른 단어 내부의 부분 문자열"

    if _is_partial_exclusion(text, start, end):
        return "partial_exclusion", "'중' 표기의 부분제외"

    # 붙임/별표 자체가 '지원 제외 업종/대상' 표이면, 표 내부의 '사업 대상'
    # 같은 일반 문구가 positive 헤더로 오인되지 않도록 섹션 성격을 고정한다.
    section_prefix = section_before[:420]
    if _last_match_pos(EXCLUSION_PATTERNS, section_prefix) >= 0:
        if any(re.search(p, local, flags=re.I) for p in EXCLUSION_EXCEPTION_PATTERNS):
            return "exclusion_exception", "지원제외 붙임/별표의 예외 문맥"
        return "excluded", "지원제외 붙임/별표 문맥"

    # 붙임/별표 경계가 있으면 그 경계 이전의 오래된 지원/제외 헤더는 끊는다.
    recent_chunk = text[max(0, start - 9000):start]
    has_appendix_boundary = bool(re.search(r"(?:붙임|븥임|별표)\s*\d*", recent_chunk, flags=re.I))
    header_context = section_before if has_appendix_boundary else before
    pos_header = _last_positive_match_pos(header_context)
    neg_header = _last_match_pos(EXCLUSION_PATTERNS, header_context)

    # 제외 섹션이 더 최근이면 먼저 제외/예외 판정.
    if neg_header > pos_header:
        if any(re.search(p, local, flags=re.I) for p in EXCLUSION_EXCEPTION_PATTERNS):
            return "exclusion_exception", "지원제외표의 예외/재포함 문맥"
        return "excluded", "지원제외/참여제외 문맥"

    # 일반 positive 섹션 안에서 '음료 제조업 제외'처럼 후보 바로 뒤에
    # 제외어가 붙는 경우. 멀리 떨어진 다른 업종의 '제외'까지 먹지 않도록 좁게 본다.
    # 후보와 같은 줄에 바로 붙은 "제외"만 본다.
    # \s는 개행까지 먹기 때문에 다음 섹션의 "지원 제외 업종"을
    # 앞 코드의 제외표시로 오인할 수 있어 같은 줄만 검사한다.
    # [2026-09-13 수정] "제외"뿐 아니라 "해당하지 않음/해당되지 않음/아님/불가"
    # 처럼 같은 뜻의 부정 표현도 흔하다(실측: PBLN_125715 "단순 주류
    # 유통·판매업 및 주점업은 해당하지 않음" — 기존 정규식은 "제외"만 잡아서
    # 이 부정 표현을 놓쳤다).
    after_short = text[end:min(len(text), end + 24)].partition("\n")[0]
    if re.match(
        r"^[ \t]*(?:[·ㆍ,，/][ \t]*)?(?:은|는|을|를)?[ \t]*"
        r"(?:(?:지원[ \t]*)?제외|해당(?:되지|하지)[ \t]*않|해당[ \t]*안|아님|불가)",
        after_short, flags=re.I,
    ):
        return "excluded", "업종명/코드 뒤에 직접 붙은 제외/부정 문구"

    if _looks_like_non_target_role(text, start, end):
        return "non_target", "협력·수행·구매·투자·직무·학력 등 비신청기업 문맥"

    # 직접 코드가 '신청대상/지원업종' 바로 아래에 있으면 주변의 다른 예시 문구보다
    # 이 근거를 우선한다(QR 메뉴판 PDF처럼 앞 문단의 '예시'가 붙는 추출 대응).
    if candidate_kind == "code" and pos_header >= 0 and (len(header_context) - pos_header) <= 320:
        return "positive", "지원대상/신청자격/지원업종 문맥의 직접 코드"

    if (candidate_kind == "name" and candidate_text and
        re.search(r"(?:기업|업체|사업주|사업자|영위)", candidate_text) and
        pos_header >= 0 and (len(header_context) - pos_header) <= 320):
        return "positive", "지원대상 문맥의 기업·업체·사업주 직접 표현"

    if _looks_like_reference_context(text, start, end):
        return "non_target", "예시/규모기준/요율/평가항목 등 참고 문맥"

    # 착한가격업소류 공고: "신청대상 : 음식점, 이·미용업 등 개인서비스업종"처럼
    # 몇 개만 예시로 들고 "등"으로 열어두는 개방형 나열. 명시된 몇 개만 코드로
    # 확정하면 실제보다 좁게 잡는다(문서 자체의 붙임 예시표가 수십 개 업종을
    # 더 나열하는 경우가 많음). candidate_kind로 안 가리는 이유: 음식점/이·
    # 미용업/세탁업 등은 short_generic 목록(공식 대분류명)에 없는 동의어/색인어
    # 매칭이라 위 short_generic 체크에 안 걸림.
    if candidate_kind == "name" and (
        OPEN_ENDED_CATCHALL_PATTERN.search(local)
        or OPEN_ENDED_CATCHALL_PATTERN.search(_paragraph_before(text, start, max_chars=650))
    ):
        return "non_target", "개방형 나열(개인서비스업종/요금) — 명시된 예시만으로 전체 범위 확정 불가"

    if candidate_kind == "name" and _looks_like_department_or_org_name(text, start, end, candidate_text):
        return "non_target", "부서·기관명 일부로 등장한 업종명"

    # 짧고 범용적인 업종명은 제품·기술 표현 안에서 자주 오탐된다.
    if candidate_kind == "name" and candidate_text:
        short_generic = candidate_text in {
            "농업", "어업", "광업", "금융업", "숙박업", "병원", "대학교", "대학원",
            "제조업", "건설업", "보건업", "면세점",
        }
        if short_generic and any(w in local for w in PRODUCT_CONTEXT_WORDS):
            # '스마트 농업 자재', '농림식품 제품'처럼 제품/기술 분야 속 단어는
            # 지원대상 헤더가 가까워도 업종으로 확정하지 않는다. 단, 후보 바로
            # 주변에 '제조업체/제조기업/농업 영위기업'처럼 기업-업종 관계가
            # 직접 쓰인 경우만 살린다.
            direct_relation = bool(
                re.search(rf"{re.escape(candidate_text)}.{{0,12}}(?:기업|업체|사업자|영위)", local)
                or re.search(rf"(?:기업|업체|사업자).{{0,12}}{re.escape(candidate_text)}", local)
            )
            if not direct_relation:
                return "non_target", "제품·품목·기술 분야 속 범용 업종명"

    # 명시적인 target 헤더가 가까이 있으면 strong positive.
    if pos_header >= 0 and (len(header_context) - pos_header) <= 650:
        return "positive", "지원대상/신청자격/지원업종 문맥"

    # 업종명 바로 주변에서 '영위기업/업체/사업자'가 붙는 경우도 positive.
    if candidate_text:
        around = _local_context(text, start, end, before=80, after=90)
        if re.search(r"(?:영위|해당|관련).{0,20}(?:기업|업체|사업자)", around) or re.search(
            r"(?:기업|업체|사업자).{0,20}(?:영위|업종)", around
        ):
            return "positive", "영위기업/해당업종 직접 선언"

    return "neutral", "지원기업 업종인지 문맥상 확정되지 않음"


# G4: KSIC 10차 → 11차 코드 크로스워크. 공고/시행령이 구 코드를 인용하면
# 11차 유효코드 집합에 없어 탈락하던 문제를 보정한다.
_LEGACY_MAP_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "ksic_legacy_map.csv"
)
_legacy_map: dict[str, str] | None = None


def _load_legacy_map() -> dict[str, str]:
    """{구코드_10차: 신코드_11차}. 1:N(확인필요)은 제외 — 자동변환 안 함."""
    global _legacy_map
    if _legacy_map is not None:
        return _legacy_map
    out: dict[str, str] = {}
    if os.path.exists(_LEGACY_MAP_CSV):
        with open(_LEGACY_MAP_CSV, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                old = (row.get("구코드_10차") or "").strip()
                new = (row.get("신코드_11차") or "").strip()
                rel = (row.get("관계") or "").strip()
                if old and new and "|" not in new and rel != "1:N_확인필요":
                    out[old] = new
    _legacy_map = out
    return _legacy_map


def _normalize_explicit_code(raw: str, valid_codes: set[str] | None) -> str | None:
    raw = raw.strip().upper().replace(" ", "")
    # C15211 -> 15211. 대분류 문자는 명칭매칭에서 처리하고 숫자부분만 사용.
    m = re.fullmatch(r"[A-U](\d{2,5})", raw)
    if m:
        raw = m.group(1)
    if valid_codes is not None and raw not in valid_codes:
        mapped = _load_legacy_map().get(raw)
        if mapped and mapped in valid_codes:
            return mapped
        return None
    return raw


def _expand_ranges(text: str, valid_codes: set[str] | None) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    if valid_codes is None:
        return out
    for m in _RANGE_PATTERN.finditer(text):
        a, b = m.group(1), m.group(2)
        if len(a) != len(b):
            continue
        try:
            ai, bi = int(a), int(b)
        except ValueError:
            continue
        if bi < ai or bi - ai > 50:  # 비정상적으로 큰 범위는 자동확장하지 않음
            continue
        for n in range(ai, bi + 1):
            code = str(n).zfill(len(a))
            if code in valid_codes:
                out.append((code, m.start(), m.end()))
    return out


def extract_explicit_ksic_details(text, valid_codes: set[str] | None = None) -> list[dict]:
    """원문에 직접 명시된 KSIC 코드의 occurrence별 상세 정보를 반환한다."""
    if not text:
        return []
    text = str(text)
    text_upper = text.upper()
    if not any(w.lower() in text.lower() for w in KSIC_CONTEXT_WORDS):
        return []

    candidates: list[tuple[str, int, int, str]] = []

    # 알파벳+숫자
    for m in _ALPHA_NUMERIC_PATTERN.finditer(text_upper):
        code = _normalize_explicit_code(m.group(1) + m.group(2), valid_codes)
        if code:
            candidates.append((code, m.start(), m.end(), "alpha_numeric"))

    # 숫자 코드. 4~5자리만 직접코드 후보로 본다.
    # - 앞쪽 KSIC 헤더는 넓게(붙임 표)
    # - 뒤쪽 KSIC 헤더는 좁게(QR처럼 표 아래에 주석이 오는 PDF 추출)
    # 이렇게 비대칭으로 둬서, KSIC 표 앞의 지번/연도 숫자가 뒤쪽 헤더 때문에
    # 끌려 들어오는 문제를 막는다.
    numeric_raw: list[tuple[str, int, int, int | None, int | None]] = []
    for m in _NUMERIC_CODE_PATTERN.finditer(text):
        code = _normalize_explicit_code(m.group(), valid_codes)
        if not code:
            continue
        prev_dist = _nearest_context_distance(text, m.start(), KSIC_CONTEXT_WORDS, FAR_CONTEXT_WINDOW)
        next_dist = _next_context_distance(text, m.end(), KSIC_CONTEXT_WORDS, 360)
        if prev_dist is None and next_dist is None:
            continue
        numeric_raw.append((code, m.start(), m.end(), prev_dist, next_dist))

    for code, start, end, prev_dist, next_dist in numeric_raw:
        if (prev_dist is not None and prev_dist <= NEAR_CONTEXT_WINDOW) or (
            next_dist is not None and next_dist <= NEAR_CONTEXT_WINDOW
        ):
            candidates.append((code, start, end, "numeric_near_header"))
            continue

        # KSIC 헤더 뒤 먼 표는 실제 코드가 여러 행 연속 등장한다.
        # 4자리 지번 하나가 우연히 KSIC 마스터와 겹치는 것을 줄이기 위해
        # 가까운 동료 후보를 최소 2개 요구한다.
        if prev_dist is not None and prev_dist <= FAR_CONTEXT_WINDOW:
            neighbor_count = sum(
                1
                for _, other_start, _, _, _ in numeric_raw
                if other_start != start and abs(other_start - start) <= FAR_CLUSTER_WINDOW
            )
            if neighbor_count >= 2:
                candidates.append((code, start, end, "numeric_table_cluster"))

    # 범위 표기(예: 42201~42204) 확장
    for code, start, end in _expand_ranges(text, valid_codes):
        prev_dist = _nearest_context_distance(text, start, KSIC_CONTEXT_WORDS, FAR_CONTEXT_WINDOW)
        next_dist = _next_context_distance(text, end, KSIC_CONTEXT_WORDS, 360)
        if prev_dist is not None or (next_dist is not None and next_dist <= NEAR_CONTEXT_WINDOW):
            candidates.append((code, start, end, "numeric_range"))

    # 와일드카드
    for m in _WILDCARD_CODE_PATTERN.finditer(text):
        dist = _nearest_context_distance(text, m.start(), KSIC_CONTEXT_WORDS, FAR_CONTEXT_WINDOW)
        if dist is None:
            continue
        prefix = m.group(1)
        if valid_codes is None or prefix in valid_codes:
            candidates.append((prefix + "*", m.start(), m.end(), "wildcard"))

    # occurrence별 role 판정. 같은 코드라도 positive/excluded가 각각 존재할 수 있으므로
    # code 문자열만으로 dedup하지 않는다.
    details: list[CodeOccurrence] = []
    seen = set()
    for code, start, end, source_kind in sorted(candidates, key=lambda x: (x[1], x[0])):
        role, reason = classify_occurrence_role(text, start, end, candidate_text=code, candidate_kind="code")
        # KSIC 헤더 바로 뒤의 코드표는 role이 neutral이어도 direct positive로 본다.
        if role == "neutral":
            # 가까운 단일 코드뿐 아니라, 헤더에서 멀지만 실제 코드표 클러스터로
            # 판정된 후보도 positive로 인정한다. reference/non-target/exclusion은
            # 위 classify_occurrence_role에서 이미 neutral이 아니므로 여기로 오지 않는다.
            max_dist = NEAR_CONTEXT_WINDOW if source_kind == "numeric_near_header" else FAR_CONTEXT_WINDOW
            dist = _nearest_context_distance(text, start, KSIC_CONTEXT_WORDS, max_dist)
            if dist is not None and source_kind in {
                "numeric_near_header", "numeric_table_cluster", "numeric_range", "wildcard", "alpha_numeric"
            }:
                role, reason = "positive", "KSIC/업종코드 표에 직접 명시"
        key = (code, start, end, role)
        if key in seen:
            continue
        seen.add(key)
        details.append(CodeOccurrence(code, start, end, role, reason, source_kind))

    return [d.to_dict() for d in details]


def extract_explicit_ksic(text, valid_codes=None):
    """기존 호출부 호환용: ``[(code, is_excluded), ...]`` 반환."""
    details = extract_explicit_ksic_details(text, valid_codes=valid_codes)
    out = []
    seen = set()
    for d in details:
        if d["role"] in {"non_target", "neutral", "exclusion_exception", "partial_exclusion"}:
            continue
        item = (d["code"], d["role"] == "excluded")
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_nts_codes_details(text: str) -> list[dict]:
    """국세청 6자리 업종코드 occurrence별 상세 탐지."""
    if not text:
        return []
    text = str(text)
    if not any(w in text for w in NTS_CONTEXT_WORDS):
        return []

    details = []
    seen = set()
    for m in _NTS_CODE_PATTERN.finditer(text):
        dist = _nearest_context_distance(text, m.start(), NTS_CONTEXT_WORDS, 450)
        if dist is None:
            continue
        role, reason = classify_occurrence_role(
            text, m.start(), m.end(), candidate_text=m.group(), candidate_kind="code"
        )
        if role == "neutral" and dist <= 220:
            role, reason = "positive", "국세청 업종코드 헤더에 직접 명시"
        key = (m.group(), m.start(), role)
        if key in seen:
            continue
        seen.add(key)
        details.append({
            "code": m.group(),
            "start": m.start(),
            "end": m.end(),
            "role": role,
            "reason": reason,
            "source": "nts",
        })
    return details


def extract_nts_codes(text):
    """기존 호출부 호환용: ``[(nts_code, is_excluded), ...]`` 반환."""
    out = []
    seen = set()
    for d in extract_nts_codes_details(text):
        if d["role"] in {"non_target", "neutral", "exclusion_exception", "partial_exclusion"}:
            continue
        item = (d["code"], d["role"] == "excluded")
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


# G3: '공장등록'이 신청자격/지원조건의 필수 요건이면 사실상 제조업 대상이다.
# (중기법 시행령 별표3의 규모기준이 공장등록·제조시설로 제조업을 정의하는 것과 같은 맥락)
_FACTORY_REQ = re.compile(
    r"공장\s*등록(?:증)?\s*(?:을|이|를|은|후|\s)*"
    r"(?:필한|필하고|필하였|하고|한|된|되어|완료|마친|마치고|보유|갖춘|가동)"
    r"|(?:공장|제조시설|생산시설)\s*(?:을|를)?\s*(?:보유|갖추|등록|운영|가동)"
    r"(?:하고\s*있는|하는|한|중인|해야)"
    r"|공장\s*등록\s*후\s*가동"
)
# 제출서류 목록에 '공장등록증 사본'으로만 등장하면 자격요건이 아니다.
_FACTORY_DOC_ONLY = re.compile(
    r"(?:제출|구비|첨부|필요)\s*서류|서류\s*목록|사본\s*(?:각)?\s*\d*\s*부|"
    r"공장\s*등록증\s*사본|등록증\s*사본"
)
# '본사 또는 공장', '본사·연구소·공장', '공장등록증 보유업체 제외'처럼
# 공장이 필수요건이 아닌(대안 나열이거나 제외 문맥인) 경우.
_FACTORY_ALT_ENTITY = r"본사|본점|사무소|사업장|지사|영업소|연구소|주소지|지점"
_FACTORY_NOT_REQ = re.compile(
    rf"(?:{_FACTORY_ALT_ENTITY})[\s·,/]*(?:또는|및)?[\s·,/]*"
    rf"(?:(?:{_FACTORY_ALT_ENTITY})[\s·,/]*(?:또는|및)?[\s·,/]*)*"
    r"(?:공장|생산시설|제조시설)"
    rf"|(?:공장|생산시설|제조시설)[\s·,/]*(?:또는|및)[\s·,/]*(?:{_FACTORY_ALT_ENTITY})"
    r"|공장\s*등록증?\s*보유\s*업체\s*제외"
    r"|공장\s*등록\s*(?:을)?\s*하지\s*않아도"
)
_TARGET_HDR = re.compile(
    r"지원\s*대상|신청\s*자격|지원\s*자격|지원\s*조건|지원\s*요건|대상\s*기업|"
    r"융자\s*대상|신청\s*대상|참여\s*대상|대상\s*업체|신청\s*요건"
)


def detect_manufacturing_requirement(text: str) -> dict | None:
    """신청자격/지원조건에 '공장등록(필수)'이 걸려 있으면 제조업(C) 대상으로 본다.

    - '제출서류 목록의 공장등록증 사본'처럼 서류일 뿐이면 발동하지 않는다.
    - 근거가 자격/조건 헤더 근처(±450자)에 있어야 한다.
    반환: 제조업(C) 결과 dict(MED) 또는 None.
    """
    if not text:
        return None
    for m in _FACTORY_REQ.finditer(text):
        window = text[max(0, m.start() - 220): m.end() + 120]
        if _FACTORY_DOC_ONLY.search(window):
            continue
        # '본사 또는 공장'처럼 공장이 대안일 뿐이면 제조업 요건이 아니다.
        if _FACTORY_NOT_REQ.search(text[max(0, m.start() - 60): m.end() + 30]):
            continue
        # 자격/조건 헤더가 앞쪽 450자 안에 있어야 함
        before = text[max(0, m.start() - 450): m.start()]
        if not _TARGET_HDR.search(before) and not _TARGET_HDR.search(window):
            continue
        return {
            "확정단계": "대분류",
            "확정코드": ["C"],
            "확정업종명": ["제조업"],
            "제외업종": [],
            "근거": {
                "매칭방식": "신청자격의 공장등록 필수요건 → 제조업(G3)",
                "근거문구": re.sub(r"\s+", " ", text[max(0, m.start() - 40): m.end() + 40]),
            },
            "ksic_confidence": "MED",
            "ksic_status": "대분류",
        }
    return None


def detect_explicit_scope(text: str) -> dict | None:
    """KSIC가 없을 때도 '업종무관'을 명시적으로 판정할 수 있는 최소 규칙.

    불명확한 '중소기업' 한 단어만으로 업종무관을 확정하지 않는다. 문서에
    '전 산업 분야/업종 제한 없음'처럼 직접적인 근거가 있을 때만 HIGH를 반환한다.
    넓은 기술분야 표현은 임의 KSIC 변환 금지 힌트로만 반환한다.
    """
    if not text:
        return None
    for pat in NO_RESTRICTION_PATTERNS:
        m = re.search(pat, text, flags=re.I)
        if m:
            return {
                "status": "업종무관",
                "confidence": "HIGH",
                "reason": f"명시적 업종무관 표현: {m.group(0)}",
            }

    # 명시적 "전 업종" 표현이 없어도, 지원대상 문장이 기업규모/기업형태만
    # 제시하고 업종·산업·분야 제한을 두지 않는 경우는 '업종무관' MED로 분리한다.
    target_match = re.search(r"(?:지원|모집|신청|사업)\s*대상", text, flags=re.I)
    if target_match:
        seg = text[target_match.start():min(len(text), target_match.start() + 900)]
        general_entity = bool(re.search(
            r"(?:중소기업|중견기업|소상공인|창업기업|벤처기업|기업)",
            seg,
            flags=re.I,
        ))

        # '업종' 계열 단어가 있어도, 그게 실제 자격 제한이 아니라
        # (a) 소상공인 규모기준(상시근로자수/매출액)을 업종별로 나열했거나
        # (b) 지원제외 섹션 안에 있거나
        # (c) '지원분야/사업분야'처럼 지원 프로그램 종류(기술지원/마케팅 등)를
        #     가리키는 것뿐이면 진짜 limiter로 보지 않는다.
        # (이런 경우들 다 "업종 단어가 있다"는 이유만으로 업종무관 판정을
        #  막아버려서, 원래 이 분기가 잡아야 할 케이스를 놓치는 버그였음)
        SCALE_HINT = re.compile(r"상시근로자|근로자\s*수|매출액|명\s*미만|명\s*이상|억원|이하")
        EXCLUSION_HEADER = re.compile(r"지원\s*제외|신청\s*제외|제외\s*대상|제외\s*업종")
        PROGRAM_FIELD_PREFIX = re.compile(r"(?:지원|사업|모집)\s*$")

        limiter = False
        for lm in re.finditer(
            r"(?:업종|산업|분야|제조업|관광|바이오|섬유|반도체|식품|농어업|수산|"
            r"소프트웨어|디자인|모빌리티|의료기기|의약품|화장품|건설업|정보통신)",
            seg,
            flags=re.I,
        ):
            before = seg[max(0, lm.start() - 40):lm.start()]
            after = seg[lm.end():lm.end() + 40]
            if SCALE_HINT.search(before + after):
                continue
            # 제외 섹션 헤더는 "근처"에 있을 때만 유효하다 - 900자 창
            # 앞쪽 아무데서나 "지원제외" 한 마디가 나왔다고 그 뒤에 나오는
            # 무관한 단어까지 전부 제외섹션 안이라고 오판하면 안 된다.
            nearby_before = seg[max(0, lm.start() - 300):lm.start()]
            if EXCLUSION_HEADER.search(nearby_before):
                continue
            if lm.group(0) == "분야" and PROGRAM_FIELD_PREFIX.search(seg[max(0, lm.start() - 6):lm.start()]):
                continue
            limiter = True
            break

        if general_entity and not limiter:
            return {
                "status": "업종무관",
                "confidence": "MED",
                "reason": "지원대상이 기업규모/기업형태로만 정의되고 업종 제한 문구가 없음",
            }

    # 과잉 의미확장을 막기 위한 신호. '특정불가' 자체를 HIGH로 확정하는 용도가 아니라
    # LLM/사람 검토로 넘길 이유를 남긴다.
    found = [term for term in BROAD_FIELD_TERMS if term in text]
    if found:
        return {
            "status": "특정불가",
            "confidence": "LOW",
            "reason": "넓은 기술/산업 분야 표현만 존재: " + ", ".join(found[:5]),
        }
    return None


# 명시적 업종무관 선언 — 최우선 override 규칙. detect_explicit_scope와 별개 함수로
# 둔 이유: detect_explicit_scope는 "다른 경로가 다 실패했을 때의 fallback"이라
# 문서 전체를 느슨하게 훑지만, 이건 direct-code/name매칭이 이미 뭔가 찾았어도
# 무시하고 덮어써야 하므로 훨씬 좁고 보수적인 조건(같은 문장 + 지원 관련
# 키워드 근접 + '제외' 문맥 아님)만 인정한다. 기존 NO_RESTRICTION_PATTERNS는
# 건드리지 않는다(detect_explicit_scope의 검증된 동작을 그대로 유지하기 위해).
#
# PBLN_124861: 원문에 "지원대상 : 업종 무관"이 명시돼 있는데도, 문서 뒷부분의
# 참고용 코드 목록(관광업 세부코드)에 끌려가 "복수산업 15개코드"로 잘못 확정됨.
INDUSTRY_AGNOSTIC_OVERRIDE_PATTERNS = [
    r"\b업종\s*무관\b",
    r"\b업종\s*제한\s*(?:없|없음|무)",
    r"\b업종에\s*관계없이",
    r"\b전\s*업종\b",
    r"\b모든\s*업종\b",
    r"\b업종\s*구분\s*(?:없|없음|무)",
]
_OVERRIDE_SUPPORT_WORDS = ("지원", "신청", "모집", "대상")
# PBLN_118336(회귀 발견): "5. 불건전업종, ... 융자지원 제한업종에 해당하는 기업"
# — "전 업종" 패턴이 "불건전업종" 내부에 부분문자열로 오탐 매칭됐던 사례
# (→ 위 패턴에 \b 경계를 추가해 근본 수정). '제한'을 가드에 통째로 추가하는
# 건 시도했다가 되돌림 — "업종 제한 없음" 자체가 '제한'을 포함하는 정상
# 패턴이라 자기 자신을 걸러버리는 문제가 있었음.
_OVERRIDE_EXCLUSION_GUARD = re.compile(r"제외")


def detect_explicit_industry_agnostic_override(text: str) -> dict | None:
    """지원대상 문맥에서 명시적 '업종무관' 선언을 찾는다.

    - 패턴과 같은 문장(줄바꿈 기준)에 지원/신청/모집/대상 같은 지원 관련
      키워드가 있어야 한다 — 단순 언급이 아니라 지원조건 선언인지 확인.
    - 같은 문장에 '제외'가 있으면 제외 조건 설명일 수 있으므로 건너뛴다
      (예: "제외업종은 업종 무관하게 적용됨").
    """
    if not text:
        return None
    for pat in INDUSTRY_AGNOSTIC_OVERRIDE_PATTERNS:
        for m in re.finditer(pat, text, flags=re.I):
            line_start = text.rfind("\n", 0, m.start())
            line_start = 0 if line_start == -1 else line_start + 1
            line_end = text.find("\n", m.end())
            line_end = len(text) if line_end == -1 else line_end
            sentence = text[line_start:line_end]

            if _OVERRIDE_EXCLUSION_GUARD.search(sentence):
                continue
            if not any(w in sentence for w in _OVERRIDE_SUPPORT_WORDS):
                continue
            return {
                "status": "업종무관",
                "confidence": "HIGH",
                "reason": f"명시적 업종무관 선언(지원대상 문맥 override): {sentence.strip()[:120]}",
            }
    return None
