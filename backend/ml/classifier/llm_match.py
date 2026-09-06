# ============================================================
# ml/classifier/llm_match.py  (v5 — 진짜 세세분류부터 + 복수산업/해당없음 지원)
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
from difflib import get_close_matches, SequenceMatcher

from backend.ml.classifier.explicit_match import _load_ksic_index, NAME_LEVEL_ORDER

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
KSIC_CLEAN_CSV_PATH = os.path.join(PROJECT_ROOT, "data", "ksic_clean_v2.csv")

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


def _pick_from_candidates(text, candidates, level_label, parent_name=None):
    """[2차 안전망용] candidates 중 하나를 LLM이 번호로 고르게 하고,
    목록 안의 번호인지 검증한 뒤에만 반환. 실패/null이면 None."""
    if not candidates:
        return None

    lines = [f"{i+1}. {name}" for i, (code, name) in enumerate(candidates)]
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
