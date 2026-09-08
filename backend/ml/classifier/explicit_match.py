# ============================================================
# ml/classifier/explicit_match.py
#
# match_ksic_by_name() — 오늘 세션의 핵심 결론:
# ------------------------------------------------------------
# 벡터 유사도(Chroma)로 KSIC를 "추측"하는 대신, KSIC 참고표에 있는
# 실제 업종 명칭이 원문에 문자 그대로(또는 근접하게) 나오는지
# "사전 찾기(deterministic lookup)"로 먼저 확인한다.
#
# bottom-up 원칙은 그대로 유지:
#   세세분류 명칭부터 찾아보고 없으면 세분류 -> 소분류 -> 중분류 -> 대분류
#   순으로 한 단계씩 위로 올라가며 찾는다.
#
# 실측 근거 (2026-08-29, 100건 원문 기준):
#   "철강산업", "제조업", "외식업", "이·미용업", "반려동물 연관산업",
#   "애니메이션" 등 명확한 업종명이 원문에 그대로 있는데도 Chroma
#   방식은 38/100건을 오판(특정불가 또는 엉뚱한 코드)했음.
#   문자열 매칭이면 이 케이스들이 전부 해결됨.
#
# [2026-09-08] KSIC 참고표 데이터 출처 변경 (CSV 파일 -> DB):
#   원래는 data/ksic_clean_v2.csv 파일을 직접 열어서 썼는데, 이 파일을
#   실행할 PC마다 일일이 복사해서 옮겨야 하는 문제가 있었다. 이 CSV의
#   내용이 DB의 ksic_codes 테이블과 100% 동일함을 확인(1202건 전수
#   대조, 불일치 0건)하고, _fetch_ksic_rows_from_db()로 DB 조회로
#   교체했다 — 매칭 알고리즘(콜로퀴얼 동의어 치환, 오탐 방지 블록리스트,
#   "제외" 문맥 판별 등 이 파일 전체에 걸친 로직)은 전부 그대로다.
#   그 결과 이 모듈은 이제 로컬 파일이 아니라 DB 접속(.env의 DB_HOST 등)이
#   있어야 동작한다 — 예전처럼 CSV 파일만 있으면 오프라인으로 돌아가던
#   방식이 아니게 됐다는 뜻이니, 이 코드를 새 환경에서 돌릴 땐 .env의
#   DB 접속 정보부터 확인할 것.
# ============================================================

import re

from backend.db.connection import get_connection

# bottom-up 순서 그대로 - 세세분류부터 대분류까지
NAME_LEVEL_ORDER = ["세세분류", "세분류", "소분류", "중분류", "대분류"]

LEVEL_TO_COLUMNS = {
    "세세분류": ("KSIC_세세분류명", "KSIC_코드"),
    "세분류":   ("KSIC_세분류명", "KSIC_세분류코드"),
    "소분류":   ("KSIC_소분류명", "KSIC_소분류코드"),
    "중분류":   ("KSIC_중분류명", "KSIC_중분류코드"),
    "대분류":   ("KSIC_대분류명", "KSIC_대분류코드"),
}

# 실측 확인(2026-08-29): 아래 명칭들은 실제 KSIC 등록명이지만 너무 짧고
# 일반적인 단어라서, 완전히 무관한 문맥에서 우연히 부분일치로 걸림.
#   - "대학교"(85302): "전남대학교"처럼 협력기관 이름에서 우연히 등장
#   - "전기업"(351): "이전기업"(이사한 기업)의 부분 문자열로 우연히 등장
#   - "경찰"(84404), "검찰"(84402): 결격사유 조항("경찰·검찰 조사")에서 등장
#   - "의원"(8620): "대의원 회의"의 부분 문자열로 우연히 등장
#   - "백화점"(47111): "○○백화점(1.5km)" 처럼 인근 시설 거리 기입 예시에서 등장
# 지어낸 목록이 아니라 실제 오탐 사례로 확인된 것만 추가. 앞으로 비슷한
# 사례 나오면 여기 추가할 것.
GENERIC_NAME_BLOCKLIST = {"대학교", "전기업", "경찰", "검찰", "의원", "백화점", "법원"}

# [2026-09-03 추가] 다수매칭(MAX_REASONABLE_MULTI_MATCH 초과) 시 무조건
# "확인필요"로 낮추던 걸 더 다듬는다 — 실측 확인: 지역혁신클러스터(반도체·
# 전자부품·자동차부품·소프트웨어 17개), 우주항공기업(항공기엔진·부품·탄소섬유·
# 로봇 등 17개) 같은 진짜 다중산업 선언도 개수만으로는 참고표와 구분이 안 됨.
# 반면 실제 참고표/제외목록 보일러플레이트는 거의 항상 이 특정 업종들(서로
# 무관한 금융·부동산·법무·수의·사행성 계열)을 2개 이상 포함하는 걸로 실측
# 확인됨 — 그래서 "개수"가 아니라 "이 시그니처 업종이 몇 개 섞여있는지"로
# 재판단한다. 2개 미만이면 진짜 다중산업으로 보고 정상 확정, 2개 이상이면
# 여전히 확인필요로 낮춘다.
KNOWN_EXCLUSION_BOILERPLATE_NAMES = {
    "주점업", "기타 주점업",
    "금융업", "연금업", "보험업", "금융 및 보험관련 서비스업",
    "부동산업", "부동산 분양 대행업", "부동산관련 서비스업",
    "법무관련 서비스업", "수의업",
    "경주장 및 동물 경기장 운영업", "경기장 운영업", "골프장 운영업",
    "카지노 운영업", "사행시설 관리 및 운영업", "기타 사행시설 관리 및 운영업",
    "무도장 운영업",
    "담배 도매업", "담배 소매업", "주류 도매업",
}
BOILERPLATE_SIGNATURE_THRESHOLD = 2

# 실측 확인: 일부 공고(특히 소상공인 경영환경개선류)는 "해당 기업의 주된
# 업종 분류기호"라는 KSIC 전체 참고표(체크리스트)를 통째로 첨부해둠.
# 이건 "이 업종들이 지원대상"이 아니라 신청자가 자기 업종에 체크하라는
# 행정 서식이므로, 매칭된 서로 다른 코드 수가 비정상적으로 많으면
# (실측 기준 대부분의 진짜 복수산업은 2~4개 이내) 참고표로 간주하고
# 특정불가로 되돌린다.
MAX_REASONABLE_MULTI_MATCH = 6

_ksic_index = None  # {"세세분류": {name: code, ...}, ...} 형태로 캐싱
_ksic_rows_cache = None  # ksic_codes 테이블 조회 결과 캐싱 (CSV DictReader와 동일한 키 구조)

# 실측 확인(2026-08-29, 원문 100건 기준): 공고 원문은 KSIC 공식 명칭이 아니라
# 구어체 표현을 쓰는 경우가 흔함. 지어낸 매핑이 아니라, 오늘 실제로 확인된
# 불일치 사례만 최소한으로 보정한다. 새 사례 나올 때마다 여기 추가할 것.
#
# 2026-08-29 2차 업데이트: GPT가 100건을 사람이 읽고 직접 판단한 정답지와
# 대조하여, 그 판단 근거에서 안전하게 일반화 가능한 것만 추가로 반영함.
# (모호하거나 여러 코드로 갈리는 것은 오탐 위험이 커서 제외 — 아래 주석 참고)
COLLOQUIAL_SYNONYMS = {
    "외식업": "음식점업",              # 착한가격업소 원문에서 확인
    "철강산업": "1차 철강 제조업",       # 당진 철강산업 공고에서 확인
    "이·미용업": "이용 및 미용업",       # 가운뎃점 압축 표기 -> 정확한 KSIC 복합명칭 있음(9611)
    "이‧미용업": "이용 및 미용업",       # 다른 유니코드 가운뎃점(U+2027)도 실제 원문에서 확인됨
    "석유화학": "석유화학계 기초 화학 물질 제조업",  # GPT 재검수 근거: 명시적 산업 대응 확인
    "비철": "1차 비철금속 제조업",
    "제조창업기업": "제조업",
    "게임콘텐츠": "게임 소프트웨어 개발 및 공급업",
    "블록체인": "응용 소프트웨어 개발 및 공급업",  # GPT: "블록체인 서비스 개발 기업은 응용SW개발로 대응"
    "반도체 패키징": "반도체 제조업",
}

# 아래는 추가했다가 실측으로 새 오탐이 발견되어 다시 제거한 것들 (기록용):
#   - "정유" -> "원유 정제처리업": "인정유무"(인정+유무), "지정유형"(지정+유형)에
#     우연히 부분일치. 2글자짜리라 대학교/경찰과 같은 종류의 함정.
#   - "공장등록" -> "제조업": 실제로는 "사업자등록증 또는 공장등록증 또는
#     연구소등록증 중 택1 제출" 식으로 여러 선택지 중 하나인 경우가 많아,
#     제조업으로 단정하면 안 됨. 처음 발견한 사례("공장등록 후 정상 가동 중인
#     기업"처럼 필수조건으로 명시된 경우)만 특별했던 것이지 일반화하면 안 됐음.

# 아래는 GPT 정답지에서 발견됐지만 의도적으로 추가하지 않은 것들 (이유 명시):
#   - "농림식품 관련 산업" -> 대분류 A + 중분류 10 (2개 코드로 동시에 감): 원문마다
#     농업 쪽 비중/식품가공 비중이 달라 일괄 매핑하면 과탐 위험 큼
#   - "소프트웨어업" -> 제조업/건설업/전기공사업/... (10개 이상 코드): 이건 GPT가
#     공고 원문의 "지원대상 업종" 표 전체를 다 읽고 판단한 것으로 추정되며,
#     단순 치환으로 일반화하면 오늘 고친 "참고표 통째매칭" 버그가 재발할 위험이 큼
#   - "관광식당업" -> 여행사업/자동차임대업/기념품소매업/음식점업 (4개 코드):
#     공고 하나의 여러 지원분야를 한꺼번에 나열한 것이라 "관광식당업"만 보고
#     4개 코드를 유추하면 다른 공고에 오적용될 위험이 큼

# 이런 문구가 매칭 위치 주변에 있으면, 그건 "신청기업 자신의 업종"이 아니라
# "공사를 맡길 하도급업체/용역업체 요건"인 경우가 실측으로 확인됨
# (정읍시 환경개선사업: "건축공사업 또는 전문건설업 등록 업체를 시공자로 선정"
#  -> 신청기업이 아니라 시공업체 얘기인데 "건설업"만 보고 오탐했었음
#  문경시 IoT사업: "3. 사물인터넷(IoT)설치 시공업체 참여 기준" 이라는 섹션제목
#  아래 "제조업체"가 나와서, 이것도 시공업체 얘기인데 신청기업 업종으로 오인했었음)
THIRD_PARTY_CONTEXT_WORDS = ["시공자", "시공업체", "설치업체", "협력업체", "용역업체", "하도급", "등록 업체를", "위탁업체"]

# [2026-09-03 추가] 실측 확인: 용산구 이태원 융자지원계획 공고 —
# "소상공인(상시근로자 5인 미만/광업ㆍ제조업ㆍ건설업ㆍ운수업 10인 미만)"은
# 이 공고의 실제 지원업종 선언이 아니라, 「소상공인기본법」상 업종별로
# 상시근로자 기준이 다르다는 걸 설명하는 표준 법정 정의 조항이다(광업·제조업·
# 건설업·운수업은 예외적으로 10인 미만까지 소상공인으로 인정, 그 외 업종은
# 5인 미만) — 이 문구는 전국 공고에 거의 그대로 반복되는 정형 문구라 업종
# 선언으로 오매칭됨.
# 진짜 "이 사업은 제조업 30인 미만 기업만 지원"류 개별 선언과 구분하려고,
# "5인 미만"(일반 기준)이 근처에 있고 + 매칭 바로 뒤에도 또 다른 숫자+인/명
# 미만이 붙는(광업ㆍ제조업ㆍ건설업ㆍ운수업 뒤에 10인 미만처럼) "두 기준 병기"
# 패턴일 때만 걸러낸다 — 숫자 기준이 하나뿐인 진짜 선언은 안 건드림.
SME_GENERAL_THRESHOLD_RE = re.compile(r"5\s*(?:인|명)\s*미만")
SME_THRESHOLD_AFTER_RE = re.compile(r"\d+\s*(?:인|명)\s*미만")

# 실측 확인: "(예) 사업자등록증의 종목으로 구분: (25294) 주형및금형제조업"처럼
# "예시"임을 명시한 경우, 그 예시 하나를 지원대상 전체로 착각하면 안 됨
EXAMPLE_MARKERS = ["(예)", "예시", "예 :", "예:", "예)"]

# 실측 확인: 본 공고와 무관한 다른 정책(재해중소기업 지원지침 등)의 조항이
# 참고용으로 통째로 인용된 경우, 그 안의 업종명을 본 공고 지원대상으로
# 착각하면 안 됨
UNRELATED_POLICY_CONTEXT = ["재해중소기업 지원지침", "재해자금 지원대상", "가점 대상"]

# 실측 확인: "농어업협력재단", "행정정보공동이용업무포털"처럼 짧은 실제
# 업종명(어업, 이용업 등)이 기관/시스템 이름의 일부로 우연히 포함된 경우.
# 매칭 위치 바로 뒤에 이런 접미사가 붙으면 업종명이 아니라 기관명으로 판단.
INSTITUTION_SUFFIX_AFTER = ["재단", "포털", "협회", "센터", "공단", "진흥원"]

# [2026-09-03 추가] "지원제외 업종" 표 바로 뒤에 예외적으로 특정 업종을 다시
# 포함시키는 각주가 붙는 사례가 실측 확인됨(용인시 특례보증: "지원 제외 업종"
# 표 뒤에 "* 사회적경제기업의 경우, 보건업(86) 영위기업도 육성자금 지원대상에
# 포함한다"). 이걸 그냥 "제외 문맥"으로만 보면 명시적으로 되살린 업종까지
# 잘못 제외된다. "지원대상에 포함" 같은 명시적 재포함 문구가 매칭 바로 뒤에
# 붙으면 제외 판정을 뒤집는다 — "부가세 포함"처럼 무관한 "포함" 오탐을
# 피하려고 "지원대상" 같이 나오는 경우만 좁혀서 인식한다.
INCLUSION_OVERRIDE_RE = re.compile(r"지원\s*대상\s*(?:에|으로)?\s*(?:도)?\s*포함")

# [2026-09-05 추가] 실측 확인: 강화군 소상공인 경영안정지원금 공고 — 별표1
# (지원대상 업종 표) 제목이 "생활밀접업종(인천광역시 소상공인통계, 소상공인
# 정책자금 지원 제외 업종 제외)"였음. "제외 업종"이라는 문구가 있긴 하지만
# 바로 뒤에 "제외"가 한 번 더 붙는 이중부정 구조라 "이미 제외 대상은 뺀
# (나머지) 목록"이라는 뜻 — 즉 뒤에 나오는 건 제외 목록이 아니라 정반대인
# 지원대상(포함) 목록이다. 이걸 일반 "제외 업종" 헤더로 오인해서 wide_window
# 안에서 뒤에 이어지는 지원대상 업종 표 전체(수십 개 항목)가 제외 목록으로
# 잘못 잡혔다. "제외 업종" 바로 뒤에 또 "제외"가 붙는 이 특정 이중부정
# 패턴만 헤더로 인정하지 않고 넘어간다.
#
# [2026-09-05 추가 2] 같은 공고에서 실측으로 하나 더 확인됨: "2. 지급
# 제외대상" 목록 안에 "□ 소상공인 정책자금 지원 제외 업종 [별표3] 사업자"라는
# 항목이 있는데, 이건 별표3 표 자체가 아니라 "별표3을 보라"는 단순 인용
# 문장이다. 그런데도 진짜 "제외 업종" 문구라서 헤더로 인정되어, 그 뒤 2,000자
# 안에 있는 별표1(지원대상 업종) 표 앞부분까지 다시 제외로 오염시켰다.
# 진짜 표 헤더(예: 이 공고의 실제 별표3 헤더 "...소상공인 정책자금 지원
# 제외 업종\n표준산업분류\n업종\n33409 중...")는 바로 뒤에 표 내용이 이어지지,
# "[별표N]" 같은 대괄호 인용표시가 붙지 않는다 — 그래서 매칭 바로 뒤에
# "[별표" / "(별표" 인용표시가 붙으면 표 헤더가 아니라 단순 인용으로 보고
# 넘어간다.
_APPENDIX_CITATION_RE = re.compile(r"^\s*[\[(]?\s*별표")

# [2026-09-05 추가 3] 같은 공고에서 하나 더 확인됨: "2. 지급 제외대상" 목록보다도
# 앞선 문장("사업자등록 상 지원대상 업종이면서 정책자금 지원제외 업종인 경우:
# 미지급")은 표 헤더가 아니라 단순 조건 설명 한 문장인데, "제외 업종"이라는
# 진짜 문구라서 여전히 헤더로 인정되고, wide_window(2,000자) 반경 안에 있는
# 별표1(전혀 다른, 지원대상 업종을 나열하는 표)의 앞부분 항목들까지 다시
# 제외로 오염시켰다. 이 문장과 별표1 항목들 사이에는 "별표1"이라는 새 부록
# 경계가 하나 끼어 있다 — 즉 이미 다른 표/섹션으로 넘어간 뒤이므로 그 이전
# 문장의 "제외 문맥"이 거기까지 이어진다고 보면 안 된다. 매칭 지점과 현재
# 위치 사이에 "별표숫자" 경계가 하나라도 새로 나타나면 그 매칭은 무효로
# 본다(자기 자신이 속한 별표의 헤더는 그 경계 앞에 있으므로 영향 없음).
_APPENDIX_BOUNDARY_RE = re.compile(r"별표\s*\d")

# "제외 업종 제외" 이중부정 구간을 다른 정규식이 재해석하지 못하도록 통째로
# 지워버리는 데 쓴다 (아래 in_exclusion_section 계산부에서 사용).
_DOUBLE_NEGATIVE_EXCLUSION_RE = re.compile(r"제외\s*업종\s*제외")


def _has_real_exclusion_header(window):
    for m in re.finditer(r"제외\s*업종", window):
        after = window[m.end():m.end() + 15]
        if re.match(r"\s*제외", after):
            continue
        if _APPENDIX_CITATION_RE.match(after):
            continue
        if _APPENDIX_BOUNDARY_RE.search(window[m.end():]):
            continue
        return True
    return False


def _fetch_ksic_rows_from_db():
    """
    ksic_codes 테이블을 최초 1회만 읽어서, ksic_clean_v2.csv를 csv.DictReader로
    읽었을 때와 동일한 키(KSIC_대분류코드 등)를 가진 딕셔너리 리스트로 변환한다.

    [2026-09-08] 원래 data/ksic_clean_v2.csv 파일을 직접 열어서 썼는데, 이 파일의
    내용이 ksic_codes 테이블과 100% 동일함을 확인(1202건 전수 대조, 불일치 0건)하고
    DB 조회로 교체함 — 팀원마다 CSV 파일을 따로 복사해서 옮겨야 하는 문제를 없애기
    위함. 아래 매칭 로직(콜로퀴얼 동의어, 오탐 방지 블록리스트 등)은 전부 이 함수가
    반환하는 딕셔너리의 키만 보고 동작하므로 그대로 유지된다.
    """
    global _ksic_rows_cache

    if _ksic_rows_cache is not None:
        return _ksic_rows_cache

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT code, name, large_code, large_name, medium_code, medium_name,
               small_code, small_name, detail_code, detail_name
        FROM ksic_codes
        """
    )
    db_rows = cur.fetchall()
    conn.close()

    _ksic_rows_cache = [
        {
            "KSIC_코드": code,
            "KSIC_세세분류명": name,
            "KSIC_대분류코드": large_code,
            "KSIC_대분류명": large_name,
            "KSIC_중분류코드": medium_code,
            "KSIC_중분류명": medium_name,
            "KSIC_소분류코드": small_code,
            "KSIC_소분류명": small_name,
            "KSIC_세분류코드": detail_code,
            "KSIC_세분류명": detail_name,
        }
        for code, name, large_code, large_name, medium_code, medium_name,
        small_code, small_name, detail_code, detail_name in db_rows
    ]
    return _ksic_rows_cache


def _load_ksic_index():
    """
    ksic_codes 테이블을 최초 1회만 읽어서 레벨별 {업종명: 코드} 인덱스를 만든다.
    이름 하나가 여러 코드에 걸치는 경우는 없음을 확인했음(2026-08-29 검증).
    """
    global _ksic_index

    if _ksic_index is not None:
        return _ksic_index

    index = {level: {} for level in NAME_LEVEL_ORDER}

    rows = _fetch_ksic_rows_from_db()

    for level, (name_col, code_col) in LEVEL_TO_COLUMNS.items():
        for row in rows:
            name = (row.get(name_col) or "").strip()
            code = (row.get(code_col) or "").strip()
            if name and code:
                index[level][name] = code

    _ksic_index = index
    return index


def _find_name_matches(text, names_by_length_desc):
    """
    텍스트 안에서 주어진 업종명들이 등장하는지 찾는다.
    긴 이름부터 먼저 확인해서, 짧고 일반적인 이름이 더 구체적인
    이름의 일부로 이미 매칭된 자리를 또 잡지 않도록 함.

    "제외" 문맥(매칭 위치 앞 6자 이내)에 있으면 제외목록으로 분리.
    """
    included = []   # (name, pos)
    excluded = []   # (name, pos)
    covered_ranges = []

    for name in names_by_length_desc:
        for m in re.finditer(re.escape(name), text):
            pos = m.start()
            end = m.end()

            # 이미 더 긴 이름에 포함된 위치면 중복 매칭 스킵
            if any(s <= pos and end <= e for s, e in covered_ranges):
                continue

            context_before = text[max(0, pos - 6):pos]
            if "제외" in context_before:
                excluded.append((name, pos))
            else:
                included.append((name, pos))

            covered_ranges.append((pos, end))

    return included, excluded


def match_ksic_by_name(text):
    """
    원문 텍스트에서 KSIC 업종명을 bottom-up으로 직접 매칭한다.

    [중요] 레벨 하나에서 매칭이 나왔다고 거기서 멈추지 않는다.
    실측 확인: 착한가격업소 원문("외식업 : 한식...", "개인서비스업 : 세탁업, 이용업...")에서
    "세탁업"은 세분류에서 바로 잡히지만, "외식업"에 대응하는 명칭은 다른 레벨에
    있을 수 있어 세분류에서 멈추면 놓친다. 그래서 5개 레벨을 전부 스캔하고,
    같은 텍스트 위치를 더 세밀한 레벨이 이미 차지했으면 그 자리의 상위레벨
    매칭은 중복으로 버린다 (bottom-up 우선순위는 유지하되, 서로 다른 위치의
    서로 다른 업종 언급은 전부 살린다).

    반환값:
        매칭 성공 시:
        {
            "확정단계": "세세분류" | ... | "대분류" | "복수산업",
            "확정코드": [코드, ...],
            "확정업종명": [업종명, ...],
            "제외업종": [{"명칭":.., "코드":..}, ...],   # 참고용, 하드필터에서 활용 가능
            "근거": {"매칭방식": "명시적 업종명 매칭", "레벨별_매칭": {...}}
        }
        매칭 실패 시: None (호출부에서 특정불가 등으로 처리)
    """
    if not text or not text.strip():
        return None

    # 구어체 표현을 KSIC 공식 명칭으로 미리 치환 (원문 위치가 밀리지 않도록
    # 같은 텍스트 안에 원래 구어체도 남겨두는 대신, 매칭 전용 사본에만 적용)
    search_text = text
    for colloquial, official in COLLOQUIAL_SYNONYMS.items():
        if colloquial in search_text and official not in search_text:
            search_text = search_text.replace(colloquial, official)

    index = _load_ksic_index()

    # [2026-09-03 시도 후 되돌림] "지원제외 업종 ... 붙임1 참조"처럼 실제 제외
    # 목록이 첨부파일에만 있고, 그 첨부 내용이 원문 추출 시 헤더로부터 2,700자
    # 넘게 떨어진 곳에 등장하는 사례가 있었다(포항시 카드수수료 지원사업 —
    # 카지노·무도장 등이 "지원업종"으로 오매칭됨). 참조 문구 발견 시 그 이후
    # 문서 끝까지를 "제외 의심 구간"으로 넓혀서 고쳐봤지만, 대구 중소기업
    # 경영안정자금 공고처럼 "가/나/다" 하위 프로그램이 여러 개 나열된 문서에서
    # 참조 문구보다 2,514자(포항시 사례보다도 짧은 거리) 뒤에 있는 완전히
    # 무관한 하위 프로그램의 정당한 업종 선언("제조업")까지 같이 죽이는 새
    # 오탐이 실측 확인되어 되돌림 — 거리만으로는 "첨부표 내용"과 "그냥 뒤에
    # 나온 무관한 섹션"을 구분할 수 없었다(포항시 2,709자 vs 대구 2,514자로
    # 폭이 겹침). 표 경계를 구조적으로 인식하는 방법이 필요해 보류.

    # 전체 매칭 결과를 (start, end, level, name, code) 형태로 다 모은다
    all_hits = []      # 포함
    all_excluded = []  # 제외

    for level in NAME_LEVEL_ORDER:
        name_to_code = index[level]
        names_sorted = sorted(
            (n for n in name_to_code if n not in GENERIC_NAME_BLOCKLIST),
            key=len, reverse=True
        )

        for name in names_sorted:
            for m in re.finditer(re.escape(name), search_text):
                pos, end = m.start(), m.end()
                context_before = search_text[max(0, pos - 6):pos]
                context_window = search_text[max(0, pos - 20):min(len(search_text), end + 20)]

                # [버그 수정] "지원 제외 업종" 같은 섹션 헤더가 몇 줄 위에만
                # 있고 개별 항목 바로 앞엔 "제외"가 없는 구조가 실측으로 확인됨
                # (건설·금융·보험·부동산업... 나열식). 바로 앞 6글자뿐 아니라
                # 현재 줄이 속한 문단(직전 빈 줄 또는 문서 시작까지) 안에
                # "제외" 관련 헤더가 있었는지도 함께 확인한다.
                paragraph_start = search_text.rfind("\n\n", 0, pos)
                paragraph_start = paragraph_start + 2 if paragraph_start != -1 else max(0, pos - 200)
                paragraph_context = search_text[paragraph_start:pos]
                fixed_window_before = search_text[max(0, pos - 400):pos]
                # [2026-09-03 추가] "지원제외 업종" 표는 400자 창도 못 덮을 만큼
                # 길게 나열되는 사례가 실측 확인됨 — "카지노 운영업/무도장 운영업/
                # 사행시설 관리 및 운영업" 등 표 뒤쪽 항목은 제외 헤더로부터
                # 1,000~1,600자 떨어져 있음(화성시 시장개척단·전남광주 소상공인
                # 판로·고성군 경영환경개선 등 여러 공고에서 동일 보일러플레이트로
                # 확인).
                #
                # [주의 — 최초 수정 후 실측으로 발견된 부작용] "업종" 대신 "대상"
                # 까지 넓혔더니, 이 사업 고유의 일반 자격조건 배제 목록("노후장비
                # 교체 제외" 등, 옥천군 환경개선사업 사례로 실측 확인)까지 걸려서
                # 무관한 매칭("전문건설업" 등)을 잘못 죽이는 부작용이 나왔음.
                # "지원제외 업종"은 산업분류 표에만 쓰이는 관용구라 넓혀도 안전하지만,
                # "지원제외 대상"은 일반 자격조건에도 널리 쓰여 넓히면 위험함 —
                # 그래서 "업종" 한정으로만 넓은 창(2,000자, 실측 최대거리 1,604자에
                # 여유)을 쓰고, "대상"은 원래 400자 창(paragraph_context)만 쓴다.
                wide_window_before = search_text[max(0, pos - 2000):pos]
                # [2026-09-05 추가 4] "정책자금 지원 제외 업종 제외)" 같은 이중부정
                # 문구는 `_has_real_exclusion_header`가 "제외 업종" 자체는 걸러주지만,
                # 그 안에 우연히 들어있는 "지원 제외"라는 부분 문자열이 바로 아래
                # `(참여|신청|지원)\s*제외` 정규식에 다시 걸려서 우회하는 문제가
                # 실측 확인됨(강화군 공고). 아래 세 정규식에 넣기 전에 이 이중부정
                # 구간 자체를 지워서, 그 안의 부분 문자열이 다른 패턴으로 재매칭되는
                # 걸 원천 차단한다.
                paragraph_context_checked = _DOUBLE_NEGATIVE_EXCLUSION_RE.sub(" ", paragraph_context)
                in_exclusion_section = bool(
                    _has_real_exclusion_header(paragraph_context_checked)
                    or re.search(r"제외\s*대상", paragraph_context_checked)
                    or re.search(r"(참여|신청|지원)\s*제외", paragraph_context_checked)
                    or _has_real_exclusion_header(wide_window_before)
                    or ("제외" in fixed_window_before and "배제" in fixed_window_before)
                )

                # 제3자(시공업체 등) 문맥도 마찬가지로 섹션 제목이 몇 줄 위에만
                # 있는 구조가 실측 확인됨 (문경시 IoT: "3. ...시공업체 참여 기준"
                # 이라는 소제목 아래에 실제 매칭은 한참 뒤에서 발생)
                is_third_party = (
                    any(w in context_window for w in THIRD_PARTY_CONTEXT_WORDS)
                    or any(w in paragraph_context for w in THIRD_PARTY_CONTEXT_WORDS)
                )

                # 예시로 든 것 하나를 전체 지원대상으로 착각하는 것 방지.
                # 실측: "(예)"가 매칭 지점에서 30자 이상 떨어진 경우도 있어
                # 좁은 context_window(±20자)로는 못 잡음 -> 문단 단위로 확인.
                is_example = (
                    any(w in context_window for w in EXAMPLE_MARKERS)
                    or any(w in paragraph_context for w in EXAMPLE_MARKERS)
                )

                # 본 공고와 무관한 다른 정책 조항이 인용된 경우 방지.
                # 실측: <표> 마커가 섞인 문서는 빈 줄이 불규칙해서 문단 경계
                # 탐지(rfind("\n\n"))가 중간에 끊길 수 있음 -> 고정 거리(400자)로도 확인.
                is_unrelated_policy = (
                    any(w in paragraph_context for w in UNRELATED_POLICY_CONTEXT)
                    or any(w in fixed_window_before for w in UNRELATED_POLICY_CONTEXT)
                )

                # 기관/시스템 이름의 일부로 우연히 포함된 경우 방지
                # (매칭 바로 뒤 10자 이내에 기관명 접미사가 붙어있는지 확인)
                after_text = search_text[end:min(len(search_text), end + 10)]
                is_institution_name = any(w in after_text for w in INSTITUTION_SUFFIX_AFTER)

                # "소상공인" 법정 정의 조항(업종별 상시근로자 기준 차등) 방지 —
                # "5인 미만"(일반 기준)이 근처에 있고, 매칭 바로 뒤에도 또 다른
                # "N인/명 미만"이 붙어있는 두 기준 병기 패턴일 때만 걸러낸다.
                nearby_window = search_text[max(0, pos - 200):min(len(search_text), end + 100)]
                after_for_sme = search_text[end:min(len(search_text), end + 60)]
                is_sme_threshold_definition = bool(
                    SME_GENERAL_THRESHOLD_RE.search(nearby_window)
                    and SME_THRESHOLD_AFTER_RE.search(after_for_sme)
                )

                entry = (pos, end, level, name, name_to_code[name])

                # [2026-09-05 추가 5] 강화군 공고 실측 확인: "* 제조업·광업·건설업
                # 및 운수업은 10인 미만" 문구가 "2. 지급 제외대상" 목록 항목들
                # 사이(빈 줄 없이 이어짐)에 끼어 있어서, 몇 문장 앞의 무관한
                # "정책자금 지원제외 업종" 언급이 200자 문단창에 걸려
                # in_exclusion_section이 True가 됐다. is_sme_threshold_definition은
                # "소상공인 법정정의 조항"이라 원래 어떤 문맥이든 항상 무시해야
                # 하는데, 아래 elif 체인에서 제외 분기보다 순서가 밀려 있어 한 번도
                # 실행되지 못하고 "제외"로 잘못 분류됐다. 이 가드만 제외 분기보다
                # 먼저 검사해서 항상 우선 적용되게 한다.
                if is_sme_threshold_definition:
                    continue
                elif "제외" in context_before or in_exclusion_section:
                    # [2026-09-03 수정] 처음엔 이 예외를 다른 가드보다 앞에 둬서
                    # 전체를 뒤집었더니, "지원대상...포함"이라는 흔한 표현이
                    # 제3자/예시/기관명 가드까지 전부 우회시켜버리는 부작용이
                    # 실측 확인됨(전체 매칭 문서 수가 512→565로 급증). "포함"
                    # 재포함 문구는 "제외 판정을 뒤집는 것"에만 좁게 적용해야
                    # 하므로 제외 분기 안으로만 한정한다.
                    after_for_inclusion = search_text[end:min(len(search_text), end + 50)]
                    if INCLUSION_OVERRIDE_RE.search(after_for_inclusion):
                        all_hits.append(entry)
                    else:
                        all_excluded.append(entry)
                elif is_third_party or is_example or is_unrelated_policy or is_institution_name:
                    # 신청기업 본인 업종이 아니라 하도급업체/예시/무관정책/기관명인
                    # 경우 -> 무시
                    continue
                else:
                    all_hits.append(entry)

    if not all_hits:
        return None

    # 같은 위치를 더 세밀한(NAME_LEVEL_ORDER 앞쪽) 레벨이 이미 차지했으면
    # 그 자리를 덮는 상위레벨(더 넓은 카테고리) 매칭은 중복이므로 버린다.
    level_rank = {lv: i for i, lv in enumerate(NAME_LEVEL_ORDER)}
    all_hits.sort(key=lambda h: (h[0], level_rank[h[2]]))  # 위치순 -> 세밀한 레벨 우선

    kept = []
    covered_ranges = []
    for pos, end, level, name, code in all_hits:
        if any(s <= pos and end <= e for s, e in covered_ranges):
            continue
        kept.append((pos, end, level, name, code))
        covered_ranges.append((pos, end))

    if not kept:
        return None

    # 최종 매칭들을 위치순으로 정리, 중복 이름 제거
    kept.sort(key=lambda h: h[0])
    seen = set()
    final_names, final_codes, level_breakdown = [], [], {}
    for pos, end, level, name, code in kept:
        if name in seen:
            continue
        seen.add(name)
        final_names.append(name)
        final_codes.append(code)
        level_breakdown[name] = level

    # [버그 수정] all_hits와 달리 all_excluded는 레벨별 중복 위치(예: 상위
    # 레벨의 "제조업"이 하위 레벨 "1차 금속 제조업" 안에 겹쳐 매칭되는 경우)를
    # 걸러내지 않아서, 같은 자리가 여러 레벨에서 중복으로 잡혀 제외목록이
    # 실제보다 부풀려지는 문제가 있었다(강화군 공고 실측: 같은 코드가 수십
    # 번씩 중복). all_hits와 동일하게 위치 중복 제거 + 이름 중복 제거를 적용한다.
    all_excluded.sort(key=lambda h: (h[0], level_rank[h[2]]))
    kept_excluded = []
    excluded_covered_ranges = []
    for pos, end, level, name, code in all_excluded:
        if any(s <= pos and end <= e for s, e in excluded_covered_ranges):
            continue
        kept_excluded.append((pos, end, level, name, code))
        excluded_covered_ranges.append((pos, end))

    seen_excluded = set()
    excluded_info = []
    for pos, end, level, name, code in kept_excluded:
        if name in seen_excluded:
            continue
        seen_excluded.add(name)
        excluded_info.append({"명칭": name, "코드": code})

    # [2026-09-03 수정] 서로 다른 코드가 비정상적으로 많이 잡히면, 실제
    # 복수산업이 아니라 "업종 분류기호 참고표"가 통째로 첨부된 것일 가능성이
    # 높다(실측: "소상공인 경영환경개선" 류 공고에서 신청자가 체크할 업종표
    # 전체가 원문에 포함되어 60개 넘는 코드가 한꺼번에 잡히는 사례 확인됨).
    # 다만 개수만으로 판단하면 지역혁신클러스터·우주항공기업처럼 진짜 다중
    # 산업을 선언하는 통합공고(17개 등)까지 같이 걸러진다 — 그래서 순수
    # 개수가 아니라, 위 KNOWN_EXCLUSION_BOILERPLATE_NAMES 시그니처가 몇 개
    # 섞여 있는지로 재판단한다.
    if len(final_codes) > MAX_REASONABLE_MULTI_MATCH:
        boilerplate_hits = sum(1 for n in final_names if n in KNOWN_EXCLUSION_BOILERPLATE_NAMES)
        if boilerplate_hits >= BOILERPLATE_SIGNATURE_THRESHOLD:
            # 이전엔 이 경우 통째로 None(특정불가)으로 버렸는데, 그 안에 진짜
            # 다중산업 선언이 섞여 있을 가능성까지 같이 폐기하는 문제가
            # 있었음 — 완전히 버리는 대신 "확인필요(LOW 신뢰도)"로 낮춰서
            # 사람이 직접 보게 한다.
            return {
                "확정단계": "확인필요(다수매칭)",
                "확정코드": final_codes,
                "확정업종명": final_names,
                "제외업종": excluded_info,
                "근거": {
                    "매칭방식": "명시적 업종명 매칭",
                    "레벨별_매칭": level_breakdown,
                    "비고": f"{len(final_codes)}개 업종 매칭, 그중 보일러플레이트 시그니처 {boilerplate_hits}개 — 참고표/체크리스트일 가능성이 있어 확인 필요",
                },
                "ksic_confidence": "LOW",
            }
        # 보일러플레이트 시그니처가 거의 없으면(2개 미만) 개수가 많아도 진짜
        # 다중산업 선언으로 보고 아래 정상 로직(복수산업 확정)으로 넘어간다.

    # 전부 같은 레벨에서 나왔고 1개뿐이면 그 레벨로, 그 외(개수 2개 이상
    # 또는 서로 다른 레벨 섞임)에는 복수산업으로 처리
    unique_levels = set(level_breakdown.values())
    if len(final_codes) == 1:
        stage = list(unique_levels)[0]
    else:
        stage = "복수산업"

    return {
        "확정단계": stage,
        "확정코드": final_codes,
        "확정업종명": final_names,
        "제외업종": excluded_info,
        "근거": {"매칭방식": "명시적 업종명 매칭", "레벨별_매칭": level_breakdown},
    }
