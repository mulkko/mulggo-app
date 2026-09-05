# ============================================================
# preprocessing/extract_region.py
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


# ============================================================
# 시/군/구 단위 지명 — 2026-09-01 추가
# 근거: "전북 기업성장 환류형 상생일자리" 공고 실측 — 원문엔 "전북특별자치도"가
# 문서 맨 앞 문단(지원대상 섹션보다 앞)에 있었고, "전주시·익산시·정읍시"처럼
# 시/군 단위로만 지역이 표현되는 경우도 실제로 확인됨. 광역시도 17개만으론
# 이런 표현을 못 잡아서 시/군 단위까지 확장.
# (구 단위는 제외 — 광역시 안의 구는 지역 하드필터 단위로는 너무 세밀해서
#  실익이 적고, 지명 자체가 여러 도시에서 겹치는 경우도 있어 오탐 위험 큼)
# ============================================================

SIGUNGU_MAP = {
    "수원시": "경기도", "성남시": "경기도", "고양시": "경기도", "용인시": "경기도",
    "부천시": "경기도", "안산시": "경기도", "안양시": "경기도", "남양주시": "경기도",
    "화성시": "경기도", "평택시": "경기도", "의정부시": "경기도", "시흥시": "경기도",
    "파주시": "경기도", "김포시": "경기도", "광명시": "경기도", "광주시": "경기도",
    "군포시": "경기도", "이천시": "경기도", "양주시": "경기도", "오산시": "경기도",
    "구리시": "경기도", "안성시": "경기도", "포천시": "경기도", "의왕시": "경기도",
    "하남시": "경기도", "여주시": "경기도", "동두천시": "경기도", "과천시": "경기도",
    "양평군": "경기도", "가평군": "경기도", "연천군": "경기도",
    "춘천시": "강원특별자치도", "원주시": "강원특별자치도", "강릉시": "강원특별자치도",
    "동해시": "강원특별자치도", "태백시": "강원특별자치도", "속초시": "강원특별자치도",
    "삼척시": "강원특별자치도", "홍천군": "강원특별자치도", "횡성군": "강원특별자치도",
    "영월군": "강원특별자치도", "평창군": "강원특별자치도", "정선군": "강원특별자치도",
    "철원군": "강원특별자치도", "화천군": "강원특별자치도", "양구군": "강원특별자치도",
    "인제군": "강원특별자치도", "고성군": "강원특별자치도", "양양군": "강원특별자치도",
    "청주시": "충청북도", "충주시": "충청북도", "제천시": "충청북도", "보은군": "충청북도",
    "옥천군": "충청북도", "영동군": "충청북도", "증평군": "충청북도", "진천군": "충청북도",
    "괴산군": "충청북도", "음성군": "충청북도", "단양군": "충청북도",
    "천안시": "충청남도", "공주시": "충청남도", "보령시": "충청남도", "아산시": "충청남도",
    "서산시": "충청남도", "논산시": "충청남도", "계룡시": "충청남도", "당진시": "충청남도",
    "금산군": "충청남도", "부여군": "충청남도", "서천군": "충청남도", "청양군": "충청남도",
    "홍성군": "충청남도", "예산군": "충청남도", "태안군": "충청남도",
    "전주시": "전북특별자치도", "군산시": "전북특별자치도", "익산시": "전북특별자치도",
    "정읍시": "전북특별자치도", "남원시": "전북특별자치도", "김제시": "전북특별자치도",
    "완주군": "전북특별자치도", "진안군": "전북특별자치도", "무주군": "전북특별자치도",
    "장수군": "전북특별자치도", "임실군": "전북특별자치도", "순창군": "전북특별자치도",
    "고창군": "전북특별자치도", "부안군": "전북특별자치도",
    "목포시": "전라남도", "여수시": "전라남도", "순천시": "전라남도", "나주시": "전라남도",
    "광양시": "전라남도", "담양군": "전라남도", "곡성군": "전라남도", "구례군": "전라남도",
    "고흥군": "전라남도", "보성군": "전라남도", "화순군": "전라남도", "장흥군": "전라남도",
    "강진군": "전라남도", "해남군": "전라남도", "영암군": "전라남도", "무안군": "전라남도",
    "함평군": "전라남도", "영광군": "전라남도", "장성군": "전라남도", "완도군": "전라남도",
    "진도군": "전라남도", "신안군": "전라남도",
    "포항시": "경상북도", "경주시": "경상북도", "김천시": "경상북도", "안동시": "경상북도",
    "구미시": "경상북도", "영주시": "경상북도", "영천시": "경상북도", "상주시": "경상북도",
    "문경시": "경상북도", "경산시": "경상북도", "군위군": "경상북도", "의성군": "경상북도",
    "청송군": "경상북도", "영양군": "경상북도", "영덕군": "경상북도", "청도군": "경상북도",
    "고령군": "경상북도", "성주군": "경상북도", "칠곡군": "경상북도", "예천군": "경상북도",
    "봉화군": "경상북도", "울진군": "경상북도", "울릉군": "경상북도",
    "창원시": "경상남도", "진주시": "경상남도", "통영시": "경상남도", "사천시": "경상남도",
    "김해시": "경상남도", "밀양시": "경상남도", "거제시": "경상남도", "양산시": "경상남도",
    "의령군": "경상남도", "함안군": "경상남도", "창녕군": "경상남도", "남해군": "경상남도",
    "하동군": "경상남도", "산청군": "경상남도", "함양군": "경상남도", "거창군": "경상남도",
    "합천군": "경상남도",
    "제주시": "제주특별자치도", "서귀포시": "제주특별자치도",
}
_SIGUNGU_PATTERN = "|".join(sorted(SIGUNGU_MAP.keys(), key=len, reverse=True))


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
# [2026-09-01 수정] 시/도뿐 아니라 시/군 단위(SIGUNGU_MAP)까지 "소재/관내"
# 패턴에서 인식하도록 확장 — "전주시에 소재한 바이오기업" 같은 표현 포착.
_BODY_PATTERN = re.compile(
    rf"({_BODY_REGION_PATTERN}|{_SIGUNGU_PATTERN})\s*(?:특별시|광역시|도|시|군|구)?\s*(?:내\s*)?(소재|관내)"
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
        found.append(_normalize_any_region(region))  # 시/도 약칭+시/군 단위 모두 정식 시/도명으로 통일

    # [2026-09-03 추가] "비수도권"처럼 정식 시/도명이 아닌 배제형 지역 표현은
    # 위 _BODY_PATTERN(지역명+소재/관내 인접)으로 못 잡히므로 줄 단위로 별도
    # 탐색한다. "신청자격" 섹션을 아예 못 찾은 문서(이 함수가 최후 폴백으로
    # 쓰이는 상황)에서도 걸리도록 문서 전체를 보되, 우대/가점/사후조건 문맥의
    # 줄은 실제 신청자격이 아니므로 같은 기준으로 제외한다.
    for line in text.split("\n"):
        if _EXCLUSION_REGION_TOKEN not in line:
            continue
        if any(marker in line for marker in _PREFERENCE_MARKERS):
            continue
        if any(marker in line for marker in _POST_SELECTION_MARKERS):
            continue
        found.append(_EXCLUSION_REGION_DISPLAY)

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

# [2026-09-01 수정] "지원대상"이 문서 안에 여러 번(진짜 자격조건 외에
# 무관한 곳에서도) 등장하는 경우가 실측 확인됨. "신청자격"/"신청대상"이
# 더 명확히 자격요건을 가리키는 용어라, 이걸 먼저 찾고 그게 없을 때만
# "지원대상"류로 넘어가도록 우선순위를 부여(리스트 순서 = 우선순위).
_TARGET_SECTION_TERMS = ["신청자격", "신청대상", "신청 자격", "신청 대상", "지원대상", "지원 대상", "접수대상", "접수 대상"]
# [2026-09-03 추가] "우선 선정"/"우선선정"/"가산점"도 우대와 같은 뜻(필수 자격이
# 아니라 심사 시 가점)으로 실측 확인됨(예: "비수도권 소재 중소기업 우선 선정").
_PREFERENCE_MARKERS = ["우대", "가점", "가산점", "우선지원", "우선 지원", "우선선정", "우선 선정"]
# [2026-09-01 추가] "선정 후에만 적용되는 조건"은 지금 신청 가능 여부와
# 무관하므로 지역 판단 근거에서 제외. 근거: "반도체 첨단패키징" 사례 —
# "지원대상: 국내 반도체 패키징 산업 종사 기업"(전국 신청 가능)인데,
# 바로 다음 줄 "전남광주통합특별시 외 기업: 선정 후... 이전 완료를
# 원칙으로 함"이 사후 이전조건인데도 지역조건으로 잘못 잡혔던 것을 정정.
_POST_SELECTION_MARKERS = ["선정 후", "선정후", "협약체결", "이전 계획", "이전 완료", "이전 후"]


# [2026-09-02 추가] 자격/대상 문맥에 "전국"이 직접 명시된 경우를
# 추론이 아니라 '명시적 전국'으로 확정한다.
# 예: "접수대상 : 전국 로봇 제조 또는 부품 연관 기업"
# 단순히 문서 어딘가에 '전국'이 등장하는 것은 잡지 않고,
# 신청자격/신청대상/지원대상/접수대상 같은 자격 헤더와 가까운 문맥만 본다.
_EXPLICIT_NATIONWIDE_ELIGIBILITY_PATTERNS = [
    re.compile(r"(?:신\s*청\s*자\s*격|신\s*청\s*대\s*상|지\s*원\s*대\s*상|접\s*수\s*대\s*상)[^\n]{0,180}?전\s*국"),
    re.compile(r"(?:신\s*청\s*자\s*격|신\s*청\s*대\s*상|지\s*원\s*대\s*상|접\s*수\s*대\s*상)[^\n]{0,180}?(?:소\s*재\s*지|지\s*역)\s*무\s*관"),
]


def _has_explicit_nationwide_eligibility(text):
    """지원/신청/접수 대상·자격에 전국/지역무관이 직접 명시됐는지 확인."""
    if not text:
        return False
    return any(p.search(text) for p in _EXPLICIT_NATIONWIDE_ELIGIBILITY_PATTERNS)


# [2026-09-03 추가] "비수도권"처럼 특정 시/도 이름이 아니라 배제형으로 지역을
# 표현하는 경우 — 근거: LLM 재검증(gpt-4o-mini)에서 "희망하는 비수도권 소재의
# 팹리스 기업" 같은 표현이 128건 중 다수 실측 확인됨. 시/도 사전에 없는 표현이라
# 기존 _BODY_PATTERN(정식 지역명 + 소재/관내)으로는 못 잡혀서 별도 토큰으로 탐지.
# "지원대상" 섹션 안에서만 인식(우대/사후조건 줄 필터링이 이미 적용되는 범위) —
# 문서 전체에 대해 열면 정책설명 등 무관한 문맥까지 주울 위험이 있어 범위를 좁힘.
_EXCLUSION_REGION_TOKEN = "비수도권"
_EXCLUSION_REGION_DISPLAY = "비수도권(수도권 제외 전체)"

_ALL_REGION_PATTERN = _BODY_REGION_PATTERN + "|" + _SIGUNGU_PATTERN


def _normalize_any_region(name):
    """시/도 약칭·정식명 + 시/군 단위까지 전부 정식 시/도 명으로 정규화."""
    if name in SINGLE_REGION_MAP:
        return SINGLE_REGION_MAP[name]
    if name in SIGUNGU_MAP:
        return SIGUNGU_MAP[name]  # 시/군 -> 상위 시/도로 승격
    return name


def _extract_target_section_block(text, max_length=400):
    """text_clean.py의 extract_target_section()과 같은 기법(글자 사이
    공백/개행 관대 매칭)을 재사용해서 "지원대상"류 섹션 블록 하나를 뽑는다.

    [2026-09-01 정리] 두 가지를 다 시도해봤고 둘 다 부작용이 있었음:
      - "첫 매칭만 사용": "지원대상"이 여러 번 나오는데 첫 번째가 지역과
        무관한 경우(전북 상생일자리)를 놓침
      - "모든 매칭을 합쳐서 사용": 같은 용어가 문서 뒤쪽에 또 나오면서
        무관한 지역명을 새로 주워오는 부작용 발견(바이오매스 사례)
    최종적으로는 "용어 우선순위(신청자격 > 지원대상) + 그 용어의 첫 매칭만"
    으로 절충 — 완벽하진 않지만 실측상 두 부작용을 둘 다 최소화함."""
    # 모든 후보 용어의 첫 등장 위치를 비교해 문서에서 가장 먼저 나오는
    # 자격/지원대상 섹션을 사용한다.
    # 이유: 신청서 양식 뒤쪽의 "신청대상자" 같은 문구가 본문 앞쪽의 실제
    # "지원대상"보다 우선 선택되는 오탐을 방지하기 위함.
    candidates = []
    for term in _TARGET_SECTION_TERMS:
        loose_pattern = re.compile(r"\s*".join(re.escape(ch) for ch in term))
        m = loose_pattern.search(text)
        if m:
            candidates.append((m.start(), m.end(), term))

    if not candidates:
        return None

    _, end, _ = min(candidates, key=lambda x: x[0])
    return text[end:end + max_length]


def _find_region_in_target_section(full_text):
    """
    [2026-09-01 수정] 도입부까지 훑는 걸 시도했다가 되돌림 — "산업통상자원부와
    전남광주통합특별시가 지원하는"처럼 "공동 주최/지원 기관"이 도입부에
    언급되는 경우까지 지역으로 착각하는 새 오탐이 발견됨(반도체·휴머노이드
    사례). 신청기업이 실제로 어디 지역이어야 하는지는 "지원대상/신청자격"
    섹션에만 있다고 보고, 그 섹션만 본다(도입부는 안 봄). 대신 그 섹션
    안에서 시/군 단위 지명(SIGUNGU_MAP)까지 찾도록 범위만 확장함.

    반환값 3가지:
      (region_list)  -> 지원대상 섹션 안에서 "우대" 아닌 지역 발견
      []             -> 섹션은 찾았는데 지역이 전혀 없음(="전국" 강한 신호)
      None           -> 지원대상 섹션 자체를 못 찾음(판단 불가, 폴백 필요)
    """
    if not full_text:
        return None

    block = _extract_target_section_block(full_text)
    if block is None:
        return None

    found = []
    for line in re.split(r"[\n]", block):
        if any(marker in line for marker in _PREFERENCE_MARKERS):
            continue  # "우대/가점" 표시된 줄의 지역명은 근거로 안 씀
        if any(marker in line for marker in _POST_SELECTION_MARKERS):
            continue  # "선정 후" 등 사후조건 줄의 지역명도 신청조건 아니므로 제외
        # [2026-09-01 추가] 「...」(행사명·사업명 따옴표) 안에 있는 지역명은
        # 신청기업의 소재지가 아니라 행사 이름의 일부일 수 있어 제외.
        # 근거: "「2026 생활지원 서비스로봇 대구 국제 로봇산업전」 모집공고"에서
        # "대구"는 행사 개최지명일 뿐 신청기업 소재지 조건이 아니었음.
        line_without_titles = re.sub(r"「[^」]*」", "", line)
        if _EXCLUSION_REGION_TOKEN in line_without_titles:
            found.append(_EXCLUSION_REGION_DISPLAY)
        for m in re.finditer(_ALL_REGION_PATTERN, line_without_titles):
            found.append(_normalize_any_region(m.group(0)))

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
      'explicit_nationwide'
          -> 지원/신청/접수 대상·자격에 '전국'이 직접 명시됨(확정)
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
            # [2026-09-02 추가] 자격/대상 문맥에 "전국" 또는 "지역 무관"이
            # 직접 명시되어 있으면 다른 지역명 추정보다 우선해 전국으로 확정.
            if _has_explicit_nationwide_eligibility(full_text):
                return {"display": "전국(무관)", "regions": None, "status": "explicit_nationwide"}

            # [2026-09-01 수정] 3순위와 동일하게, "지원대상" 섹션은 찾았는데
            # 그 안에 지역이 아예 없으면(빈 리스트) 그 자체가 강한 "전국"
            # 신호이므로 즉시 확정한다 — 이전엔 이 분기가 빠져서 "국내"라고
            # 명시된 반도체 첨단패키징 사례가 엉뚱하게 전남광주로 오판정됨.
            section_result = _find_region_in_target_section(full_text)
            if section_result is not None:
                if section_result:
                    return {"display": " / ".join(section_result), "regions": section_result,
                            "status": "parsed_from_fulltext"}
                else:
                    return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}

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
            # [2026-09-02 추가] 지원/신청/접수 대상·자격에 전국이 명시된 경우
            # fallback이 아니라 명시적 전국으로 처리한다.
            if _has_explicit_nationwide_eligibility(full_text):
                return {"display": "전국(무관)", "regions": None, "status": "explicit_nationwide"}

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
            # [2026-09-03 수정] 이 분기(3순위)만 found 리스트 결과를 그냥 버리고
            # 무조건 "추정 전국"으로 떨어지는 구멍이 있었음 — 2순위(중앙부처)
            # 분기는 이미 이 결과를 쓰고 있었는데 여기만 빠져 있었음. 실측으로
            # "춘천시 소재 기업" 같은 문구가 있는데도 추정으로 잘못 분류된
            # 사례를 LLM 재검증으로 발견해 정정.
            if found:
                return {"display": " / ".join(found), "regions": found, "status": "parsed_from_fulltext"}
        # [2026-09-01 변경] "소관기관 이름을 그대로 지역으로 믿는" 것도 확실한
        # 근거가 아니라 추정일 뿐이므로, 명확한 신호(제목태그·지원대상 섹션
        # 명시)가 없으면 전국으로 기본 처리(회원님 지시 반영).
        return {"display": "전국(무관)", "regions": None, "status": "inferred_no_restriction"}

    # 4순위: 요약문에서 "{지역} 소재/관내" 탐색 (최후 폴백)
    found = _scan_text_for_region(bsns_sumry_cn if not isinstance(bsns_sumry_cn, str) else _strip_html(bsns_sumry_cn))
    if found == "__NO_RESTRICTION__":
        return {"display": "전국(무관)", "regions": None, "status": "no_restriction"}
    if found:
        return {"display": " / ".join(found), "regions": found, "status": "parsed_from_body"}

    # [2026-09-01 변경] 끝까지 못 찾으면 "확인불가"가 아니라 "전국(무관)"으로
    # 기본 처리(회원님 지시 반영). status는 추정임을 구분할 수 있게 남겨둠.
    return {"display": "전국(무관)", "regions": None, "status": "inferred_no_restriction"}


# ============================================================
# K-Startup(창업진흥원) 전용 — 2026-09-04 추가
#
# [발견 경위] 100건 표본에 extract_region()을 그대로 돌렸더니 100/100건이
# "전국(무관)"으로 나왔는데, 원본 supt_regin 필드를 까보니 실제론 39/100건이
# 특정 지역(서울16·경기10·대구3 등)이었음. extract_region()은 "구조화된
# 지역 필드가 아예 없는" 기업마당을 위해 텍스트에서 지역을 추론하도록 만든
# 함수라, K-Startup처럼 이미 깨끗한 구조화 필드가 있는 경우엔 그 필드를
# 보지도 않고 텍스트 추론만 하다가 다 놓치고 폴백값(전국)을 뱉은 것.
#
# 그래서 K-Startup은 추론이 아니라 "이미 있는 값을 표준 명칭으로 정규화"만
# 하면 됨 — SINGLE_REGION_MAP(위에서 이미 검증된 테이블)을 그대로 재사용.
# ============================================================

_KSTARTUP_MULTI_SPLIT_RE = re.compile(r"[,/·、]")


def normalize_kstartup_region(supt_regin):
    """
    K-Startup 원본 "지원지역"(supt_regin) 필드를 직접 정규화한다.
    extract_region()과 달리 텍스트에서 추론하지 않는다 — 이미 구조화된
    값이 주어지므로 추론이 오히려 정보를 잃어버림(위 발견 경위 참고).

    Parameters
    ----------
    supt_regin : str   원본 값. 예: '경기', '전국', '대구'.
                        콤마/슬래시로 여러 지역이 같이 오는 경우도 방어적으로 처리.

    Returns
    -------
    dict — extract_region()과 동일한 형태 {"display", "regions", "status"}.
    상태값은 기존 체계를 그대로 재사용/확장:
      'explicit_nationwide'      -> 원본값이 '전국'(또는 동의어)
      'parsed_from_source_field' -> 원본 구조화 필드를 SINGLE_REGION_MAP으로 직접
                                     정규화(신규 status. 텍스트 추론이 전혀 없어
                                     기존 'parsed'류보다도 신뢰도 높음 — 확정 처리)
      'unparsed'                 -> 값이 비어있거나 SINGLE_REGION_MAP에 없는
                                     처음 보는 표기(조용히 버리지 않고 원본값 보존)
    """
    raw = (supt_regin or "").strip()

    if not raw or raw in ("전국", "전국(무관)", "제한없음", "지역무관"):
        return {"display": "전국(무관)", "regions": None, "status": "explicit_nationwide"}

    tokens = [t.strip() for t in _KSTARTUP_MULTI_SPLIT_RE.split(raw) if t.strip()]

    resolved, unknown = [], []
    for tok in tokens:
        if tok in SINGLE_REGION_MAP:
            resolved.append(SINGLE_REGION_MAP[tok])
        elif tok in SINGLE_REGION_MAP.values():
            resolved.append(tok)  # 이미 정식 명칭이면 그대로 사용
        else:
            unknown.append(tok)

    if not resolved:
        # 처음 보는 표기 -> 조용히 잃어버리지 않고 원본값을 그대로 보존,
        # 사람이 확인하도록 unparsed로 남김
        return {"display": raw, "regions": [raw], "status": "unparsed"}

    if unknown:
        # 일부만 정규화됐으면 안전한 쪽(unparsed)으로 낮추되 값은 보존
        return {"display": " / ".join(resolved + unknown), "regions": resolved + unknown, "status": "unparsed"}

    return {"display": " / ".join(resolved), "regions": resolved, "status": "parsed_from_source_field"}


def _strip_html(raw):
    if not isinstance(raw, str):
        return ""
    t = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    import html
    return html.unescape(t)
