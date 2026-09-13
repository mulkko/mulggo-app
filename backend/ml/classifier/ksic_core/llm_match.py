# ============================================================
# ksic_core/llm_match.py  (v5 — 진짜 세세분류부터 + 복수산업/해당없음 지원)
#
# 여기까지 오게 된 이유 (버전 히스토리):
# ------------------------------------------------------------
# v1: LLM 자유응답 + KSIC 마스터 역매핑(exact/fuzzy). 근데 "화학제품
#     제조업"(LLM 답) vs "화학물질 및 화학제품 제조업; 의약품 제외"
#     (KSIC 실제명) 유사도 0.516으로 근접매칭(0.85) 미달 -> 버려짐.
#     맞는 답인데 표기 차이로 놓치는 손실(recall 저하) 확인.
# v2~v4: 그래서 방향을 반대로 — LLM한테 이름을 짓게 안 하고 "번호로
#     고르게"(대분류→...→세세분류, 후보 목록 제시형)만 씀. 이름 지어낼
#     방법이 없어져 안전하긴 한데, 두 가지 한계가 있었음:
#       1) 세세분류가 아니라 대분류부터 시작 — 원래 bottom-up 원칙과 반대 방향
#       2) 한 경로만 선택 가능한 구조라 "복수산업"을 답할 수 없음
#          (실측: #10, #29는 GPT 정답이 12~22개짜리 목록인데 이 구조로는
#          원천적으로 못 맞힘)
#
# v5는 v1(자유응답, 진짜 세세분류부터 가능, 복수산업 가능)과 v2~v4
# (안전한 번호선택 캐스케이드)를 합침:
#   1차: LLM한테 업종을 자유롭게(여러 개면 배열로) 답하게 하고,
#        각 이름을 세세분류부터 대분류까지 순서로 역매핑 시도
#   2차 안전망: 1차가 전부 실패(LLM이 답은 했는데 KSIC에 없는 이름뿐)
#        하면, 기존에 검증된 번호선택 캐스케이드로 재시도
# ============================================================

import os
import csv
import json
import re
from difflib import get_close_matches, SequenceMatcher

from ksic_core.explicit_match import _load_ksic_index, NAME_LEVEL_ORDER

KSIC_CLEAN_CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "processed", "ksic_clean_v2.csv")

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "openai")  # 'openai' | 'gemini'
LLM_MODEL = os.environ.get(
    "LLM_MODEL",
    "gpt-4o-mini" if os.environ.get("LLM_PROVIDER", "openai") == "openai" else "gemini-1.5-flash",
)

DEBUG_LLM = os.environ.get("DEBUG_LLM", "0") == "1"


def _debug_print(label, value):
    if DEBUG_LLM:
        print(f"[DEBUG:{label}] {value}")


# 근접 매칭(fuzzy) 허용 최소 유사도. 오탈자/띄어쓰기 차이 정도만 허용하는 보수적 값.
FUZZY_CUTOFF = 0.85

# 대분류→세세분류 계층 (안전망 캐스케이드용)
LEVEL_CHAIN = ["대분류", "중분류", "소분류", "세분류", "세세분류"]
_LEVEL_COLUMNS = {
    "대분류": ("KSIC_대분류코드", "KSIC_대분류명", None),
    "중분류": ("KSIC_중분류코드", "KSIC_중분류명", "KSIC_대분류코드"),
    "소분류": ("KSIC_소분류코드", "KSIC_소분류명", "KSIC_중분류코드"),
    "세분류": ("KSIC_세분류코드", "KSIC_세분류명", "KSIC_소분류코드"),
    "세세분류": ("KSIC_코드", "KSIC_세세분류명", "KSIC_세분류코드"),
}

_daebunlyu_list = None       # [(code, name), ...] 21개, 최상위(부모 없음)
_children_by_level = None    # {레벨: {부모코드: [(code, name), ...]}}


# ============================================================
# 공통 판단 기준 (100건 실측 분석 결과) — 게이트/자유응답/캐스케이드
# 프롬프트 전부에서 재사용
# ============================================================
COMMON_JUDGMENT_RULES = """# 판단 기준 (엄격 적용, 2026-08-31 개정 — 실측 35건 오탐 분석 반영)

[최우선 규칙] "신청 자격", "지원 대상", "참가 자격" 조항에 업종이 직접
언급된 경우만 근거로 인정한다. 그 조항의 문구를 quote 필드에 원문
그대로 옮겨 적을 수 있어야 한다. 인용할 문구를 못 찾겠으면 근거 없음
으로 판단하라.

[근거로 절대 인정하지 않는 것 — 실측 35건 오탐에서 확인된 패턴]
- 사업명·정책 주제·트렌드 키워드("AI", "ICT", "그린뉴딜", "기후테크",
  "데이터 스페이스", "9대 대표산업", "지역특화산업", "○○산업 육성")는
  사업을 소개하는 문구일 뿐 신청기업의 업종 요건이 아니다. 이런 단어가
  나와도 "그래서 신청기업이 반드시 그 업종이어야 한다"는 별도 조항이
  없으면 근거로 쓰지 마라.
- "지원 품목/분야 예시 나열"(예: "지원품목: 식품, 공산품, 키트 제작 등",
  "음식점체·건설업체 등을 포함한 소상공인")은 실제 지원대상을 정확히
  열거한 게 아니라 예시일 수 있다. "등", 콤마로 여러 업종이 뒤섞여
  나열되어 있으면 참고용 예시로 보고 근거로 쓰지 마라.
- "위탁기업/수탁기업/원사업자/수급사업자"는 거래상 지위이지 업종이 아니다.
- "OO기업"(예: "항공기업", "드론 기업", "반도체 기업")처럼 사업명·타이틀에
  들어간 축약 표현은, "신청 자격" 조항에 구체적으로 반복되지 않는 한
  근거로 인정하지 마라. 사업 타이틀은 근거가 될 수 없다.
- 시상/포상/컨설팅/투자유치/인증취득/특허/보험료 지원 같은 사업은
  대부분 업종 무관(모든 업종의 중소기업이 신청 가능)이다. 이런 유형인데
  원문에 구체적 업종 제한 문구가 안 보이면 근거 없음으로 판단하라.
- 종합 무역사절단·박람회·전시회처럼 여러 업종이 섞인 행사는 업종 무관인
  경우가 많다. 특정 산업 전문 행사(예: "섬유 전시회", "애니메이션 마켓")
  라고 제목·목적에 명확히 나온 경우만 예외로 인정하라.
- [추가] 콤마나 "등"으로 여러 항목이 나열된 문구("숙박업, 음식점업 등",
  "바이오의약품, 바이오헬스, 바이오화학 등")는 예시 나열이다. 그중 하나만
  뽑아서 확정 짓지 마라 — 나열 자체가 "특정할 수 없다"는 신호다.
- [추가] "AI", "ICT", "특허", "IP", "혁신제품"처럼 사업 전반에 범용적으로
  쓰이는 단어는 그 자체로 특정 업종(정보통신업·소프트웨어업 등)의 근거가
  아니다. "AI 기업을 지원한다"가 아니라 "AI 기술로 무엇을 만들어 파는
  기업인지"가 구체적으로 명시돼야 한다.
- [추가] "비영리법인", "사회적기업", "협동조합"처럼 법인격·조직 형태를
  나타내는 말은 업종이 아니다. 이것만으로 특정 업종을 판단하지 마라.
- [추가] "산업 전·후방 연계 기업", "생태계 조성", "공급망" 같은 표현은
  범위가 넓은 정책 용어다. 구체적으로 어느 업종인지 짚어주는 말이 따로
  없으면 이 표현만으로 업종을 확정하지 마라.

[근거로 인정 가능한 것]
- "가공식품 포함", "공장등록기업"처럼 구체적 사업활동 요건이 신청자격
  조항에 명시된 경우.
- 특정 산업 전문 행사(위 예외 참고) 참가기업 모집인 경우.

여러 업종을 동시에 답할 땐(복수산업), 각각이 신청자격 조항에 직접
명시된 경우만 담아라. 사업 설명에서 여러 업종이 예시로 스쳐 지나간
것까지 다 담지 마라. 확신이 없으면 반드시 "근거 없음" 쪽으로 판단하라
— 이 판단 기준은 헛다리(위험한 오답)를 막는 게 최우선이다."""


GATE_PROMPT_TEMPLATE = """너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문을 읽고,
"이 공고가 지원대상으로 삼는 기업의 업종을 판단할 수 있는 근거가
원문 안에 있는지"만 먼저 판단하라. 아직 어떤 업종인지는 답하지 마라.

중요 — 아래 두 경우를 반드시 구분하라:
1. 원문에 업종을 짐작할 단서가 전혀 없다 (예: 지원금액·접수기간·신청서류
   안내만 있고 업종 얘기가 아예 없음, 또는 "중소기업"처럼 업종이 아니라
   기업 규모/형태만 언급됨) -> has_basis: false
2. 업종을 특정할 표현이 없어도, 문맥상 합리적으로 추론 가능한 단서가
   있다 -> has_basis: true

애매하면(둘 중 뭔지 확신이 안 서면) 반드시 false로 답하라 — 여기서
false가 맞는데 true라고 잘못 답하면 이후 단계에서 억지 추론으로
이어져 위험한 오답이 생긴다. 확신 없으면 무조건 false.

{rules}

반드시 아래 JSON 형식으로만 답하라:
{{"has_basis": true 또는 false, "quote": "근거로 삼은 원문 문구를 그대로 인용(없으면 빈 문자열)", "reasoning": "판단 근거 한 문장"}}

[공고 원문]
{text}""".replace("{rules}", COMMON_JUDGMENT_RULES)


FREEFORM_PROMPT_TEMPLATE = """너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문을 읽고,
이 공고가 지원대상으로 삼는 기업의 업종을 판단하라.

가능한 한 세밀하게(세세분류 수준으로) 판단하되, 세부 근거가 부족하면
더 넓은 상위 카테고리(중분류·대분류 수준)로 답해도 된다 — 억지로
세세분류까지 짜내지 마라.

반드시 지켜야 할 규칙:
1. 업종명은 반드시 한국표준산업분류(KSIC)의 공식 업종명 형식으로 답하라
   (예: "식료품 제조업", "소프트웨어 개발 및 공급업"). 네가 지어낸 이름이나
   코드 번호를 직접 답하지 마라 — 이름만 답하면 우리가 코드로 변환한다.
2. 원문 자체가 여러 업종을 동시에 지원대상으로 명시하면 배열에 여러 개를
   담아라. 그렇지 않으면 하나만 담아라.
3. 이 공고는 이미 "업종 판단 근거가 있다"고 확인된 상태다. 따라서
   industries 배열을 반드시 최소 1개는 채워라.

{rules}

반드시 아래 JSON 형식으로만 답하라. 다른 설명·문장을 붙이지 마라.
{{"industries": [{{"name": "업종명", "quote": "근거로 삼은 원문 문구 그대로 인용", "reasoning": "판단 근거"}}]}}

[공고 원문]
{text}""".replace("{rules}", COMMON_JUDGMENT_RULES)


SCOPE_JUDGMENT_PROMPT_TEMPLATE = """너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문을 읽고, 이 공고가
"신청기업의 업종을 실제로 제한하는지"를 판단하라. 아직 어떤 업종인지는
답하지 마라 — 범위만 먼저 판단한다.

[핵심 질문 — 반드시 이 구분을 지켜라]
네가 답해야 할 질문은 "이 사업이 무엇에 관한 것인가(SUBJECT)"가 아니라
"실제로 누가 신청할 수 있는지를 정하는 신청자격(ELIGIBILITY) 조항에서
업종이 제한되어 있는가"이다. SUBJECT에 특정 산업·기술 단어가 나와도
ELIGIBILITY 조항에 업종 제한 근거가 없으면 SPECIFIC이 아니다.

예시(일반 원칙일 뿐, 아래 원문과 무관):
- "AI 도입 지원사업" (사업명/주제) -> 이것만으로는 AI 관련 업종 제한이 아니다.
- "지원대상: AI 소프트웨어 개발업체" (신청자격 조항) -> 업종 제한 근거가 될 수 있다.

세 가지 중 하나로만 답하라:
- ALL_INDUSTRIES: 원문에 "업종 무관", "전 업종", "업종 제한 없음"처럼
  업종 제한이 없다는 근거가 명시적으로 있다.
- SPECIFIC: 신청자격/지원대상 조항에 특정 업종(하나 또는 여럿)을 요구하는
  근거가 있다.
- UNRESOLVED_REVIEW: 위 둘 다 아니다 — 업종 얘기가 아예 없거나(첨부파일
  안내만 있는 등), 근거가 있어도 너무 애매해서 사람 확인이 필요하다.

[SPECIFIC으로 답하려면 반드시 eligibility_quote와 evidence_role을 함께 채워라]
eligibility_quote: 신청자격/지원대상 조항에서 업종 제한 근거가 되는 문구를
원문 그대로 인용. SPECIFIC이면 절대 비워둘 수 없다.

evidence_role: 그 인용문이 실제로 어떤 역할인지 다음 중 하나로 답하라.
- SUPPORT_TARGET: 신청기업 자신의 업종을 직접 제한하는 신청자격 조항이다.
  SPECIFIC은 오직 이 역할일 때만 인정된다.
- SUBJECT_ONLY: 사업명, 사업목적, 정책 주제, 기술 분야, 제품명처럼 이
  사업이 "무엇에 관한" 것인지 설명할 뿐 신청기업의 업종 요건이 아니다.
- EXCLUSION: 제외 업종/지원 불가 대상을 나열한 것이지 지원대상이 아니다.
- REFERENCE_OR_EXAMPLE: 참고표, 예시, 각주, 예외적 제출요건처럼 본 조항이
  아닌 참고용 나열이다.
- THIRD_PARTY: 수행기관/공급기관/시설명/공간명 등 신청기업이 아닌 제3자를
  가리킨다.
- UNKNOWN: 위 어디에도 명확히 속하지 않는다.
SUBJECT_ONLY/EXCLUSION/REFERENCE_OR_EXAMPLE/THIRD_PARTY/UNKNOWN인 인용문
만으로는 SPECIFIC이라고 답하지 마라 — 그 경우 UNRESOLVED_REVIEW로 답하라.

industry_expression: eligibility_quote 안에서 업종을 가리키는 핵심 표현만
짧게(예: "여행업", "소프트웨어 개발업").

{risk_note}
{rules}

애매하면 반드시 UNRESOLVED_REVIEW로 답하라 — 여기서 억지로 ALL_INDUSTRIES나
SPECIFIC을 고르면 이후 단계에서 위험한 오답으로 이어진다. "특정 업종 근거를
못 찾았다"는 사실만으로 ALL_INDUSTRIES를 자동으로 고르지도 마라 — 근거가
없으면 UNRESOLVED_REVIEW다.

반드시 아래 JSON 형식으로만 답하라:
{{"scope": "ALL_INDUSTRIES 또는 SPECIFIC 또는 UNRESOLVED_REVIEW",
  "eligibility_quote": "SPECIFIC일 때만 필수, 원문 그대로 인용(없으면 빈 문자열)",
  "evidence_role": "SUPPORT_TARGET|SUBJECT_ONLY|EXCLUSION|REFERENCE_OR_EXAMPLE|THIRD_PARTY|UNKNOWN",
  "industry_expression": "업종 핵심 표현(없으면 빈 문자열)",
  "reasoning": "판단 근거 한 문장"}}

[공고 원문]
{text}""".replace("{rules}", COMMON_JUDGMENT_RULES)


SPECIFIC_SCOPE_TYPE_PROMPT_TEMPLATE = """너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문은 이미 "신청기업의
업종을 실제로 제한한다(SPECIFIC)"고 판단된 상태다. 이제 그 제한이 어떤
형태인지 더 구체적으로 분류하라.

다섯 가지 중 하나로만 답하라:
- SINGLE_INDUSTRY: 신청자격 조항이 하나의 업종만 구체적으로 요구한다.
- MULTI_INDUSTRY: 신청자격 조항이 여러 업종을 각각 구체적으로 명시한다
  (예: "제조업 또는 정보통신업 영위기업").
- OPEN_ENDED_MULTI: 업종을 나열하긴 했지만 "등", 콤마로 몇 개만 예시로
  들거나 통계청 분류를 통째로 가리키는 개방형 표현이라 그 예시만으로는
  전체 범위를 확정할 수 없다(예: "외식업, 이미용업, 세탁업 등
  개인서비스업종"). 이 경우 특정 업종 몇 개로 좁혀 답하면 실제보다 좁은
  오답이 된다.
- BROAD_SECTOR_AMBIGUOUS: "관련 분야"라는 것은 분명하지만(예: "해양수산
  관련 기업", "바이오헬스 분야 기업"), 그 분야가 여러 KSIC 세세분류에
  걸쳐 있어서 하나의 세부 코드로 안전하게 좁힐 수 없다. "관련 분야다"와
  "하나의 세부 KSIC로 확정 가능하다"는 다르다 — 후자가 아니면 이걸
  선택하라. 억지로 세세분류 하나를 고르지 마라.
- UNRESOLVED_REVIEW: 조건이 "A 또는 B"처럼 여러 대안으로 나뉘는데 그 중
  하나 이상이 업종 무관/모호한 조건(예: "중소기업 또는 업종 무관
  소상공인")이라 하나의 업종으로 확정할 수 없다.

{risk_note}
{rules}

애매하면 SINGLE_INDUSTRY/MULTI_INDUSTRY로 억지로 좁히지 말고
BROAD_SECTOR_AMBIGUOUS, OPEN_ENDED_MULTI 또는 UNRESOLVED_REVIEW로 답하라.

반드시 아래 JSON 형식으로만 답하라:
{{"scope_type": "SINGLE_INDUSTRY 또는 MULTI_INDUSTRY 또는 OPEN_ENDED_MULTI 또는 BROAD_SECTOR_AMBIGUOUS 또는 UNRESOLVED_REVIEW", "reasoning": "판단 근거 한 문장"}}

[공고 원문]
{text}""".replace("{rules}", COMMON_JUDGMENT_RULES)


def _load_hierarchy():
    """ksic_clean.csv에서 대분류 목록 + 레벨별 부모->자식 목록(안전망 캐스케이드용)을 만든다."""
    global _daebunlyu_list, _children_by_level

    if _daebunlyu_list is not None:
        return

    with open(KSIC_CLEAN_CSV_PATH, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    dae_seen = {}
    children_by_level = {lv: {} for lv in LEVEL_CHAIN[1:]}

    for row in rows:
        dcode = (row.get("KSIC_대분류코드") or "").strip()
        dname = (row.get("KSIC_대분류명") or "").strip()
        if dcode and dname:
            dae_seen[dcode] = dname

        for level in LEVEL_CHAIN[1:]:
            code_col, name_col, parent_col = _LEVEL_COLUMNS[level]
            code = (row.get(code_col) or "").strip()
            name = (row.get(name_col) or "").strip()
            parent = (row.get(parent_col) or "").strip()
            if code and name and parent:
                children_by_level[level].setdefault(parent, {})[code] = name

    _daebunlyu_list = sorted(dae_seen.items())
    _children_by_level = {
        lv: {p: sorted(m.items()) for p, m in pm.items()} for lv, pm in children_by_level.items()
    }


def _call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "openai":
        from openai import OpenAI
        from openai import BadRequestError

        client = OpenAI()  # 환경변수 OPENAI_API_KEY를 자동으로 읽음
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                temperature=0,  # 재현성 확보 시도 — 지원 안 하는 모델이면 아래서 재시도
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
        except BadRequestError as e:
            # [2026-08-31 추가] GPT-5/o1/o3 같은 추론형 모델은 temperature=0을
            # 거부하고 기본값(1)만 허용함("Unsupported value: temperature...").
            # 이 경우에만 temperature를 아예 안 넘기고 재시도.
            if "temperature" in str(e).lower():
                _debug_print("temperature_not_supported_retrying_without_it", str(e))
                resp = client.chat.completions.create(
                    model=LLM_MODEL,
                    response_format={"type": "json_object"},
                    messages=[{"role": "user", "content": prompt}],
                )
            else:
                raise
        return resp.choices[0].message.content

    elif LLM_PROVIDER == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        model = genai.GenerativeModel(LLM_MODEL)
        resp = model.generate_content(
            prompt,
            generation_config={"temperature": 0, "response_mime_type": "application/json"},
        )
        return resp.text

    else:
        raise ValueError(f"지원하지 않는 LLM_PROVIDER: {LLM_PROVIDER}")


# [2026-09-03 추가] 1,589건 전체 실측 결과, 특정불가/확인필요로 남은 919건 중
# 38~48%가 원문 3000자를 넘는 것으로 확인됨(중앙값 2,300~2,800자, 최대 4.8만자).
# "신청 자격" 조항이 문서 뒷부분(첨부 안내 뒤 등)에 있는 경우 이 컷오프에 잘려서
# has_basis가 거짓으로 판정되는 게 실제 recall 손실 원인 중 하나로 추정됨.
# 12000자는 같은 표본의 94.9%를 통째로 커버함(3000자는 58.3%만 커버) — gpt-4o-mini
# 컨텍스트 한도 대비 비용/속도 여유도 충분해 이 값으로 확장.
LLM_TEXT_BUDGET = 12000


def _check_has_basis(text: str) -> bool:
    """0차 관문. 후보/이름을 아무것도 안 보여준 상태에서 근거 존재여부만 먼저 확인.
    파싱 실패 등 애매하면 무조건 False(안전한 쪽)로 처리."""
    prompt = GATE_PROMPT_TEMPLATE.replace("{text}", text[:LLM_TEXT_BUDGET])
    try:
        raw = _call_llm(prompt)
        _debug_print("gate_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("gate_EXCEPTION", f"{type(e).__name__}: {e}")
        return False
    return bool(parsed.get("has_basis", False))


def _extract_industry_names(text: str):
    """[1차] LLM한테 업종을 자유롭게(세세분류 관점, 여러 개 가능) 답하게 함.
    반환: [{"name":..., "reasoning":...}, ...] (실패/빈 배열이면 [])"""
    prompt = FREEFORM_PROMPT_TEMPLATE.replace("{text}", text[:LLM_TEXT_BUDGET])
    try:
        raw = _call_llm(prompt)
        _debug_print("freeform_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("freeform_EXCEPTION", f"{type(e).__name__}: {e}")
        return []
    return parsed.get("industries", []) or []


def _remap_industry_name(name: str):
    """[1차 역매핑] 이름 하나를 KSIC 마스터와 대조.

    [2026-08-31 수정] fuzzy(근접) 매칭을 제거하고 exact(정확일치)만 허용.
    실측 확인: LLM이 가끔 name 필드에 짧은 업종명 대신 긴 문장을 그대로
    넣는 경우가 있었는데(형식 위반), 그런 문장을 fuzzy 매칭에 태우면
    전혀 무관한 업종으로 잘못 착지하는 사례가 실제로 발생함(예: "바이오
    플라스틱..." 문장이 "자동차 신품 부품 제조업"으로 잘못 매칭됨).
    exact만 허용하고 안 맞으면 _fallback_cascade(2차 안전망, 번호선택
    방식이라 애초에 엉뚱한 매칭이 불가능)로 넘기는 게 훨씬 안전함."""
    name = str(name).strip()
    if not name:
        return None

    index = _load_ksic_index()  # explicit_match.py가 쓰는 것과 동일한 캐시

    for level in NAME_LEVEL_ORDER:  # 세세분류 -> ... -> 대분류
        name_to_code = index[level]
        if name in name_to_code:
            return {"code": name_to_code[name], "name": name, "level": level, "match_type": "exact"}

    return None  # exact 실패 -> 안전망으로 위임 (fuzzy 시도 안 함)


# [2026-08-31 추가] "고른 번호"가 "자기가 댄 근거"와 실제로 맞는지 코드로
# 검증하는 안전장치. 실측 확인: #50에서 reasoning엔 "항공기업"이라고 써놓고
# 실제 선택은 "금융 및 보험업"으로 완전히 동떨어진 사례 발견 — 프롬프트
# 지시만으론 못 막고, 고른 이름이 근거 텍스트와 최소한의 관련성이 있는지
# 대조해야 함.
#
# [주의] 단순 부분문자열 대조는 너무 엄격함이 실측으로 확인됨 — "식료품"과
# "가공식품"처럼 뜻은 통하지만 글자가 하나도 안 겹치는 정상 케이스까지
# 차단해버림. 대신 슬라이딩 윈도우로 최고 유사도를 구하는 방식 사용.
# 실측: 정상케이스(식료품~가공식품) 0.50, 불일치케이스(금융보험~항공) 0.29
# -> 0.35를 경계선으로 사용.
_GENERIC_SUFFIXES = ["제조업", "서비스업", "판매업", "중개업", "공급업", "도매업", "소매업", "운송업", "가공업", "임대업"]
_CONSISTENCY_CUTOFF = 0.35


def _sanity_check_consistency(picked_name: str, grounding_text: str) -> bool:
    """picked_name의 핵심(접미사 제외)이 grounding_text(quote+reasoning) 안의
    어떤 구간과 최소한의 유사도가 있는지 슬라이딩 윈도우로 확인."""
    core = picked_name
    for suf in _GENERIC_SUFFIXES:
        core = core.replace(suf, "")
    core = core.strip("; ,()·")
    if len(core) < 2:
        return True  # 이름 자체가 너무 짧아 검증 불가 -> 과탐 방지 위해 통과

    grounding_text = grounding_text or ""
    if not grounding_text.strip():
        return False  # 근거 텍스트 자체가 없으면 검증 불가 -> 안전하게 차단

    window = len(core) + 2
    best = 0.0
    for i in range(max(1, len(grounding_text) - window + 1)):
        seg = grounding_text[i:i + window]
        best = max(best, SequenceMatcher(None, core, seg).ratio())
        if best >= _CONSISTENCY_CUTOFF:
            return True
    return best >= _CONSISTENCY_CUTOFF


# [2026-09-03 추가] 기존 _sanity_check_consistency는 "고른 업종명"이 LLM 자신이
# 댄 근거(quote+reasoning) 문장과 서로 관련 있는지만 봤음 — LLM이 quote 자체를
# 지어내도(원문에 없는 문장을 인용해도) 이 검사는 통과함(할루시네이션을 못 잡음).
# 이 함수는 그 한 겹 아래를 검증한다: quote가 실제로 원문에 존재하는지 직접 대조.
# 공백/개행 차이(추출 과정에서 흔함)만 허용하고, 그 외엔 부분일치를 요구한다.
def _quote_verified_in_text(quote: str, text: str) -> bool:
    quote = (quote or "").strip()
    if len(quote) < 4:
        return False  # 너무 짧은 인용은 검증 신뢰도가 없음 -> 안전하게 차단
    norm_quote = "".join(quote.split())
    norm_text = "".join((text or "").split())
    return norm_quote in norm_text


# G5: KSIC 11차 해설서의 코드별 정의/제외를 후보 설명에 붙여 LLM 판단을 돕는다.
_HAESEOL_CSV = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "ksic_haeseolseo_summary.csv"
)
_haeseol = None
_HAESEOL_NOISE = re.compile(r"제\s*조\s*업|대분류\s*[A-U]|중분류\s*\d+")


def _load_haeseol():
    """{code: (정의, 제외)}. 파일 없으면 빈 dict → 기존 프롬프트와 동일."""
    global _haeseol
    if _haeseol is not None:
        return _haeseol
    out = {}
    if os.path.exists(_HAESEOL_CSV):
        import csv as _csv
        with open(_HAESEOL_CSV, encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                code = (row.get("KSIC코드") or "").strip()
                dfn = _HAESEOL_NOISE.sub("", row.get("정의") or "").strip(" ;·")
                exc = _HAESEOL_NOISE.sub("", row.get("제외") or "").strip(" ;·/")
                if code:
                    out[code] = (dfn[:160], exc[:160])
    _haeseol = out
    return _haeseol


def _candidate_line(i, code, name, budget=160):
    """G5: '3. 업종명 — 정의 …[제외: …]'"""
    dfn, exc = _load_haeseol().get(str(code), ("", ""))
    dfn, exc = dfn[:budget], exc[:budget]
    extra = ""
    if dfn:
        extra += f" — {dfn}"
    if exc:
        extra += f" [제외: {exc}]"
    return f"{i+1}. {name}{extra}"


def _pick_from_candidates(text, candidates, level_label, parent_name=None):
    """[2차 안전망용] candidates 중 하나를 LLM이 번호로 고르게 하고,
    목록 안의 번호인지 검증한 뒤에만 반환. 실패/null이면 None."""
    if not candidates:
        return None

    _bud = 90 if len(candidates) > 20 else 160   # 후보 많으면 설명 축약(프롬프트 비대화 방지)
    lines = [_candidate_line(i, code, name, _bud) for i, (code, name) in enumerate(candidates)]
    candidate_block = "\n".join(lines)
    parent_note = f'(이미 "{parent_name}" 대분류로 판단됨)\n' if parent_name else ""

    prompt = f"""너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문을 읽고,
이 공고가 지원대상으로 삼는 기업의 업종이 {level_label} 중 몇 번에
가장 가까운지 판단하라.

{parent_note}
반드시 지켜야 할 규칙:
1. 아래 목록에 있는 번호만 답할 수 있다. 목록에 없는 답은 절대 하지 마라.
2. 원문에 근거가 부족하면 억지로 고르지 말고 selected_number를 null로 답하라.
3. 반드시 아래 JSON 형식으로만 답하라. 다른 설명·문장을 붙이지 마라.

{COMMON_JUDGMENT_RULES}

{{"selected_number": 번호 또는 null, "reasoning": "판단 근거 한 문장"}}

[{level_label} 목록]
{candidate_block}

[공고 원문]
{text[:LLM_TEXT_BUDGET]}"""

    try:
        raw = _call_llm(prompt)
        _debug_print("pick_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("pick_EXCEPTION", f"{type(e).__name__}: {e}")
        return None

    num = parsed.get("selected_number")
    if num is None:
        return None
    try:
        num = int(num)
    except (TypeError, ValueError):
        return None
    if not (1 <= num <= len(candidates)):  # 목록 밖 번호는 절대 통과 안 시킴
        return None

    code, name = candidates[num - 1]
    reasoning = parsed.get("reasoning", "")

    # [2026-08-31 추가] 일관성 검증 — 고른 이름의 핵심 단어가 근거 텍스트에
    # 없으면(reasoning이 다른 업종 얘기를 하고 있으면) 통과시키지 않음
    if not _sanity_check_consistency(name, reasoning):
        _debug_print("pick_CONSISTENCY_CHECK_FAILED", f"name={name!r} vs reasoning={reasoning!r}")
        return None

    return {"code": code, "name": name, "reasoning": reasoning}


def _fallback_cascade(text: str):
    """[2차 안전망] 1차(자유응답+역매핑)가 전부 실패했을 때만 호출.
    대분류->세세분류 순으로 번호선택, 각 레벨에서 확신 없으면 직전에서 멈춤."""
    _load_hierarchy()

    picks = []
    candidates = _daebunlyu_list
    parent_name = None

    for level in LEVEL_CHAIN:
        pick = _pick_from_candidates(text, candidates, level, parent_name)
        if pick is None:
            break
        picks.append((level, pick["code"], pick["name"], pick["reasoning"]))

        next_idx = LEVEL_CHAIN.index(level) + 1
        if next_idx >= len(LEVEL_CHAIN):
            break
        next_level = LEVEL_CHAIN[next_idx]
        candidates = _children_by_level[next_level].get(pick["code"], [])
        parent_name = pick["name"]
        if not candidates:
            break

    if not picks:
        return None

    final_level, final_code, final_name, final_reasoning = picks[-1]
    confidence = "LOW" if final_level == "대분류" else "MED"

    return {
        "확정단계": f"LLM보강-안전망({final_level})",
        "확정코드": [final_code],
        "확정업종명": [final_name],
        "제외업종": [],
        "근거": {
            "매칭방식": "LLM 후보선택(안전망 캐스케이드)",
            "llm_provider": LLM_PROVIDER,
            "llm_model": LLM_MODEL,
            "단계별_판단": {lv: r for lv, c, n, r in picks},
        },
        "ksic_confidence": confidence,
    }


# ============================================================
# candidate verifier (2026-09-12d 추가) — 자유생성 분류기가 아니라
# "Rule/ML이 이미 낸 후보를 검증"하는 별도 진입점.
#
# 왜 필요했나: match_ksic_by_llm()(위)은 원문만 보고 처음부터 자유롭게
# 업종을 판단한다. orchestrator의 LLM Verifier 단계는 이 자유응답을
# Rule 후보와 "완전 문자열 일치"로만 대조했는데, Rule 후보가 대분류
# 알파벳처럼 넓은 코드(예: "C")이고 LLM이 그보다 세밀한 코드(예: "285")로
# 답하면 계층적으로는 맞는 답인데도 문자열이 달라 전부 폐기되는 문제가
# 실측(T1 PBLN_126209)으로 확인됐다.
#
# 그렇다고 "계층 호환되면 자동 채택"으로 고치면, 이번엔 LLM이 아무 이름이나
# 던져도 Rule 후보와 같은 대분류이기만 하면 통과되어 버려 위험하다. 그래서
# 방향을 바꿔 LLM의 역할 자체를 "새 코드를 만드는 것"에서 "Rule이 이미
# 제시한 후보 각각을 SUPPORTED/UNSUPPORTED/UNCERTAIN으로 검증하는 것"으로
# 좁혔다 — 최종 코드셋은 항상 Rule 후보의 부분집합이고, 더 세밀하거나 새로운
# 코드는 "suggested_refinement"라는 별도 필드로만 나가며 자동 채택되지 않는다
# (llm_verifier.py가 이 원칙을 강제한다).
# ============================================================

CANDIDATE_VERIFY_PROMPT_TEMPLATE = """너는 한국표준산업분류(KSIC) 전문가다. 아래 공고 원문과, 이전 규칙 판정
단계에서 이미 제시된 "후보 업종 코드" 목록이 있다.

너의 역할은 새로운 업종을 자유롭게 찾아내는 것이 아니라, 이 후보들이
실제로 원문의 신청자격/지원대상 요건에 해당하는지 하나씩 검증하는 것이다
(candidate verifier). 후보 목록에 없는 코드를 최종 답으로 만들어내지 마라.

각 후보에 대해 다음 중 하나로 판정하라:
- SUPPORTED: 원문의 신청자격/지원대상 조항이 이 후보 업종을 직접 뒷받침한다.
- UNSUPPORTED: 원문에 이 후보 업종을 뒷받침하는 근거가 없다(과잉확장이었을 가능성).
- UNCERTAIN: 관련 언급은 있으나 확신을 갖고 판정하기엔 근거가 불충분하다.

[SUPPORTED로 답하려면 반드시 evidence_role도 함께 채워라]
그 인용문(quote)이 실제로 어떤 역할인지 다음 중 하나로 답하라 — SUPPORTED는
오직 evidence_role이 SUPPORT_TARGET일 때만 인정된다:
- SUPPORT_TARGET: 신청기업 자신의 업종을 직접 제한하는 신청자격/지원대상
  조항이다.
- SUBJECT_ONLY: 사업명, 사업목적, 정책 주제, 기술 분야처럼 사업이 "무엇에
  관한" 것인지 설명할 뿐 신청기업의 업종 요건이 아니다.
- EXCLUSION: 제외 업종/지원 불가 대상을 나열한 것이지 지원대상이 아니다.
- REFERENCE_OR_EXAMPLE: 참고표, 예시, 각주, 산업분류 참고표, 부록/별표의
  참고용 분류표처럼 본 신청자격 조항이 아닌 참고용 나열이다. 단 그 표가
  "지원대상 업종/신청 가능 업종/모집 업종"이라고 명시적으로 정의돼 있으면
  SUPPORT_TARGET으로 인정한다.
- PRIORITY_OR_PREFERENCE: "우선 모집분야", "우대 조건", "가점 대상"처럼
  특정 업종을 우선순위·가점으로만 언급할 뿐, 실제 신청자격 자체를 그
  업종으로 제한하지 않는다(신청자격 조항 자체는 업종 무관인 경우가 많다).
- THIRD_PARTY: 수행기관/공급기관 등 신청기업이 아닌 제3자를 가리킨다.
- UNKNOWN: 위 어디에도 명확히 속하지 않는다.
SUBJECT_ONLY/EXCLUSION/REFERENCE_OR_EXAMPLE/PRIORITY_OR_PREFERENCE/
THIRD_PARTY/UNKNOWN인 근거만으로는 SUPPORTED로 답하지 마라 — 그 경우
UNCERTAIN으로 답하라.

{rules}

추가로, 후보 목록에는 없지만 원문에서 더 구체적이거나 다른 업종이 명확히
발견되면 suggested_refinement에 참고용으로만 적어라. 이건 자동으로
채택되지 않고 사람이 검토할 제안일 뿐이다 — 확신 없으면 비워둬라.

반드시 아래 JSON 형식으로만 답하라. 다른 설명·문장을 붙이지 마라.
{{
  "verdicts": [
    {{"code": "후보코드(목록에 있는 것 그대로)", "verdict": "SUPPORTED 또는 UNSUPPORTED 또는 UNCERTAIN",
      "evidence_role": "SUPPORT_TARGET|SUBJECT_ONLY|EXCLUSION|REFERENCE_OR_EXAMPLE|PRIORITY_OR_PREFERENCE|THIRD_PARTY|UNKNOWN",
      "quote": "근거 원문 인용(없으면 빈 문자열)", "reasoning": "판단 근거 한 문장"}}
  ],
  "suggested_refinement": [
    {{"name": "업종명(공식 KSIC 명칭 형식)", "quote": "근거 원문 인용", "reasoning": "판단 근거"}}
  ]
}}

[후보 업종 목록]
{candidate_block}

[공고 원문]
{text}""".replace("{rules}", COMMON_JUDGMENT_RULES)


def verify_candidates_with_llm(text: str, candidates: list[dict]):
    """Rule이 이미 낸 후보(candidates)를 LLM이 하나씩 검증한다 — 자유생성 아님.

    Args:
        candidates: [{"code": str, "name": str}, ...] (Rule/ML 단계의 원본 후보)

    Returns:
        {
          "verdicts": {code: {"verdict": "SUPPORTED"|"UNSUPPORTED"|"UNCERTAIN",
                               "quote": str, "reasoning": str}, ...},
          "suggested_refinement": [{"code":..., "name":..., "quote":..., "reasoning":...}, ...],
        }
        또는 호출/파싱 실패 시 None.
    """
    if not candidates:
        return None

    candidate_block = "\n".join(f"{i+1}. {c['code']} — {c['name']}" for i, c in enumerate(candidates))
    prompt = (
        CANDIDATE_VERIFY_PROMPT_TEMPLATE
        .replace("{candidate_block}", candidate_block)
        .replace("{text}", text[:LLM_TEXT_BUDGET])
    )
    try:
        raw = _call_llm(prompt)
        _debug_print("candidate_verify_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("candidate_verify_EXCEPTION", f"{type(e).__name__}: {e}")
        return None

    valid_codes = {c["code"] for c in candidates}
    verdicts: dict = {}
    for v in parsed.get("verdicts", []) or []:
        code = str(v.get("code", "")).strip()
        if code not in valid_codes:
            continue  # 후보 목록 밖 code는 verdict로 인정하지 않는다(안전장치)
        verdict = str(v.get("verdict", "")).strip().upper()
        if verdict not in ("SUPPORTED", "UNSUPPORTED", "UNCERTAIN"):
            continue
        quote = v.get("quote", "")
        evidence_role = str(v.get("evidence_role", "") or "").strip().upper()
        # SUPPORTED인데 인용문이 실제 원문에 없으면 UNCERTAIN으로 강등(할루시네이션 방지,
        # 기존 _quote_verified_in_text 그대로 재사용).
        if verdict == "SUPPORTED" and not _quote_verified_in_text(quote, text):
            verdict = "UNCERTAIN"
        # [2026-09-13 V2.1 evidence gate] SUPPORTED인데 evidence_role이
        # SUPPORT_TARGET이 아니면(SUBJECT_ONLY/EXCLUSION/REFERENCE_OR_EXAMPLE/
        # PRIORITY_OR_PREFERENCE/THIRD_PARTY/UNKNOWN) UNCERTAIN으로 강등한다.
        # 실측(PBLN_126301): "우선 모집분야"(PRIORITY_OR_PREFERENCE) 근거만으로
        # SUPPORTED를 낸 사례를 재현·수정.
        if verdict == "SUPPORTED" and evidence_role != "SUPPORT_TARGET":
            verdict = "UNCERTAIN"
        verdicts[code] = {"verdict": verdict, "quote": quote, "evidence_role": evidence_role,
                           "reasoning": v.get("reasoning", "")}

    # LLM 응답에서 언급 안 된 후보는 누락 방지를 위해 안전하게 UNCERTAIN 처리.
    for c in candidates:
        verdicts.setdefault(c["code"], {"verdict": "UNCERTAIN", "quote": "", "evidence_role": "",
                                         "reasoning": "LLM 응답에 없음"})

    suggestions = []
    for s in parsed.get("suggested_refinement", []) or []:
        name = str(s.get("name", "")).strip()
        quote = s.get("quote", "")
        if not name or not _quote_verified_in_text(quote, text):
            continue  # 인용 검증 실패 시 제안도 버린다(할루시네이션 방지)
        remapped = _remap_industry_name(name)  # 기존 exact-매핑 함수 재사용, 수정 없음
        if not remapped:
            continue
        suggestions.append({
            "code": remapped["code"], "name": remapped["name"],
            "quote": quote, "reasoning": s.get("reasoning", ""),
        })

    return {"verdicts": verdicts, "suggested_refinement": suggestions}


def match_ksic_by_llm(text: str):
    """
    2단계 진입점. 1단계(explicit_match.match_ksic_by_name)가 실패했을 때만 호출.

    반환 형태는 세 가지 다 가능 (explicit_match.py의 단일/복수산업/특정불가와 동일):
      - None                          : 해당없음(특정불가)
      - 확정코드 1개                   : 단일 업종
      - 확정코드 2개 이상               : 복수산업
    """
    if not _check_has_basis(text):
        return None  # 해당없음

    # 1차: 세세분류부터 — 자유응답 + 역매핑 (복수산업 자연스럽게 지원됨)
    industries = _extract_industry_names(text)

    remapped = []
    for item in industries:
        name = item.get("name", "")
        grounding = f"{item.get('quote', '')} {item.get('reasoning', '')}"
        # [2026-08-31 추가] 1차도 동일한 일관성 검증 적용 — LLM이 답한 이름이
        # 자기가 댄 근거(quote+reasoning)와 실제로 관련 있는지 확인.
        if not _sanity_check_consistency(name, grounding):
            _debug_print("freeform_CONSISTENCY_CHECK_FAILED", f"name={name!r} vs grounding={grounding!r}")
            continue
        if not _quote_verified_in_text(item.get("quote", ""), text):
            _debug_print("freeform_QUOTE_NOT_FOUND_IN_TEXT", f"quote={item.get('quote', '')!r}")
            continue
        r = _remap_industry_name(name)
        if r:
            r["llm_reasoning"] = item.get("reasoning", "")
            r["llm_quote"] = item.get("quote", "")
            remapped.append(r)

    if remapped:
        codes = [r["code"] for r in remapped]
        names = [r["name"] for r in remapped]
        levels_used = {r["level"] for r in remapped}
        is_multi = len(remapped) > 1
        stage = "복수산업" if is_multi else next(iter(levels_used))
        all_exact = all(r["match_type"] == "exact" for r in remapped)

        return {
            "확정단계": f"LLM보강({stage})",
            "확정코드": codes,
            "확정업종명": names,
            "제외업종": [],
            "근거": {
                "매칭방식": "LLM 자유응답+역매핑",
                "llm_provider": LLM_PROVIDER,
                "llm_model": LLM_MODEL,
                "항목별_상세": remapped,
            },
            "ksic_confidence": "HIGH" if all_exact else "MED",
        }

    # 2차 안전망: 1차가 다 실패했으면(이름은 나왔지만 KSIC과 하나도 안 맞음)
    return _fallback_cascade(text)


# ============================================================
# Resolver v2: scope-first (2026-09-12g 추가) — 57건 실측 진단에서 확인된
# "자유응답은 반드시 하나를 답해야 한다"는 구조적 압력을 없애기 위해, 범위
# 판단(R1: ALL_INDUSTRIES/SPECIFIC/UNRESOLVED_REVIEW)과 세부유형 판단
# (R2: SINGLE/MULTI/OPEN_ENDED_MULTI/UNRESOLVED_REVIEW)을 코드 생성(R3)보다
# 먼저 분리했다. R3는 기존 _extract_industry_names/_remap_industry_name/
# _fallback_cascade를 한 글자도 바꾸지 않고 그대로 재사용한다.
# ============================================================

_RISK_SIGNAL_LABELS = {
    "open_ended_list_detected": '원문에 개방형 나열("...등") 패턴이 있다 — 예시로 든 업종만 뽑으면 과소확정(실제보다 좁게 확정) 위험.',
    "or_condition_with_open_scope_detected": '원문에 "또는/혹은" 조건 중 업종무관 대안이 섞여 있을 수 있다 — 하나만 골라 확정하면 위험.',
    "exclusion_mentioned": "원문에 제외/제한 업종 문구가 있다 — 제외 목록을 지원대상으로 착각하지 마라.",
    "reference_context_present": "원문에 참고표/예시/기준표 문맥이 있다 — 참고용 나열을 지원대상으로 착각하지 마라.",
    "non_target_role_present": "원문에 신청기업이 아닌 역할(시공사/운영기관 등) 단어가 있다 — 그 역할을 신청업종으로 착각하지 마라.",
    "broad_field_term_present": "원문에 범위가 넓은 정책 용어(바이오헬스/모빌리티 등)가 있다 — 이것만으로 세부 업종을 단정하지 마라.",
    "explicit_no_restriction_present": "원문에 업종 무관을 명시하는 문구가 있다.",
}


def _risk_signal_note(risk_signals: dict | None) -> str:
    """Rule이 미리 감지한 위험 신호를 프롬프트에 넣을 참고 문구로 바꾼다.
    신호는 참고용일 뿐이며, 최종 판단은 LLM이 원문을 직접 읽고 내린다."""
    if not risk_signals:
        return ""
    active = [label for key, label in _RISK_SIGNAL_LABELS.items() if risk_signals.get(key)]
    if not active:
        return ""
    bullet = "\n".join(f"- {label}" for label in active)
    return f"[Rule 엔진이 미리 감지한 위험 신호 — 참고만 하고 원문을 직접 확인해서 최종 판단하라]\n{bullet}\n"


def _judge_scope(text: str, risk_note: str = "") -> dict:
    """R1: ALL_INDUSTRIES/SPECIFIC/UNRESOLVED_REVIEW 판단 + evidence gate.

    [2026-09-13 Resolver Phase 2 추가] SPECIFIC은 LLM이 그렇게 답했다는
    사실만으로 인정하지 않는다. Phase 1 진단(resolver_false_positive_15_
    execution_trace.csv)에서 15건 중 9건(60%)이 "R1이 사업명/정책주제/기술
    분야/시설명/각주 같은 SUBJECT성 근거를 신청자격(ELIGIBILITY) 근거로
    착각"해서 발생한 것으로 확인됐다. 그래서 SPECIFIC은 아래 evidence gate를
    통과해야만 최종 SPECIFIC으로 인정한다:
      1) eligibility_quote가 비어있지 않다
      2) 그 quote가 실제 원문에 존재한다(_quote_verified_in_text 재사용,
         새 검증 로직 추가 안 함 — 기존 할루시네이션 방지 장치 그대로 재사용)
      3) evidence_role == SUPPORT_TARGET이다(SUBJECT_ONLY/EXCLUSION/
         REFERENCE_OR_EXAMPLE/THIRD_PARTY/UNKNOWN이면 게이트 불통과)
    게이트를 통과 못 하면 SPECIFIC이 아니라 UNRESOLVED_REVIEW로 내려간다
    (ALL_INDUSTRIES로 자동 승격하지 않는다 — "특정업종 근거가 없다"가 곧
    "업종 무관 근거가 있다"는 뜻은 아니라는 기존 원칙과 동일)."""
    prompt = (
        SCOPE_JUDGMENT_PROMPT_TEMPLATE
        .replace("{risk_note}", risk_note)
        .replace("{text}", text[:LLM_TEXT_BUDGET])
    )
    try:
        raw = _call_llm(prompt)
        _debug_print("scope_judgment_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("scope_judgment_EXCEPTION", f"{type(e).__name__}: {e}")
        return {"scope": "UNRESOLVED_REVIEW", "reasoning": f"판단 실패({type(e).__name__})",
                "eligibility_quote": "", "evidence_role": "", "industry_expression": ""}

    scope = str(parsed.get("scope", "")).strip().upper()
    if scope not in ("ALL_INDUSTRIES", "SPECIFIC", "UNRESOLVED_REVIEW"):
        scope = "UNRESOLVED_REVIEW"  # 형식 위반 응답은 안전한 쪽으로

    quote = str(parsed.get("eligibility_quote", "") or "")
    role = str(parsed.get("evidence_role", "") or "").strip().upper()
    industry_expr = str(parsed.get("industry_expression", "") or "")
    reasoning = parsed.get("reasoning", "")

    if scope == "SPECIFIC":
        gate_ok = bool(quote.strip()) and _quote_verified_in_text(quote, text) and role == "SUPPORT_TARGET"
        if not gate_ok:
            _debug_print("scope_judgment_EVIDENCE_GATE_REJECTED",
                         f"quote={quote!r} role={role!r}")
            scope = "UNRESOLVED_REVIEW"
            reasoning = f"[evidence_gate_rejected: quote={quote!r}, role={role!r}] {reasoning}"

    return {"scope": scope, "reasoning": reasoning, "eligibility_quote": quote,
            "evidence_role": role, "industry_expression": industry_expr}


def _judge_specific_scope_type(text: str, risk_note: str = "") -> dict:
    """R2: R1==SPECIFIC일 때만 호출. SINGLE/MULTI/OPEN_ENDED_MULTI/
    BROAD_SECTOR_AMBIGUOUS/UNRESOLVED_REVIEW."""
    prompt = (
        SPECIFIC_SCOPE_TYPE_PROMPT_TEMPLATE
        .replace("{risk_note}", risk_note)
        .replace("{text}", text[:LLM_TEXT_BUDGET])
    )
    try:
        raw = _call_llm(prompt)
        _debug_print("scope_type_raw_response", raw)
        parsed = json.loads(raw)
    except Exception as e:
        _debug_print("scope_type_EXCEPTION", f"{type(e).__name__}: {e}")
        return {"scope_type": "UNRESOLVED_REVIEW", "reasoning": f"판단 실패({type(e).__name__})"}
    scope_type = str(parsed.get("scope_type", "")).strip().upper()
    if scope_type not in ("SINGLE_INDUSTRY", "MULTI_INDUSTRY", "OPEN_ENDED_MULTI",
                           "BROAD_SECTOR_AMBIGUOUS", "UNRESOLVED_REVIEW"):
        scope_type = "UNRESOLVED_REVIEW"
    return {"scope_type": scope_type, "reasoning": parsed.get("reasoning", "")}


def resolve_scope_first(text: str, *, risk_signals: dict | None = None) -> dict:
    """LLM Fallback Resolver v2 진입점. R1(범위)→R2(세부유형)→R3(코드생성) 순서로,
    앞 단계가 SPECIFIC+SINGLE/MULTI를 확정할 때만 다음 단계로 넘어간다.

    반환: {"scope": "ALL_INDUSTRIES"|"SPECIFIC"|"UNRESOLVED_REVIEW",
           "scope_type": "SINGLE_INDUSTRY"|"MULTI_INDUSTRY"|"OPEN_ENDED_MULTI"|None,
           "확정코드": [...], "확정업종명": [...], "근거": {...},
           "r1_reasoning": str, "r2_reasoning": str}
    (확정코드/확정업종명/근거 키는 기존 match_ksic_by_llm과 같은 이름을 재사용해
    llm_resolver.py가 두 형태를 비슷한 방식으로 다룰 수 있게 했다.)
    """
    risk_note = _risk_signal_note(risk_signals)
    r1 = _judge_scope(text, risk_note)
    # r1의 evidence-gate 근거(Phase 2 감사용)는 최종 scope와 무관하게 항상 기록한다.
    r1_evidence = {"r1_eligibility_quote": r1.get("eligibility_quote", ""),
                   "r1_evidence_role": r1.get("evidence_role", ""),
                   "r1_industry_expression": r1.get("industry_expression", "")}
    empty = {"확정코드": [], "확정업종명": [],
             "근거": {"매칭방식": "scope-first", "llm_provider": LLM_PROVIDER, "llm_model": LLM_MODEL,
                     **r1_evidence}}

    if r1["scope"] in ("ALL_INDUSTRIES", "UNRESOLVED_REVIEW"):
        return {**empty, "scope": r1["scope"], "scope_type": None,
                "r1_reasoning": r1["reasoning"], "r2_reasoning": ""}

    # r1["scope"] == "SPECIFIC"
    r2 = _judge_specific_scope_type(text, risk_note)

    # [2026-09-13 Resolver Phase 2 추가] deterministic risk guard — 코드
    # 레벨 invariant다, 프롬프트 지시가 아니다. Phase 1에서 open_ended_list_
    # detected=True가 프롬프트에 정확히 주입됐는데도 LLM이 SINGLE_INDUSTRY로
    # 확정한 실측 사례(PBLN_125620)가 확인됐다 — "신호를 참고하라"는 지시만
    # 으로는 못 막혔으므로, 이 신호가 켜져 있으면 SINGLE_INDUSTRY 자체를
    # 코드로 차단한다. 다른 risk flag는 의미가 다르므로 이 차단을 적용하지
    # 않는다(모든 flag를 일괄 UNRESOLVED로 만들지 말라는 지시에 따름).
    if risk_signals and risk_signals.get("open_ended_list_detected") and r2["scope_type"] == "SINGLE_INDUSTRY":
        _debug_print("scope_first_DETERMINISTIC_GUARD_BLOCKED_SINGLE",
                     "open_ended_list_detected=True but LLM said SINGLE_INDUSTRY")
        return {**empty, "scope": "UNRESOLVED_REVIEW", "scope_type": "OPEN_ENDED_MULTI",
                "r1_reasoning": r1["reasoning"],
                "r2_reasoning": f"[deterministic_guard: open_ended_list_detected로 SINGLE_INDUSTRY 차단] {r2['reasoning']}"}

    if r2["scope_type"] in ("OPEN_ENDED_MULTI", "BROAD_SECTOR_AMBIGUOUS", "UNRESOLVED_REVIEW"):
        # Rule의 OPEN_ENDED_CATCHALL_PATTERN과 동일한 보수 원칙: 개방형 나열/
        # 애매한 다부문/광역 섹터는 코드를 만들지 않고 사람 검토로 넘긴다.
        # ("관련 분야다" != "하나의 세부 KSIC로 확정 가능하다")
        return {**empty, "scope": "UNRESOLVED_REVIEW", "scope_type": r2["scope_type"],
                "r1_reasoning": r1["reasoning"], "r2_reasoning": r2["reasoning"]}

    # r2["scope_type"] in (SINGLE_INDUSTRY, MULTI_INDUSTRY) -> R3: 기존 로직 그대로 재사용
    industries = _extract_industry_names(text)
    remapped = []
    for item in industries:
        name = item.get("name", "")
        grounding = f"{item.get('quote', '')} {item.get('reasoning', '')}"
        if not _sanity_check_consistency(name, grounding):
            _debug_print("scope_first_r3_CONSISTENCY_CHECK_FAILED", f"name={name!r} vs grounding={grounding!r}")
            continue
        if not _quote_verified_in_text(item.get("quote", ""), text):
            _debug_print("scope_first_r3_QUOTE_NOT_FOUND_IN_TEXT", f"quote={item.get('quote', '')!r}")
            continue
        r = _remap_industry_name(name)
        if r:
            r["llm_reasoning"] = item.get("reasoning", "")
            r["llm_quote"] = item.get("quote", "")
            remapped.append(r)

    # [2026-09-13 Resolver Phase 2 수정] deterministic guard를 R2 라벨이 아니라
    # R3의 실제 최종 코드 개수에 적용한다. 실측 확인(PBLN_125620 재현): R2가
    # MULTI_INDUSTRY라고 답했더라도 R3(_extract_industry_names+remap)가 여러
    # 이름 중 하나만 성공적으로 매핑하면, llm_resolver.py가 len(codes)==1을
    # 보고 최종 라벨을 SINGLE_INDUSTRY로 재계산한다 — 그래서 R2 시점의
    # scope_type만 검사하는 가드는 이 경로를 놓친다. "닫힌 개수로 확정됐다"는
    # 사실 자체를 R3 출력에서 다시 확인해야 한다.
    open_ended = bool(risk_signals and risk_signals.get("open_ended_list_detected"))

    if not remapped:
        cascade = _fallback_cascade(text)
        if not cascade:
            return {**empty, "scope": "UNRESOLVED_REVIEW", "scope_type": r2["scope_type"],
                    "r1_reasoning": r1["reasoning"], "r2_reasoning": r2["reasoning"]}
        if open_ended and len(cascade["확정코드"]) == 1:
            _debug_print("scope_first_DETERMINISTIC_GUARD_BLOCKED_R3_CASCADE_SINGLE",
                         "open_ended_list_detected=True but cascade narrowed to 1 code")
            return {**empty, "scope": "UNRESOLVED_REVIEW", "scope_type": "OPEN_ENDED_MULTI",
                    "r1_reasoning": r1["reasoning"],
                    "r2_reasoning": f"[deterministic_guard: R3 결과 1개로 닫힘 차단] {r2['reasoning']}"}
        return {"scope": "SPECIFIC", "scope_type": r2["scope_type"],
                "확정코드": cascade["확정코드"], "확정업종명": cascade["확정업종명"],
                "근거": {**cascade["근거"], **r1_evidence},
                "r1_reasoning": r1["reasoning"], "r2_reasoning": r2["reasoning"]}

    if open_ended and len(remapped) == 1:
        _debug_print("scope_first_DETERMINISTIC_GUARD_BLOCKED_R3_SINGLE",
                     "open_ended_list_detected=True but R3 narrowed to 1 code")
        return {**empty, "scope": "UNRESOLVED_REVIEW", "scope_type": "OPEN_ENDED_MULTI",
                "r1_reasoning": r1["reasoning"],
                "r2_reasoning": f"[deterministic_guard: R3 결과 1개로 닫힘 차단] {r2['reasoning']}"}

    return {"scope": "SPECIFIC", "scope_type": r2["scope_type"],
            "확정코드": [r["code"] for r in remapped], "확정업종명": [r["name"] for r in remapped],
            "근거": {"매칭방식": "scope-first R3(자유응답+역매핑)", "llm_provider": LLM_PROVIDER,
                     "llm_model": LLM_MODEL, "항목별_상세": remapped, **r1_evidence},
            "r1_reasoning": r1["reasoning"], "r2_reasoning": r2["reasoning"]}
