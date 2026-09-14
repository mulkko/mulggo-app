# ============================================================
# ksic_core/text_clean.py
#
# 목적
# ------------------------------------------------------------
# 기업마당 API 원문(bsnsSumryCn 등)은 HTML이 섞여 있고
# 사람이 미리 정리해둔 "지원대상_산업업종" 같은 컬럼이 없다.
#
# 이 모듈은 실제 API 응답 원문에서
# 검색(임베딩)에 쓸 텍스트를 만드는 역할만 한다.
# 산업 판단 로직은 여기 넣지 않는다 (rule_detectors.py에서 처리).
# ============================================================

import re
import html


def clean_html(raw):
    """
    bsnsSumryCn 같은 HTML 텍스트를 정제된 평문으로 변환.

    - <br>, </p> 는 줄바꿈으로 치환 (문장 경계 보존)
    - 나머지 태그는 제거
    - &nbsp; &amp; 등 HTML entity 디코딩
    - 빈 줄 제거
    """

    if not raw or not isinstance(raw, str):
        return ""

    text = raw

    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)

    text = re.sub(r"<[^>]+>", "", text)

    text = html.unescape(text)

    lines = [
        re.sub(r"[ \t]+", " ", line).strip()
        for line in text.split("\n")
    ]

    lines = [line for line in lines if line]

    return "\n".join(lines)


def extract_bullet_lines(cleaned_text):
    """
    ☞ 로 시작하는 bullet 라인만 추출.

    기업마당 공고 원문 관찰 결과, 지원대상/지원내용이
    이 bullet 라인에 정리되어 있는 경우가 많음.
    (규칙이지만 특정 공고 문구가 아니라 "이 사이트의 서식 패턴"이므로
    Gold 10건 하드코딩과는 성격이 다름 — 여러 공고에서 일관되게 확인됨)
    """

    bullets = []

    for line in cleaned_text.split("\n"):

        line = line.strip()

        if line.startswith("☞"):
            bullets.append(line.lstrip("☞").strip())

    return bullets


from ksic_core.file_extract import get_notice_full_text


def make_search_text(row):
    """
    우선순위:
    1. 원본 텍스트에서 '지원대상' 블록만 추출 성공 시 그것만 사용 (가장 깨끗함)
    2. 실패하면 원본 텍스트 전체 사용 (기존 방식)
    3. 원본 확보 자체 실패하면 요약문+해시태그 폴백
    """

    parts = []
    extraction_method = "fallback"

    full_text, status = get_notice_full_text(row.get("printFlpthNm", ""))

    if full_text:
        target_section = extract_target_section(full_text)

        if target_section:
            parts.append(target_section)
            extraction_method = "targeted_section"
        else:
            parts.append(full_text)
            extraction_method = "full_text"
    else:
        cleaned = clean_html(row.get("bsnsSumryCn", ""))
        bullets = extract_bullet_lines(cleaned)

        if row.get("trgetNm"):
            parts.append(str(row["trgetNm"]).strip())

        if bullets:
            parts.append(bullets[0])
        else:
            parts.append(cleaned)

    if row.get("pblancNm"):
        parts.append(str(row["pblancNm"]).strip())

    if row.get("hashtags"):
        parts.append(str(row["hashtags"]).strip())

    parts = [p for p in parts if p]

    seen = set()
    result = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            result.append(p)

    return " | ".join(result), status, extraction_method

def split_into_chunks(text, min_length=8):
    """
    긴 텍스트를 줄 단위로 쪼갠다.
    너무 짧은 줄(번호만 있거나 의미 없는 줄)은 제외.
    """

    lines = text.split("\n")

    chunks = []
    for line in lines:
        line = line.strip()
        if len(line) >= min_length:
            chunks.append(line)

    return chunks

import re


POSITIVE_TARGET_TERMS = [
    "지원대상", "신청자격", "신청대상", "사업대상", "지원자격",
    "모집대상", "참여자격", "선정대상", "참여대상", "참가자격",
    "수혜대상", "융자대상",
]

# 실측 확인 (2026-08, 원문 100건 전수 스캔) — 아래 용어들은 겉보기엔
# "OO대상" 패턴이지만 실제로는 무관한 내용이라 넣지 않음. 다시 추가하고
# 싶다면 반드시 원문 맥락부터 확인할 것 (이미 두 번 이 함정에 빠진 적 있음):
#   - "등록대상": 성과 등록 항목(바이어명 등) 안내, 기업 지원대상과 무관
#   - "중소기업대상": "OO대상 수상업체"(어워드 이름)이지 "중소기업을 대상으로"가 아님
#   - "지급대상"/"수행대상": 대부분 배제·제재 조항 맥락이라 오탐 위험 높음, 보류


def extract_target_section(text, max_length=400):
    """
    [버그2 수정] 이전엔 문서에서 가장 먼저 나온 매칭 딱 하나만 사용했음.
    근데 실측 확인 결과, 한 문서에 "지원대상"류 표현이 여러 번 나오는데
    앞쪽 것이 업종과 무관한 경우가 실제로 있었음
    (예: "지원 대상 : 체험 소모품, 1회용 도구..." 처럼 "지원 물품" 얘기가
     먼저 나오고, 진짜 기업 자격 얘기("모집대상 및 분야: 사회연대경제기업...")
     는 그 뒤에 나옴).

    "이게 진짜 업종 얘기인지 물품 얘기인지"를 텍스트만 보고 정확히 구분하는
    규칙은 또 다른 하드코딩 함정이 되기 쉬우므로, 대신 매칭되는 모든 블록을
    다 모아서 반환한다. 진짜 업종 정보가 포함된 블록도 함께 들어가면
    Chroma 청킹검색 단계에서 각 줄 단위로 비교되기 때문에, 노이즈 블록이
    섞여도 진짜 신호가 사라지지 않고 같이 후보에 반영된다.
    """
    matches = []  # (pos, match_end)

    for term in POSITIVE_TARGET_TERMS:
        # PDF 추출 특성상 단어 중간에 줄바꿈/공백이 끼는 경우가 실측으로 확인됨
        # (예: "지원\n대상"). 글자 사이에 공백류를 허용해서 매칭.
        loose_pattern = re.compile(r"\s*".join(re.escape(ch) for ch in term))
        for m in loose_pattern.finditer(text):
            pos = m.start()
            context_before = text[max(0, pos - 6):pos]
            if "제외" in context_before:
                continue
            matches.append((pos, m.end()))

    if not matches:
        return None

    matches.sort(key=lambda x: x[0])

    CIRCLE_MARKERS = "○❍◯"

    # 각 매칭에 대해 블록(start, end) 범위를 먼저 전부 계산한다.
    block_ranges = []
    for start, match_end in matches:
        search_start = match_end
        search_zone = text[search_start:search_start + max_length]

        # 수정 — 가/나/다 글자 마커는 하위항목이므로 경계에서 제외, 숫자와 원문자류만 경계로 인정
        # 주의: "○"(U+25CB)와 "❍"(U+274D)는 육안으로 구분 안 되지만 다른 유니코드 문자.
        # 실라리안 공고 원문 실측 결과 ❍(U+274D)가 쓰였음을 확인 → 둘 다 커버.
        # ◯(U+25EF, LARGE CIRCLE)도 실무 문서에서 흔히 섞여 쓰이므로 함께 포함.
        next_marker = re.search(rf"[\n\s]\s*(?:\d+\.|[{CIRCLE_MARKERS}])\s", search_zone[1:])

        if next_marker:
            end = search_start + 1 + next_marker.start()
        else:
            end = min(search_start + max_length, len(text))

        block_ranges.append((start, end))

    # 블록 범위 기준으로 겹치는 것 제거 (한 블록 안에 다른 용어가 또 걸려서
    # 같은 내용을 중복으로 잘라내는 것 방지)
    deduped_ranges = []
    last_end = -1
    for start, end in block_ranges:
        if start < last_end:
            continue
        deduped_ranges.append((start, end))
        last_end = end

    blocks = []
    for start, end in deduped_ranges:
        block = text[start:end].strip()
        if block:
            blocks.append(block)

    if not blocks:
        return None

    return "\n".join(blocks)