# ============================================================
# ksic_core/extract_region.py
#
# 목적
# ------------------------------------------------------------
# 기업마당 공고에서 "지원 지역" 하드필터 값을 뽑아낸다.
# 기업마당 원본 API엔 K-Startup의 supt_regin 같은 구조화된 지역
# 필드가 없어서, 3단 폴백 체인으로 실측 근거를 갖고 추출한다.
#
# 재사용 원칙: 여기서 쓰는 원문(full_text)은 KSIC 매칭을 위해
# file_extract.py로 이미 한 번 다운로드·추출해둔 그 텍스트를 그대로
# 받아서 쓴다. 지역 추출을 위해 파일을 따로 또 받지 않는다.
#
# ------------------------------------------------------------
# 폐기/배제한 컬럼과 근거 (다시 시도하지 말 것)
# ------------------------------------------------------------
# - excInsttNm(수행기관명): 제목태그로 확정된 지역 20건과 대조 시
#   신뢰도 60%(12/20)에 그침. "기초자치단체"라는 값 자체가 지역명이
#   아닌 경우, "KOTRA대전세종충남지원본부"처럼 여러 지역을 동시에
#   관할하는 경우, "국방기술진흥연구소"처럼 전국단위 기관이 지역
#   공고를 수행하는 경우가 섞여있어 배제.
# - refrncNm(문의처, 전화번호): 지역번호(02/031/053 등) 추출 시도했으나
#   1,063건 중 8건(0.75%)만 지역번호 패턴이 나왔고, 그마저 25%만
#   실제 지역과 일치. 대부분 070(인터넷전화, 물리적 위치 무관) 번호라
#   신호로 쓸 수 없어 배제.
# ============================================================

import re

# ============================================================
# 1순위: 제목 대괄호 [지역] 태그 (실측 커버리지 68.6%, 1,589건 기준)
# 근거: 무작위 20건을 jrsdInsttNm과 교차검증한 결과 20/20 전부 일치.
# jrsdInsttNm이 중앙부처로 찍혀도 제목 태그가 더 정확한 사례까지 확인됨
# (예: "[충남]..." vs jrsdInsttNm="산업통상부").
# ============================================================

TITLE_TAG_PATTERN = re.compile(r"^\[([^\]]+)\]")

SINGLE_REGION_MAP = {
    "경기": "경기도", "경북": "경상북도", "경남": "경상남도", "충북": "충청북도",
    "강원": "강원특별자치도", "부산": "부산광역시", "전북": "전북특별자치도",
    "울산": "울산광역시", "인천": "인천광역시", "충남": "충청남도", "서울": "서울특별시",
    "전남광주": "전남광주통합특별시", "대구": "대구광역시", "대전": "대전광역시",
    "제주": "제주특별자치도", "광주": "광주광역시", "전남": "전라남도", "세종": "세종특별자치시",
}

# 실측 확인된 권역명(광역 묶음 표현) -> 소속 지역 리스트로 전개
REGION_GROUP_MAP = {
    "충청권": ["충청북도", "충청남도", "대전광역시", "세종특별자치시"],
    "호남권": ["전라북도", "전라남도", "광주광역시"],
    "비수도권": None,  # 수도권 제외 전체 -> 포함이 아니라 배제 목록이라 별도 표시
}


def _parse_title_tag(title):
    m = TITLE_TAG_PATTERN.match(str(title))
    if not m:
        return None
    tag = m.group(1)

    if "ㆍ" in tag or "·" in tag:
        parts = re.split(r"[ㆍ·]", tag)
        resolved = [SINGLE_REGION_MAP.get(p, p) for p in parts if p in SINGLE_REGION_MAP]
        if resolved:
            return resolved, "parsed_multi"

    if tag in REGION_GROUP_MAP:
        group = REGION_GROUP_MAP[tag]
        if group is None:
            return ["비수도권(수도권 제외 전체)"], "parsed_group_exclusion"
        return group, "parsed_group"

    if tag in SINGLE_REGION_MAP:
        return [SINGLE_REGION_MAP[tag]], "parsed"

    return None  # 태그는 있지만 알려진 지역명이 아닌 경우


# ============================================================
# 본문(요약문 또는 원문 전체)에서 "{지역명} 소재/관내" 패턴 탐색
# 공통 로직 — bsnsSumryCn(짧은 요약)과 원문(긴 전체 텍스트) 둘 다 이걸 씀
# 근거: "소재" 키워드는 "위치"와 "재료(소재부품)" 두 뜻이 있어 동음이의어
# 오탐 위험이 있음이 실측(15건 샘플 중 1건)으로 확인되어 회피 로직 포함.
# ============================================================

_REGION_NAMES_FOR_BODY = sorted(
    set(SINGLE_REGION_MAP.keys()) | set(SINGLE_REGION_MAP.values()), key=len, reverse=True
)
_BODY_REGION_PATTERN = "|".join(_REGION_NAMES_FOR_BODY)
_BODY_PATTERN = re.compile(
    rf"({_BODY_REGION_PATTERN})\s*(?:특별시|광역시|도|시|군|구)?\s*(?:내\s*)?(소재|관내)"
)


def _scan_text_for_region(text):
    if not text:
        return None
    if re.search(r"소재지\s*무관|지역\s*무관", text):
        return "__NO_RESTRICTION__"  # 명시적 "무관" 표현 발견

    found = []
    for m in _BODY_PATTERN.finditer(text):
        region, marker = m.group(1), m.group(2)
        after = text[m.end():m.end() + 3]
        if marker == "소재" and ("부품" in after or after.startswith("산업")):
            continue  # "소재부품"류 재료 의미 오탐 회피
        found.append(SINGLE_REGION_MAP.get(region, region))  # 짧은형/긴형 표기를 정식명으로 통일

    return list(dict.fromkeys(found)) if found else None


# ============================================================
# 2순위: jrsdInsttNm(소관기관명) — 중앙부처 목록
# ============================================================

CENTRAL_MINISTRIES = {
    "중소벤처기업부", "산업통상부", "과학기술정보통신부", "고용노동부",
    "기후에너지환경부", "지식재산처", "농림축산식품부", "해양수산부",
    "문화체육관광부", "보건복지부", "환경부", "국토교통부", "기획재정부",
}


# ============================================================
# "지원대상" 섹션 한정 지역 탐색 — 2026-09-01 추가
#
# 배경: "{지역} 소재/관내" 같은 긍정 패턴이 원문에 아예 없어도, "지원대상"
# 섹션 안에 지역 얘기가 통째로 없으면 그 자체가 "전국"이라는 신호다.
# 다만 "* 경기과학기술대학교... 우대"처럼 지원대상 섹션 안에 지역 관련
# 단어가 있어도, 그게 "우대"(필수 아닌 가점) 조건으로 붙어있으면 지역
# 확정 근거로 쓰면 안 된다 — 실측(바이오매스관련 사례)으로 확인된 패턴.
# ============================================================

_TARGET_SECTION_TERMS = ["지원대상", "신청자격", "신청대상", "지원 대상", "신청 대상"]
_PREFERENCE_MARKERS = ["우대", "가점"]


def _extract_target_section_block(text, max_length=400):
    """text_clean.py의 extract_target_section()과 같은 기법(글자 사이
    공백/개행 관대 매칭)을 재사용해서 "지원대상" 섹션 블록만 뽑는다.
    간단화 버전 — 첫 번째로 발견된 블록만 반환(지역 판단 용도로는 충분)."""
    for term in _TARGET_SECTION_TERMS:
        loose_pattern = re.compile(r"\s*".join(re.escape(ch) for ch in term))
        m = loose_pattern.search(text)
        if not m:
            continue
        start = m.end()
        block = text[start:start + max_length]
        return block
    return None


def _find_region_in_target_section(full_text):
    """
    반환값 3가지:
      (region_list)  -> 지원대상 섹션 안에서 "우대" 아닌 지역 발견
      []             -> 지원대상 섹션은 찾았는데 그 안에 지역이 전혀 없음
                         (= "전국"으로 확정해도 되는 강한 신호)
      None           -> 지원대상 섹션 자체를 못 찾음(판단 불가, 폴백 필요)
    """
    if not full_text:
        return None

    block = _extract_target_section_block(full_text)
    if block is None:
        return None

    found = []
    for line in re.split(r"[\n]", block):
        # 이 줄에 "우대/가점" 표시가 있으면, 이 줄 안의 지역명은 근거로 안 씀
        if any(marker in line for marker in _PREFERENCE_MARKERS):
            continue
        for m in re.finditer(_BODY_REGION_PATTERN, line):
            found.append(SINGLE_REGION_MAP.get(m.group(0), m.group(0)))

    return list(dict.fromkeys(found))  # 빈 리스트일 수도 있음(그게 정상 신호)


def extract_region(pblanc_nm, jrsd_instt_nm, bsns_sumry_cn, full_text=None):
    """
    지역 하드필터 값을 추출한다. 함수 하나로 통일 — 반환값(dict) 안에
    "바로 화면에 쓸 문자열"과 "DB 저장·로직 분기에 쓸 원본 값"을 같이 담는다.

    Parameters
    ----------
    pblanc_nm : str        공고명 (원본 pblancNm)
    jrsd_instt_nm : str     소관기관명 (원본 jrsdInsttNm)
    bsns_sumry_cn : str     사업요약내용 (원본 bsnsSumryCn, HTML 포함 가능)
    full_text : str | None  KSIC 매칭용으로 이미 추출해둔 원문(있으면 사용,
                             없으면 이 인자 없이 호출해도 됨 — 필수 아님)

    Returns
    -------
    dict {
        "display": str          -> 화면에 바로 쓸 문자열. 예: "대구광역시",
                                    "전국(무관)", "확인불가"
        "regions": list | None  -> 지역명 리스트(여러 개일 수 있음), 없으면 None
        "status": str           -> 아래 표 참고. DB notice_hard_filter.region_status에
                                    그대로 저장하는 값
    }

    status 값 의미(신뢰도 순):
      'parsed' / 'parsed_multi' / 'parsed_group' / 'parsed_group_exclusion'
          -> 제목 태그로 확정 (신뢰도 최상)
      'parsed_from_fulltext'
          -> 중앙부처라 전국 추정했다가, 원문에서 실제 지역을 발견해 정정
      'parsed_from_body'
          -> 요약문에서 발견 (최후 폴백)
      'inferred_no_restriction'
          -> 중앙부처 + 지역 조건 못 찾음 -> 전국 추정(확정 아님, 확인필요 권장)
      'inferred_from_jrsd'
          -> 소관기관 자체가 지자체명이라 그대로 사용(신뢰도 낮음)
      'no_restriction'
          -> "지역 무관" 등 명시적 무관 표현 발견(확정)
      'unparsed'
          -> 끝까지 못 찾음
    """
    # 1순위: 제목 태그
    tag_result = _parse_title_tag(pblanc_nm)
    if tag_result:
        regions, status = tag_result
        return {"display": " / ".join(regions), "regions": regions, "status": status}

    is_central = jrsd_instt_nm in CENTRAL_MINISTRIES

    # 2순위: 중앙부처인 경우 -> 바로 "전국"으로 단정하지 않고, 원문이 있으면
    # 먼저 검증한다. 근거: 100건 샘플 중 "산업통상부"(중앙부처) 소관인데
    # 원문엔 "대구광역시 소재"라고 명시된 사례를 실제로 발견함.
    if is_central:
        if full_text:
            found = _scan_text_for_region(full_text)
            if found == "__NO_RESTRICTION__":
                return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}
            if found:
                return {"display": " / ".join(found), "regions": found, "status": "parsed_from_fulltext"}
        return {"display": "전국(무관)", "regions": None, "status": "inferred_no_restriction"}

    # 3순위: 소관기관 자체가 지자체명이면 사용 — 단, jrsdInsttNm을 그대로
    # 믿기 전에 "지원대상" 섹션을 직접 뒤져서 더 정확한 신호가 있는지 먼저
    # 확인한다(2026-09-01 추가). 이게 jrsdInsttNm보다 우선함 — 실제 신청
    # 자격을 담은 섹션이라 소관기관보다 신뢰도가 높음.
    if jrsd_instt_nm and str(jrsd_instt_nm).strip():
        if full_text:
            section_result = _find_region_in_target_section(full_text)
            if section_result is not None:  # 지원대상 섹션을 찾긴 함
                if section_result:  # 그 안에 우대아닌 지역이 실제로 있음
                    return {"display": " / ".join(section_result), "regions": section_result,
                            "status": "parsed_from_target_section"}
                else:  # 섹션은 찾았는데 지역 얘기가 아예 없음 -> 전국 확정(추정 아님)
                    return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}

            found = _scan_text_for_region(full_text)
            if found == "__NO_RESTRICTION__":
                return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}
        return {"display": jrsd_instt_nm, "regions": [jrsd_instt_nm], "status": "inferred_from_jrsd"}

    # 4순위: 요약문에서 "{지역} 소재/관내" 탐색 (최후 폴백)
    found = _scan_text_for_region(bsns_sumry_cn if not isinstance(bsns_sumry_cn, str) else _strip_html(bsns_sumry_cn))
    if found == "__NO_RESTRICTION__":
        return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}
    if found:
        return {"display": " / ".join(found), "regions": found, "status": "parsed_from_body"}

    # [2026-09-01 변경] 끝까지 못 찾으면 "확인불가"가 아니라 "전국(무관)"으로
    # 기본 처리(회원님 지시 반영). status는 추정임을 구분할 수 있게 남겨둠.
    return {"display": "전국(무관)", "regions": None, "status": "inferred_no_restriction"}


def _strip_html(raw):
    if not isinstance(raw, str):
        return ""
    t = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    import html
    return html.unescape(t)
