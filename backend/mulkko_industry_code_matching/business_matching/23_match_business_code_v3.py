from __future__ import annotations

import argparse
import json
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent))
import embedders  # 임베딩 백엔드 추상화 (OpenAI / 로컬 bge-m3) — 개정 계획서 §6.4

# =============================================================================
# 23_match_business_code_v3.py  (단순화 유지 + 검색 품질 개선판)
#
# 개선 포인트 (2026-09)
# 1) canonical_activity를 "업종분류표 용어"로 강하게 유도
#    - 판매 / 온라인 / 앱 / 제조 같은 오염 단어를 canonical에서 배제
# 2) business_role을 고정 목록(enum)으로 뽑아 검색/재판정에 활용
# 3) Embedding 검색을 "여러 표현으로 검색 후 병합" (multi-query) 로 바꿔 재현율↑
# 4) Keyword 검색은 세세분류명 일치에 가중치 (linked_ksic_names 여전히 제외)
# 5) Reranker가 "역할이 명백히 안 맞는 후보 먼저 탈락 → 세세분류 직접일치" 순서로 판정
# 6) 출력에 후보 업종명을 함께 표시 (retrieval 품질을 눈으로 확인 가능)
# 7) --json-out / --no-llm : Gold Set 구축 및 retrieval 평가용
# 8) 결과에 후보 2·3위(alternatives) + 예측점수 노출
#    - 벤치마킹(BEACON/ONS): 코드 1개로 강제하지 않고 사용자가 다른 후보를 고를 수 있게
#    - representative_business.ai_predicted_code / ai_predicted_score / alternatives
#    - user_selected_code / changed_by_user 는 이후 UI·DB 계층에서 채운다
#
# cosine similarity는 정답 확률이 아니라 후보검색용 상대 유사도이며,
# 최종 판정은 후보 pool 안에서 LLM이 한다.
# ai_predicted_score 도 "검색 유사도(참고값)"이지 정답 확률이 아니다. 신뢰도는 confidence(high/mid/low).
# =============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# 다중 검색문서 DB (25 -> 26). 롤백하려면 아래 2줄을 옛 값으로:
#   DB_DIR = ... / "chroma_db" / "business_codes_2025"
#   COLLECTION = "business_codes_2025"
DB_DIR = PROJECT_ROOT / "chroma_db" / "business_code_docs_2025"
REF_CSV = PROJECT_ROOT / "data" / "processed" / "business_code_chroma_reference_v1.csv"
COLLECTION = "business_code_docs_2025"

DEFAULT_LLM_MODEL = "gpt-5-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"

# gpt-5 계열 추론 강도. 구조화·재판정은 제약된 JSON 스키마 작업이라 low 로도 충분하고
# medium/high 대비 응답이 크게 빠르다(평가 대량 실행 시 특히). .env 의 LLM_REASONING 으로 조정.
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "90"))


def _chat_json(client: OpenAI, model: str, system: str, user: str, schema: dict) -> dict:
    """제약 스키마 JSON 응답 1회. reasoning_effort 미지원 모델이면 자동 폴백."""
    # minimal 은 속도 이득이 거의 없고 재판정 정확도가 소폭 낮았음(2026-09-10 측정) → 기본 low.
    effort = (os.getenv("LLM_REASONING") or "low").strip() or "low"
    kw = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": schema},
    )
    try:
        resp = client.chat.completions.create(reasoning_effort=effort, **kw)
    except Exception as e:  # noqa: BLE001
        if "reasoning" not in str(e).lower():
            raise
        resp = client.chat.completions.create(**kw)
    return json.loads(resp.choices[0].message.content)

# 쿼리 1개당 벡터 후보 수, 병합 후 유지 수, 키워드 후보 수, 재판정 후보 수
# 이제 한 업종코드가 문서 여러 개를 가지므로 문서 기준 검색 수를 넉넉히 잡는다.
VECTOR_PER_QUERY = 40
VECTOR_KEEP = 25          # 기본(공식정보) 채널에서 유지할 코드 수
EXAMPLE_KEEP = 12         # 예시 채널에서 '추가'로 얹을 코드 수 (기본 채널을 밀어내지 않음)
KEYWORD_TOP_N = 15
# 재판정 후보 창. gold_set_v1(42건)에서 정답이 pool 16~18위였던 케이스가 있어 15 -> 20.
# (2026-09-09 검토: gold_v2 재판정 실패 73건 중 42건이 정답 pool 15위+. 28로 올리는 실험은
#  OpenAI 크레딧 소진으로 미검증 — 크레딧 복구 시 RERANK_TOP_N=28 로 gold_v1/v2 재평가 권장.)
RERANK_TOP_N = 20

# 검색 문서 채널 분리 (2026-09-09)
#  - BASE   : 공식 정보 (업종명/계층/KSIC/정의·설명)  → 후보의 뼈대. 반드시 유지.
#  - EXAMPLE: 해설서 <예시> 활동 + <제외> 경계 활동    → 후보 '보완'만. 기본 채널을 못 민다.
BASE_DOC_TYPES = ["name", "hier", "ksic", "desc", "def"]
EXAMPLE_DOC_TYPES = ["example", "xref"]

HAESEOL_JSON = PROJECT_ROOT / "data" / "processed" / "ksic_haeseol_v1.json"
KSIC_CLEAN_CSV = PROJECT_ROOT / "data" / "processed" / "ksic_clean.csv"

# 실제 PSST 폼(6단계) 중 업종 매칭에 쓰는 입력 4개:
#   Q1 사업 아이템(seed) / Q3 문제·기회 / Q4 해결 방식 / Q5 매장 운영 여부(이진)
#   (Q6 지역은 업종 판정에 미사용, 통과만)
LENGTH_RULES = {
    "seed": (5, 400),                    # Q1 사업 아이템 — 짧은 한 줄~한 문단 모두 허용
    "problem_or_opportunity": (5, 500),  # Q3 문제/기회
    "solution_approach": (5, 500),       # Q4 해결 방식
}

# business_role 고정 목록.
# 사업자가 "실제로 무엇을 해서 돈을 버는가"의 성격을 한 단어로 고른다.
BUSINESS_ROLES = [
    "재배·사육·어업",
    "제조·가공",
    "건설·시공",
    "도매",
    "소매",
    "음식·주점",
    "운수·물류",
    "정보서비스·SW개발",
    "콘텐츠·미디어",
    "교육",
    "금융·보험",
    "부동산·임대",
    "전문·과학·기술서비스",
    "시설관리·사업지원",
    "수리·개인서비스",
    "보건·복지",
    "예술·스포츠·여가",
    "중개·플랫폼·정보제공",
]

# business_role -> 명백히 상충하는 대분류(section) 조각.
# 후보의 biz_large_names 에 이 조각이 들어 있으면 "역할 상충"으로 강하게 후순위화한다.
# (제거가 아니라 강한 감점. 애매한 후보는 건드리지 않는다.)
ROLE_SECTION_CONFLICT: dict[str, list[str]] = {
    "재배·사육·어업": ["제조업", "도매 및 소매"],
    "제조·가공": ["도매 및 소매"],
    "건설·시공": ["제조업", "도매 및 소매"],
    "도매": ["제조업", "농업, 임업 및 어업"],
    "소매": ["제조업", "농업, 임업 및 어업"],
    "음식·주점": ["제조업", "도매 및 소매", "농업, 임업 및 어업"],
    "운수·물류": ["제조업", "도매 및 소매"],
    "정보서비스·SW개발": ["제조업", "도매 및 소매", "건설업"],
    "콘텐츠·미디어": ["제조업", "도매 및 소매"],
    "교육": ["제조업", "도매 및 소매"],
    "금융·보험": ["제조업", "도매 및 소매"],
    "부동산·임대": ["제조업", "도매 및 소매"],
    "전문·과학·기술서비스": ["제조업", "도매 및 소매"],
    "시설관리·사업지원": ["제조업"],
    "수리·개인서비스": ["제조업", "도매 및 소매"],
    "보건·복지": ["제조업", "도매 및 소매"],
    "예술·스포츠·여가": ["제조업", "도매 및 소매"],
    "중개·플랫폼·정보제공": ["제조업"],
}

# business_role -> 우선(부합) 대분류 조각. 후보가 여기에 맞으면 앞으로 당긴다.
ROLE_SECTION_PREFER: dict[str, list[str]] = {
    "재배·사육·어업": ["농업, 임업 및 어업"],
    "제조·가공": ["제조업"],
    "건설·시공": ["건설업"],
    "도매": ["도매 및 소매"],
    "소매": ["도매 및 소매"],
    "음식·주점": ["숙박 및 음식점"],
    "운수·물류": ["운수 및 창고"],
    "정보서비스·SW개발": ["정보통신"],
    "콘텐츠·미디어": ["정보통신", "예술, 스포츠"],
    "교육": ["교육 서비스"],
    "금융·보험": ["금융 및 보험"],
    "부동산·임대": ["부동산"],
    "전문·과학·기술서비스": ["전문, 과학 및 기술"],
    "시설관리·사업지원": ["사업시설 관리"],
    "보건·복지": ["보건업 및 사회복지"],
    "예술·스포츠·여가": ["예술, 스포츠"],
}

# role_fit 코드: 0 = 부합(앞으로), 1 = 중립, 2 = 상충(뒤로)
def role_fit(role: str, large_names: str, business_name: str = "") -> int:
    ln = clean(large_names)
    role = clean(role)
    for frag in ROLE_SECTION_PREFER.get(role, []):
        if frag in ln:
            return 0
    if role == "중개·플랫폼·정보제공" and ("중개" in business_name or "대리" in business_name):
        return 0
    for frag in ROLE_SECTION_CONFLICT.get(role, []):
        if frag in ln:
            return 2
    return 1


# role_fit -> 검색 순위 가감(위치). 상충은 '완전 배제'가 아니라 뒤로 미룬다.
# (구조화 LLM이 역할을 오판하는 경우가 있어, 상충 후보도 재판정 창에는 남겨 LLM이 되돌릴 수 있게 한다.)
_ROLE_RANK_DELTA = {0: -6, 1: 0, 2: 12}


# =============================================================================
# Q5 (매장 운영 여부) — 개정 계획서 §5.3. 실제 폼은 이진.
#   is_offline_store=True  : 고객이 직접 방문하는 오프라인 매장·공간
#   is_offline_store=False : 온라인·서비스 중심 (약한 신호 → 순위 조정 안 함)
#   is_offline_store=None  : 미입력
#
# 튜닝 파라미터 없음. "방문형 점포가 성립할 수 없는 대분류"를 기존 role_fit 의
# [상충](=2)으로 취급하고, 이미 있는 _ROLE_RANK_DELTA[2] 로 뒤로 민다. (완전 배제 아님)
# 근거: 손님이 걸어 들어오는 매장을 운영한다는데 그 사업의 '대표' 업종이
#       공장·농장·건설현장·운수업일 수는 없다 — 임계값이 아니라 논리적 배제.
# =============================================================================
# reference CSV의 대분류명은 "건 설 업" 처럼 공백이 섞여 있어 공백 제거 후 매칭한다.
def _nospace(s: str) -> str:
    return clean(s).replace(" ", "")


_OFFLINE_IMPOSSIBLE_SECTIONS = ["제조업", "농업,임업및어업", "건설업", "운수및창고", "광업"]


def store_conflict(is_offline_store: bool | None, large_names: str) -> bool:
    if is_offline_store is not True:
        return False
    ln = _nospace(large_names)
    return any(s in ln for s in _OFFLINE_IMPOSSIBLE_SECTIONS)


# =============================================================================
# 결과 상태 — 개정 계획서 §8.1. (추천 가능 / 사용자 확인 필요 / 정보 추가 필요)
# 튜닝 파라미터 없음 — 전부 이미 계산된 신호의 규칙 조합:
#   정보 추가 필요 : 후보 pool 이 비었거나, 구조화 LLM이 '무엇을 파는지'를 못 뽑음
#                    (NIOSH 대화형 코딩: 입력에 분류할 내용이 없으면 follow-up)
#   사용자 확인 필요: (a) 상위 후보 3개가 역할 경계(제조/도소매/SW) 2개 이상에 걸침, 또는
#                    (b) compute_confidence 가 'low' (이 규칙은 팀이 gold_v2 240건으로 이미 보정)
#   추천 가능      : 그 외
#   ⑦에서 골든셋으로 '이 규칙들이 얼마나 잘 맞는지'를 측정 (규칙 자체는 파라미터 없음)
# =============================================================================
RESULT_STATES = ("추천_가능", "사용자_확인_필요", "정보_추가_필요")

# 게이트 = 앙상블 (40_ensemble_gate.py, 사람검수 골든셋 gold_set_v3 90건):
#   "원문검색 1위 == 재판정 선택 AND 역할경계 아님"  →  커버 36% / 정확도 97%  ← 채택(A안)
#   (참고: + high 조건까지 걸면 26%/100%(B안), 검색 top3까지 넓히면 56%/80%(C안))
#   문헌 목표 ~55%/≥90% 중 정확도는 크게 상회, 커버는 낮음 — 신뢰성 우선.
#   커버 넓히려면 _AUTO_REQUIRE_HIGH=True 로(B) 또는 decide_result_state 의 ensemble_ok 를 agree3 로(C).
_AUTO_REQUIRE_HIGH = False

_ROLE_BOUNDARY_GROUPS = {   # 공백 제거 후 매칭 (_nospace)
    "제조": ["제조업"],
    "도소매": ["도매및소매"],
    "중개·SW·정보": ["정보통신"],
}

_INFO_QUESTION = (
    "해결 방식(Q4)을 조금 더 구체적으로 알려주세요. "
    "무엇을 직접 만들거나 제공하고, 고객에게 무엇을 팔거나 어떤 이용료를 받나요?"
)
_ROLE_QUESTION = (
    "주로 어떤 방식인가요? "
    "(직접 만든 걸 판다 / 떼다가 판다 / 연결해주고 수수료 / 구독료·이용료)"
)


def _section_group(large_names: str) -> str | None:
    ln = _nospace(large_names)
    for g, frags in _ROLE_BOUNDARY_GROUPS.items():
        if any(f in ln for f in frags):
            return g
    return None

# (2026-09-10) Soft Hierarchy Reranking 실험 코드 제거 — 개정 계획서에 없는 개념이고
#   런타임 경로에서 USE_HIERARCHY_RERANK=False 로 항상 비활성이었음.
#   원본은 archive/ 및 23_..._v3_baseline_20260909.py 에 보존.


ACTIVITY_SCHEMA = {
    "name": "activity_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "classifiable": {
                "type": "string", "enum": ["yes", "no"],
                "description": "이 설명만으로 국세청 업종(6자리)을 특정할 수 있으면 yes, "
                               "무슨 일로 돈 버는지 너무 막연하면 no",
            },
            "activities": {
                "type": "array",
                "minItems": 1,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "properties": {
                        "activity_name": {"type": "string"},
                        "canonical_activity": {"type": "string"},
                        "business_role": {"type": "string", "enum": BUSINESS_ROLES},
                        "priority": {"type": "string", "enum": ["primary", "secondary"]},
                        "product_service": {"type": "string"},
                        "evidence": {"type": "string"},
                        "search_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 2,
                            "maxItems": 6,
                        },
                    },
                    "required": [
                        "activity_name", "canonical_activity", "business_role",
                        "priority", "product_service", "evidence", "search_keywords",
                    ],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["classifiable", "activities"],
        "additionalProperties": False,
    },
}

RERANK_SCHEMA = {
    "name": "candidate_rerank",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "selected_business_code": {"type": "string"},
            "role_alignment": {"type": "string"},
            "reason": {"type": "string"},
            "confidence": {"type": "string", "enum": ["high", "mid", "low"]},
        },
        "required": ["selected_business_code", "role_alignment", "reason", "confidence"],
        "additionalProperties": False,
    },
}

ACTIVITY_SYSTEM = f"""
너는 대한민국 사업자의 실제 수익활동을 '업종분류표 검색용'으로 구조화한다.
업종코드/KSIC 코드는 절대 직접 출력하지 않는다.

[분해 규칙]
- 실제로 돈을 버는 독립 수익활동만 1~3개로 분리한다. primary는 정확히 하나.
- 한 활동이 애매하다는 이유로 활동을 쪼개지 않는다. 진짜 별개의 매출원일 때만 분리한다.
- 생산/재배/제조/가공/도매/소매/음식점/시공/개발/교육/임대/중개를 명확히 구분한다.
- 사업자가 직접 만들거나(로스팅·양조·봉제·조립 등) 재배·사육하면, 그 물건을 도매·소매·
  온라인으로 팔더라도 역할은 '제조·가공' 또는 '재배·사육·어업'이다. 도매/소매/온라인은
  판매 채널일 뿐이며 canonical도 제조업·가공업·재배업으로 잡는다.
  물건을 남에게서 떼다가 파는 경우에만 도매/소매다.
- AI·IoT·빅데이터·앱·웹·플랫폼·온라인·포장·배달은 그 자체를 파는 게 아니면 '수단'이다.
  수단은 activity/canonical에 넣지 말고 필요하면 search_keywords에만 최소로 넣는다.
- 고객이 속한 업종을 사업자의 업종으로 착각하지 않는다.
  (예: 식당에 솔루션 파는 회사는 음식점이 아니다)
- 입력에 없는 활동은 추측하지 않는다.

[business_role] : 아래 목록에서만 고른다. primary 활동의 역할을 반드시 하나로 확정한다.
{", ".join(BUSINESS_ROLES)}

[역할 확정 규칙] : 아래 순서로 판단한다.
- 원료·소재를 사서 형태·성질을 바꿔 새 제품을 만들거나(로스팅·양조·봉제·염색·조립·성형)
  재배·사육·어획하면 → '제조·가공' 또는 '재배·사육·어업'.
  (그 물건을 도매·소매·온라인으로 팔아도 역할은 제조/재배다. 판매는 채널일 뿐.)
- 완제품을 남에게서 떼어다가 소비자에게 팔면 → '소매'. 사업자에게 대량으로 팔면 → '도매'.
- 물건을 직접 안 갖고 매수자·매도자를 연결해 수수료만 받으면 → '중개·플랫폼·정보제공'.
- 매장에서 직접 조리·제조한 음식을 손님에게 바로 제공하면 → '음식·주점' (식품 제조업 아님).
- 앱·플랫폼·AI·IoT·온라인은 '그 자체'가 판매 상품(구독 SW 등)이 아니면 역할로 치지 않는다.
  거래 중개가 실제 수익원이면 역할은 '중개·플랫폼·정보제공'이지 '정보서비스·SW개발'이 아니다.
- 고객이 속한 업종을 사업자의 역할로 착각하지 않는다.

[제조로 착각하기 쉬운 도매·소매·서비스] : 아래는 '제조·가공'이 아니다.
- 도매·소매상이 파는 물건을 판매 전에 하는 손질·선별·등급분류·소분·재포장·냉장보관.
  원물의 형태·성질을 안 바꾸면 여전히 '도매' 또는 '소매'다. (예: 활어·선어를 대량 매입해
  손질·선별 후 거래처에 도매 마진 붙여 납품 → '도매', canonical은 '수산물 도매업')
- 안경원이 검안 후 완제품 프레임과 렌즈를 골라 고객 얼굴에 맞게 렌즈를 깎아 끼우고 조정해 파는 것
  → '소매' (안경 소매업). 렌즈·프레임을 공장에서 직접 만드는 게 아니면 제조가 아니다.
- 완성 가구·기계를 사와서 설치·조립만 해 주는 것 → 제조가 아니라 설치/도소매.

[canonical_activity] : 가장 중요.
- 통계청 한국표준산업분류 / 국세청 업종분류표에 실제로 나올 법한 짧은 명사형 표현.
- 반드시 '~업 / ~ 제조업 / ~ 가공업 / ~ 도매업 / ~ 소매업 / ~ 전문점 / ~ 개발 및 공급업 /
  ~ 교육 서비스업' 같은 분류형 어미로 끝낸다.
- '판매', '온라인', '앱', '스마트', '혁신', '플랫폼', 브랜드명, 고객명, 지역명을 넣지 않는다.
- 직접 만들면 '제조업/가공업', 떼다 팔면 '도매업/소매업', 매장 조리 판매면 '전문점/음식점업'.

[예시]
직접 로스팅한 원두를 포장해 온라인 판매 / 볶은 원두를 카페와 개인에게 도매로 납품
  business_role: 제조·가공
  canonical_activity: 커피 가공업
  (직접 볶으므로 '도매로 납품'해도 도매업이 아니라 가공업)
매장에서 커피 음료를 만들어 손님에게 판매
  business_role: 음식·주점
  canonical_activity: 커피 전문점
수제 비누를 만들어 자사몰에서 판매
  business_role: 제조·가공
  canonical_activity: 비누 및 세정제 제조업
다른 브랜드 신발을 사입해 인터넷 쇼핑몰에서 판매
  business_role: 소매
  canonical_activity: 전자상거래 소매업
식당에 농산물을 대량 납품
  business_role: 도매
  canonical_activity: 채소·과실 도매업
기업용 재고관리 SaaS를 직접 개발해 구독료로 제공
  business_role: 정보서비스·SW개발
  canonical_activity: 응용 소프트웨어 개발 및 공급업
프리랜서와 의뢰인을 앱으로 연결하고 수수료를 받음
  business_role: 중개·플랫폼·정보제공
  canonical_activity: 그 외 기타 정보 서비스업

[search_keywords] : 핵심 제품/서비스 및 경제활동 명사 2~6개. 수단어(앱/AI/온라인)는 넣지 않는다.
""".strip()

RERANK_SYSTEM = """
너는 6자리 업종코드 후보 재판정기다. 반드시 제공된 후보 목록 안에서 딱 하나만 고른다.
후보 목록에 없는 코드는 절대 만들어내지 않는다.

[판정 순서] — 반드시 이 순서. 1번(역할)이 최우선.
1) 사업자 역할(business_role) 일치 여부.
   - 후보의 '역할 적합성'이 [상충]이면 원칙적으로 탈락. (제품명이 비슷해도 탈락)
     · 역할이 '소매/도매'인데 후보가 '제조업' → 탈락
     · 역할이 '제조·가공'인데 후보가 단순 '도매/소매' → 탈락
     · 역할이 '음식·주점'인데 후보가 '식품 제조업' → 탈락 (커피 전문점 > 커피 가공업)
     · 역할이 '중개'인데 후보가 직접 도매/소매하는 업종 → 탈락
   - [상충] 후보만 남은 경우에 한해, 그 중 가장 덜 어긋나는 것을 고른다.
2) 실제 제품/서비스가 후보의 세세분류명·세부설명과 직접 일치하는가.
3) 후보의 '포함 예시'에 사업 활동이 들어맞는가.
4) 후보의 '제외 규칙'을 위반하지 않는가.
   (제외 규칙 = "이 활동은 이 후보가 아니라 다른 코드로 가야 한다"는 해설서 경계.
    사업 활동이 후보의 제외 규칙에 걸리면 그 후보를 고르지 않는다.)
5) 연계 KSIC 문구에 단어가 겹친다는 이유만으로 고르지 않는다.
6) 그래도 애매하면 상위 계층(대/중/소분류)이 사업 성격과 맞는 쪽.

[헷갈리기 쉬운 구분]
- 매장에서 직접 굽거나 조리해 파는 것(빵·케이크·커피·분식 등)은 제조업·도매업이 아니라
  음식점업(제과점업/전문점/간이 음식점업 등)이다.
- 직접 만든(로스팅·양조·봉제) 물건을 도매·소매로 팔면 역할은 제조·가공이다. → 제조 관련 업종.
- 완제품을 떼어다 파는 것은 도매업/소매업. 물건 없이 연결만 하면 중개업.
- 소비자에게 인터넷 쇼핑몰로 파는 소매는 품목 전문 소매업보다 '전자상거래 소매업'을 우선 고려한다.
- 도매·소매상의 판매 전 손질·선별·소분·재포장은 제조·가공이 아니다.
  (활어·선어 대량 매입 후 손질·선별해 도매 마진 붙여 납품 → 수산물 '도매업', 가공업 아님)
- 안경원(검안 후 완제품 프레임·렌즈를 골라 깎아 끼워 판매)은 '안경 소매업'이지 안경 제조업이 아니다.

[confidence]
- high: 역할도 맞고 세세분류명이 거의 그대로 일치
- mid: 역할은 맞으나 세세분류가 '기타/그 외'이거나 부분 일치
- low: 역할이 맞는 후보 자체가 약하거나 후보군이 빈약
""".strip()


def clean(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and math.isnan(v):
        return ""
    return str(v).strip()


def normalize(text: str) -> str:
    text = clean(text).lower()
    text = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


STOPWORDS = {
    "사업", "서비스", "제품", "제공", "관련", "기타", "및", "등",
    "위한", "통해", "활용", "고객", "대상", "방식", "판매", "운영",
    "온라인", "오프라인", "앱", "웹", "플랫폼", "모바일", "ai", "iot",
}


# 사용자가 흔히 쓰는 말 -> 업종분류표 용어. keyword 검색 토큰을 이걸로 넓힌다.
# (임베딩 검색이 놓치는 표현 차이를 키워드 쪽에서 보완)
SYNONYMS = {
    "꽃": ["화초", "화훼"],
    "꽃집": ["화초", "화훼"],
    "꽃다발": ["화초", "화훼"],
    "플로리스트": ["화초", "화훼"],
    "생선": ["수산물", "수산", "선어"],
    "회": ["수산물", "선어"],
    "활어": ["수산물", "선어"],
    "횟감": ["수산물", "선어"],
    "쇼핑몰": ["전자상거래", "통신 판매"],
    "인터넷쇼핑몰": ["전자상거래", "통신 판매"],
    "자사몰": ["전자상거래", "통신 판매"],
    "온라인판매": ["전자상거래", "통신 판매"],
    "정육점": ["육류 소매"],
    "빵집": ["제과점"],
    "베이커리": ["제과점"],
}


def tokenize(text: str) -> set[str]:
    toks = re.findall(r"[가-힣A-Za-z0-9]+", normalize(text))
    return {t for t in toks if len(t) >= 2 and t not in STOPWORDS}


def expand_synonyms(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for tok in tokens:
        for syn in SYNONYMS.get(tok, []):
            out.update(tokenize(syn))
    return out


@lru_cache(maxsize=1)
def _openai_client() -> OpenAI:
    return OpenAI(api_key=os.environ["OPENAI_API_KEY"], timeout=LLM_TIMEOUT, max_retries=2)


def load_env() -> tuple[str, str]:
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(env_path if env_path.exists() else None)

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(f"OPENAI_API_KEY가 없습니다: {env_path}")

    return (
        os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL).strip(),
        os.getenv("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL).strip(),
    )


def validate_inputs(
    seed: str,
    problem_or_opportunity: str,
    solution_approach: str,
    is_offline_store: bool | None = None,
) -> None:
    for name, value in [
        ("seed", seed),
        ("problem_or_opportunity", problem_or_opportunity),
        ("solution_approach", solution_approach),
    ]:
        lo, hi = LENGTH_RULES[name]
        n = len(value.strip())
        if n < lo or n > hi:
            raise ValueError(f"{name}: {n}자입니다. 허용 범위 {lo}~{hi}자")
    if is_offline_store is not None and not isinstance(is_offline_store, bool):
        raise ValueError("is_offline_store 는 True/False 또는 None 이어야 합니다.")


def _store_line(is_offline_store: bool | None) -> str:
    if is_offline_store is True:
        return "고객이 직접 방문하는 오프라인 매장·공간을 운영한다"
    if is_offline_store is False:
        return "온라인·서비스 중심 (고객 방문형 고정 매장 없음)"
    return "(미입력)"


def extract_activities(
    client: OpenAI,
    llm_model: str,
    seed: str,
    problem_or_opportunity: str,
    solution_approach: str,
    is_offline_store: bool | None = None,
) -> list[dict[str, Any]]:
    prompt = f"""
[Q1 사업 아이템]
{seed}

[Q3 문제/기회]
{problem_or_opportunity}

[Q4 해결 방식]
{solution_approach}

[Q5 매장 운영]
{_store_line(is_offline_store)}

위 정보만 사용해서 실제 수익활동을 1~3개로 구조화하라. 지역 정보는 사용하지 않는다.
business_role(역할)을 확정할 때 Q4(해결 방식)와 Q5(매장 운영)를 우선 근거로 삼는다:
- 오프라인 매장을 운영하면 방문형 소매·음식·개인서비스일 가능성이 높다.
- 직접 만들어 팔면 '제조·가공', 떼다가 팔면 '도매'/'소매',
  연결해주고 수수료면 '중개·플랫폼·정보제공', 구독 SW 자체가 상품이면 '정보서비스·SW개발'.

classifiable: Q4에 "무엇을 만들거나 팔거나 어떤 이용료를 받는지"가 안 나와서 업종을 특정할 수
없으면 "no". 관심사·비전·팀 소개만 있고 실제 경제활동이 없어도 "no". 특정 가능하면 "yes".
""".strip()

    parsed = _chat_json(client, llm_model, ACTIVITY_SYSTEM, prompt, ACTIVITY_SCHEMA)
    activities = parsed["activities"]
    classifiable = clean(parsed.get("classifiable")).lower() != "no"
    for a in activities:
        a["classifiable"] = classifiable   # 전 활동에 동일 플래그 부착 (primary 에서 읽음)

    primaries = [i for i, a in enumerate(activities) if a["priority"] == "primary"]
    if not primaries:
        activities[0]["priority"] = "primary"
    elif len(primaries) > 1:
        first = primaries[0]
        for i, a in enumerate(activities):
            a["priority"] = "primary" if i == first else "secondary"

    return activities


def build_queries(activity: dict[str, Any]) -> list[str]:
    """
    한 활동을 여러 표현으로 검색한다 (multi-query).
    표현마다 임베딩 공간에서 잡히는 후보가 조금씩 달라서
    병합하면 정답이 후보군에 들어올 확률이 올라간다.

    지역/고객/기술/문제상황 문장은 넣지 않는다.
    """
    canonical = clean(activity["canonical_activity"])
    role = clean(activity["business_role"])
    product = clean(activity["product_service"])
    keywords = [clean(k) for k in activity["search_keywords"] if clean(k)]
    kw = ", ".join(keywords)

    queries = [
        # 1) 분류표 용어 단독 (가장 깔끔)
        canonical,
        # 2) 분류표 용어 + 역할 + 제품 + 키워드 (맥락 보강)
        f"{canonical}\n{role}\n{product}\n{kw}",
        # 3) 제품/서비스 + 키워드 중심 (canonical이 틀렸을 때 보완)
        f"{product}\n{kw}",
    ]
    # 중복/빈 쿼리 제거
    seen: set[str] = set()
    out: list[str] = []
    for q in queries:
        q = q.strip()
        if q and q not in seen:
            seen.add(q)
            out.append(q)
    return out


@lru_cache(maxsize=1)   # 백엔드에서 호출마다 CSV 재로드 안 하도록
def load_reference() -> pd.DataFrame:
    df = pd.read_csv(REF_CSV, dtype={"business_code": str}, encoding="utf-8-sig")
    for col in df.columns:
        if col != "source_row_count":
            df[col] = df[col].map(clean)
    return df


_EXCLUSION_NOTES: dict[str, list[str]] | None = None


def load_exclusion_notes() -> dict[str, list[str]]:
    """
    해설서 <제외> -> {업종코드(출발): ["<활동> → 다른 업종" ...]}.
    재판정 프롬프트에서 "이 후보로 가면 안 되는 활동"을 후보별로 보여준다.
    (예: 안경 제조업 후보에 "안경 소매 → 안경 및 렌즈 소매업")
    """
    global _EXCLUSION_NOTES
    if _EXCLUSION_NOTES is not None:
        return _EXCLUSION_NOTES

    notes: dict[str, list[str]] = {}
    try:
        entries = json.loads(HAESEOL_JSON.read_text(encoding="utf-8"))
        k2name: dict[str, str] = {}
        if KSIC_CLEAN_CSV.exists():
            kc = pd.read_csv(KSIC_CLEAN_CSV, dtype=str, encoding="utf-8-sig").fillna("")
            for _, r in kc.iterrows():
                k2name.setdefault(clean(r.get("KSIC_코드", "")), clean(r.get("국세청_세세분류명", "")))
        for e in entries:
            srcs = [clean(c) for c in (e.get("business_codes_clean") or e.get("business_codes") or [])]
            for x in e.get("excludes", []):
                act = clean(x.get("activity"))
                if not act or len(act) > 60 or "대분류" in act or act.endswith("다."):
                    continue
                dests = [k2name.get(clean(c), "") for c in x.get("codes", [])]
                dest = next((d for d in dests if d), "다른 업종")
                line = f"{act} → {dest}"
                for s in srcs:
                    if re.fullmatch(r"\d{6}", s):
                        notes.setdefault(s, [])
                        if line not in notes[s]:
                            notes[s].append(line)
    except Exception:  # noqa: BLE001
        notes = {}
    _EXCLUSION_NOTES = notes
    return notes


@lru_cache(maxsize=1)
def load_lookup() -> dict[str, dict[str, str]]:
    """load_reference() + reference_lookup() 을 캐시. 백엔드용."""
    return reference_lookup(load_reference())


def reference_lookup(df: pd.DataFrame) -> dict[str, dict[str, str]]:
    out = {}
    for _, r in df.iterrows():
        out[r["business_code"]] = {
            "business_code": r["business_code"],
            "business_name": r["biz_detail_names"],
            "biz_large_names": r["biz_large_names"],
            "biz_middle_names": r["biz_middle_names"],
            "biz_small_names": r["biz_small_names"],
            "biz_sub_names": r["biz_sub_names"],
            "main_ksic_names": r["main_ksic_names"],
            "linked_ksic_names": r["linked_ksic_names"],
            "detail_descriptions": r["detail_descriptions"],
        }
    return out


@lru_cache(maxsize=4)   # 컬렉션 핸들 재사용 (백엔드)
def open_chroma(embedding_model: str):
    # 모델마다 별도 컬렉션 (차원·의미공간이 다르므로). embedders 가 경로/이름을 안다.
    try:
        db_path, coll_name = embedders.chroma_target(embedding_model)
    except KeyError:
        db_path, coll_name = str(DB_DIR), COLLECTION   # 미등록 모델은 기존 기본값
    chroma = chromadb.PersistentClient(path=db_path)
    col = chroma.get_collection(coll_name)

    db_model = clean((col.metadata or {}).get("embedding_model"))
    if db_model and db_model != embedding_model:
        raise RuntimeError(
            f"Embedding 모델 불일치: DB={db_model}, 검색={embedding_model}"
        )
    return col


def _search_channel(
    embs: list[list[float]],
    collection,
    doc_types: list[str],
) -> dict[str, dict[str, Any]]:
    """한 채널(doc_type 집합) 안에서만 검색해 코드별 최고 순위로 접는다."""
    merged: dict[str, dict[str, Any]] = {}
    for qi, emb in enumerate(embs):
        result = collection.query(
            query_embeddings=[emb],
            n_results=VECTOR_PER_QUERY,
            where={"doc_type": {"$in": doc_types}},
            include=["metadatas", "distances"],
        )
        for rank, (m, d) in enumerate(
            zip(result["metadatas"][0], result["distances"][0]), start=1
        ):
            code = clean(m.get("business_code"))
            cos = round(1.0 - float(d), 6)
            cur = merged.get(code)
            if cur is None or rank < cur["vector_rank"]:
                merged[code] = {
                    "business_code": code,
                    "vector_rank": rank,
                    "cosine_similarity": cos,
                    "hit_query": qi + 1,
                    "hit_doc_type": clean(m.get("doc_type")),
                }
            merged[code]["cosine_similarity"] = max(merged[code]["cosine_similarity"], cos)
    return merged


def raw_text_top1(collection, embedding_model: str, text: str) -> str:
    """원문(Q1+Q3+Q4) 임베딩 검색의 1위 업종코드. 앙상블 게이트용 독립 신호. LLM 안 씀."""
    emb = embedders.embed([text], embedding_model)[0]
    res = collection.query(
        query_embeddings=[emb], n_results=8,
        where={"doc_type": {"$in": BASE_DOC_TYPES}}, include=["metadatas"],
    )
    for m in res["metadatas"][0]:
        c = clean(m.get("business_code"))
        if c:
            return c
    return ""


def vector_search_multi(
    client: OpenAI,
    collection,
    embedding_model: str,
    queries: list[str],
) -> list[dict[str, Any]]:
    """
    검색을 2개 채널로 분리한다 (2026-09-09).
      BASE    : 공식 정보(name/hier/ksic/desc/def)  → 후보의 뼈대. 상위 VECTOR_KEEP개 반드시 유지.
      EXAMPLE : 해설서 <예시>/<제외>(example/xref)  → 보완. 상위 EXAMPLE_KEEP개를 '추가'만.
    예시 채널이 공식 채널 후보를 밀어내지 못하게 해서, 제조업 예시가 검색을 오염시키던 문제를 막는다.
    반환 각 행: business_code, vector_rank(정렬용 통합 순위), cosine_similarity,
                from_base / from_example, hit_doc_type
    """
    embs = embedders.embed(queries, embedding_model)   # OpenAI 또는 로컬 bge-m3
    return vector_search_from_embeddings(collection, embs)


def vector_search_from_embeddings(
    collection,
    embs: list[list[float]],
) -> list[dict[str, Any]]:
    """vector_search_multi 의 임베딩 이후 부분. 실험 스크립트가 캐시된 임베딩으로 호출한다.
    (30/31 이 OpenAI 임베딩 비용 없이 검색을 재현하기 위한 진입점 — 로직은 원본과 동일)"""
    base = _search_channel(embs, collection, BASE_DOC_TYPES)
    example = _search_channel(embs, collection, EXAMPLE_DOC_TYPES)

    base_rows = sorted(base.values(), key=lambda x: x["vector_rank"])[:VECTOR_KEEP]
    kept_codes = {r["business_code"] for r in base_rows}

    out: list[dict[str, Any]] = []
    for r in base_rows:
        ex = example.get(r["business_code"])
        out.append({
            **r,
            "from_base": True,
            "from_example": ex is not None,
            "cosine_similarity": max(r["cosine_similarity"],
                                     ex["cosine_similarity"] if ex else r["cosine_similarity"]),
        })

    # 예시 채널에만 있는 코드를 뒤에 '추가'
    example_only = sorted(
        (r for c, r in example.items() if c not in kept_codes),
        key=lambda x: x["vector_rank"],
    )[:EXAMPLE_KEEP]
    for i, r in enumerate(example_only, start=1):
        out.append({
            **r,
            "vector_rank": VECTOR_KEEP + i,   # 항상 base 뒤 순위
            "from_base": False,
            "from_example": True,
        })

    for rank, r in enumerate(out, start=1):
        r["vector_rank"] = rank
    return out


def keyword_score(activity: dict[str, Any], row: pd.Series) -> float:
    query_tokens = expand_synonyms(tokenize(
        " ".join([
            activity["canonical_activity"],
            activity["product_service"],
            activity["activity_name"],
            " ".join(activity["search_keywords"]),
        ])
    ))
    if not query_tokens:
        return 0.0

    # 세세분류명은 직접 일치 가치가 크므로 2배 가중.
    # linked_ksic_names는 의도적으로 제외 (여러 KSIC가 섞여 오탐 유발).
    detail = normalize(row["biz_detail_names"])
    context = normalize(" ".join([
        row["biz_sub_names"],
        row["biz_small_names"],
        row["biz_middle_names"],
        row["main_ksic_names"],
        row["detail_descriptions"],
    ]))

    score = 0.0
    for token in query_tokens:
        if token in detail:
            score += 2.0
        elif token in context:
            score += 1.0
    return score / (2.0 * len(query_tokens))


def keyword_search(
    ref_df: pd.DataFrame,
    activity: dict[str, Any],
    top_n: int = KEYWORD_TOP_N,
) -> list[dict[str, Any]]:
    rows = []
    for _, r in ref_df.iterrows():
        score = keyword_score(activity, r)
        if score > 0:
            rows.append({
                "business_code": r["business_code"],
                "keyword_score": round(score, 6),
            })
    rows.sort(key=lambda x: x["keyword_score"], reverse=True)
    return rows[:top_n]


def build_candidate_pool(
    vector_rows: list[dict[str, Any]],
    keyword_rows: list[dict[str, Any]],
    lookup: dict[str, dict[str, str]],
    activity: dict[str, Any] | None = None,
    is_offline_store: bool | None = None,
) -> list[dict[str, Any]]:
    """
    Hybrid 가중치/RRF를 쓰지 않는다.
    정렬 (2026-09-09):
      - 두 검색(벡터·키워드) 동시 검출 후보 우선
      - 그 안에서 vector_rank 에 역할 위치 가감(_ROLE_RANK_DELTA)을 더한 값으로 정렬
        · 역할 부합 후보는 앞으로(-6), 역할 상충 후보는 뒤로(+12) 밀되 창에서 빼지는 않는다
      - 동점이면 keyword_score
    """
    role = clean((activity or {}).get("business_role"))
    merged: dict[str, dict[str, Any]] = {}

    for r in vector_rows:
        code = r["business_code"]
        merged.setdefault(code, {"business_code": code})
        merged[code].update(r)
        merged[code]["from_vector"] = True

    for r in keyword_rows:
        code = r["business_code"]
        merged.setdefault(code, {"business_code": code})
        merged[code].update(r)
        merged[code]["from_keyword"] = True

    pool = []
    for code, signals in merged.items():
        ref = lookup.get(code)
        if not ref:
            continue
        both = bool(signals.get("from_vector")) and bool(signals.get("from_keyword"))
        fit = role_fit(role, ref.get("biz_large_names", ""), ref.get("business_name", "")) if role else 1
        # Q5: 오프라인 매장인데 후보가 공장·농장·건설·운수 대분류 → 상충 취급 (역할 신호와 같은 통로)
        if store_conflict(is_offline_store, ref.get("biz_large_names", "")):
            fit = 2
        pool.append({
            **ref,
            **signals,
            "in_both_searches": both,
            "role_fit": fit,
        })

    for x in pool:
        base_rank = x.get("vector_rank", 999999)
        role_d = _ROLE_RANK_DELTA.get(x.get("role_fit", 1), 0)   # Q5 상충도 이 통로로 반영됨
        x["role_adjusted_rank"] = base_rank + role_d

    pool.sort(
        key=lambda x: (
            0 if x["in_both_searches"] else 1,
            x["role_adjusted_rank"],
            -x.get("keyword_score", 0.0),
        )
    )

    for rank, row in enumerate(pool, start=1):
        row["candidate_rank"] = rank

    return pool


def candidate_view(c: dict[str, Any]) -> dict[str, Any]:
    """
    후보 1개를 UI/DB/JSON에 넘길 최소 필드로 정리한다.
    retrieval_similarity 는 검색 유사도(참고값)이지 정답 확률이 아니다.
    """
    return {
        "business_code": c["business_code"],
        "business_name": c["business_name"],
        "biz_sub_names": c.get("biz_sub_names", ""),
        "biz_middle_names": c.get("biz_middle_names", ""),
        "candidate_rank": c.get("candidate_rank"),
        "retrieval_similarity": c.get("cosine_similarity"),
        "from_vector": bool(c.get("from_vector")),
        "from_keyword": bool(c.get("from_keyword")),
    }


def pick_alternatives(
    shortlist: list[dict[str, Any]],
    selected_code: str,
    n: int = 5,
) -> list[dict[str, Any]]:
    """
    선택된 코드를 제외한 상위 후보 n개 (사용자의 '다른 업종 같아요'용).

    근거: 미국 Census BEACON — write-in 텍스트에 대해 '순위 매긴 후보 목록'을
    제시하고 응답자가 고르게 한다. gold_v2 실측상 대표 1개만 보면 정답률 67%,
    대표+대안이 넓을수록 사용자가 정답에 닿을 확률이 올라간다(pool 8위 안 72%, 10위 안 75%).
    프론트에서 confidence=mid/low 이면 n을 더 크게 요청해도 된다(비용 없음, 같은 검색 결과에서 슬라이스).
    """
    out = []
    for c in shortlist:
        if c["business_code"] == selected_code:
            continue
        out.append(candidate_view(c))
        if len(out) >= n:
            break
    return out


_CONF_ORDER = {"high": 3, "mid": 2, "low": 1}
_CONF_NAME = {3: "high", 2: "mid", 1: "low"}


def compute_confidence(
    llm_confidence: str,
    selected: dict[str, Any],
    vector_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    최종 신뢰도 = 재판정 LLM의 자기판단 + 검색 신호 가드.

    - LLM 신뢰도(high/mid/low)를 출발점으로 쓴다.
    - 아래 신호가 나쁘면 한 단계 낮춘다(올리지는 않는다).

    임계값 근거 = gold_set_v2 240건(통계청 해설서 <예시>/<제외> 기반) 실측
    calibration (29번, 2026-09-09):
        · 재판정이 고른 후보 순위: 1~3위 정확도 67% → 4위부터 37%로 급락.
          → rank ≥ 4 이면 한 단계 하향 (기존 임계값 6위는 너무 느슨했음)
        · 벡터·키워드 동시 검출: O 66% vs X 33%.
          → 한쪽에서만 잡히면 순위와 무관하게 하향
        · retrieval_margin(1위-2위 cosine 차): >0.15 71% vs ≤0.06 43%.
          → margin < 0.06 이고 1위도 아니면 하향
        · 근거가 확실히 얕은 경우(6위+ & 한쪽만) 는 low 로 확정.
    주의: 이 정답셋에서 최종 high 버킷의 실측 정확도는 ~74% 다. 넓은 입력에서는
      >90% high 버킷이 안 나온다 — high 는 "확실"이 아니라 "십중팔구"로 읽어야 하고
      자동 확정용이 아니다. (v1 42건의 high 95% 는 쉬운 손선별셋 과적합이었음)
    """
    order = _CONF_ORDER.get(llm_confidence, 1)
    rank = selected.get("candidate_rank") or 999
    both = bool(selected.get("from_vector")) and bool(selected.get("from_keyword"))

    margin = None
    if len(vector_candidates) >= 2:
        margin = round(
            float(vector_candidates[0]["cosine_similarity"])
            - float(vector_candidates[1]["cosine_similarity"]),
            4,
        )

    downgrades = []
    if rank >= 4:
        order = min(order, 2)
        downgrades.append(f"재판정이 후보 {rank}위 선택(≥4)")
    if not both:
        order = min(order, 2)
        downgrades.append("한 가지 검색에서만 잡힘")
    if margin is not None and margin < 0.06 and rank >= 2:
        order = min(order, 2)
        downgrades.append(f"1·2위 유사도차 얇음({margin})")
    if rank >= 6 and not both:
        order = 1
        downgrades.append("근거 얕음 → low 확정")

    return {
        "confidence": _CONF_NAME[order],
        "llm_confidence": llm_confidence,
        "retrieval_margin": margin,
        "selected_pool_rank": None if rank == 999 else rank,
        "found_by_both_searches": both,
        "confidence_downgrade_reason": "; ".join(downgrades),
    }


def rerank(
    client: OpenAI,
    llm_model: str,
    activity: dict[str, Any],
    pool: list[dict[str, Any]],
    top_n: int = RERANK_TOP_N,
    is_offline_store: bool | None = None,
) -> dict[str, Any]:
    shortlist = pool[:top_n]
    if not shortlist:
        raise RuntimeError("후보가 없습니다.")

    exclusion_notes = load_exclusion_notes()
    fit_label = {0: "부합", 1: "중립", 2: "상충"}

    blocks = []
    for i, c in enumerate(shortlist, start=1):
        excl = exclusion_notes.get(c["business_code"], [])
        excl_txt = ("\n이 코드가 아닌 활동(해설서 제외): "
                    + "; ".join(excl[:6])) if excl else ""
        blocks.append(f"""
후보 {i}
업종코드: {c['business_code']}
세세분류(활동명): {c['business_name']}
세분류: {c['biz_sub_names']}
소분류: {c['biz_small_names']}
중분류: {c['biz_middle_names']}
대분류: {c['biz_large_names']}
역할 적합성: {fit_label.get(c.get('role_fit', 1), '중립')}
main KSIC: {c['main_ksic_names']}
세부설명: {c['detail_descriptions']}{excl_txt}
""".strip())

    prompt = f"""
[실제 수익활동]
활동명: {activity['activity_name']}
분류표 표현(canonical): {activity['canonical_activity']}
사업자 역할(business_role): {activity['business_role']}
제품/서비스: {activity['product_service']}
근거: {activity['evidence']}
키워드: {', '.join(activity['search_keywords'])}
매장 운영(Q5): {_store_line(is_offline_store)}
  → 오프라인 매장을 운영한다면 대표 업종이 공장·농장·건설·운수일 수 없다(방문형 소매·음식·서비스).

[후보 {len(shortlist)}개]
{chr(10).join(blocks)}

[판정] 위 후보 중 하나의 업종코드만 선택하라.
1순위 기준은 '역할 적합성'이다. 역할 적합성이 [상충]인 후보는
제품명이 비슷해도 원칙적으로 고르지 않는다.
단, 활동 설명(canonical·제품/서비스·근거)이 명백히 그 [상충] 후보를 가리키고
다른 후보는 활동과 안 맞으면, 역할 라벨이 잘못 붙었다고 보고 그 후보를 골라도 된다.
그 다음 제품/서비스 직접일치 → 포함 예시 → 제외 규칙 위반 여부 순으로 본다.
""".strip()

    parsed = _chat_json(client, llm_model, RERANK_SYSTEM, prompt, RERANK_SCHEMA)
    selected_code = clean(parsed["selected_business_code"])
    allowed = {c["business_code"] for c in shortlist}

    if selected_code not in allowed:
        selected_code = shortlist[0]["business_code"]
        parsed["reason"] = (
            "후보 밖 코드가 반환되어 후보 1위로 대체됨. "
            + clean(parsed.get("reason"))
        )
        parsed["confidence"] = "low"

    selected = next(c for c in shortlist if c["business_code"] == selected_code)

    return {
        "selected_candidate": selected,
        "role_alignment": clean(parsed.get("role_alignment")),
        "reason": clean(parsed["reason"]),
        "confidence": clean(parsed.get("confidence")) or "low",
        "shortlist": shortlist,
        "alternatives": pick_alternatives(shortlist, selected_code),
    }


def decide_result_state(
    activity: dict[str, Any],
    pool: list[dict[str, Any]],
    confidence_level: str,
    selected_code: str,
    raw_top1_code: str,
) -> dict[str, Any]:
    """
    개정 계획서 §8.1 — 결과 3상태 + (필요 시) 확인 질문 1개.

    정보_추가_필요 : pool 비었거나 / 구조화가 classifiable=no / product_service 없음
    추천_가능      : 신뢰도 high AND 원문검색 1위 == 재판정 선택 AND 역할 경계 아님
                     (앙상블. 두 독립 신호 일치 = 88% 정확 / 34% 커버. 40_ensemble_gate.py)
    사용자_확인_필요: 그 외 (역할 경계면 역할질문, 아니면 후보쌍 질문)
    """
    if not pool:
        return {"result_state": "정보_추가_필요", "clarifying_question": _INFO_QUESTION,
                "state_reason": "후보 pool 이 비어 있음"}

    if activity.get("classifiable") is False:
        return {"result_state": "정보_추가_필요", "clarifying_question": _INFO_QUESTION,
                "state_reason": "구조화가 '이 설명으론 업종 특정 불가(classifiable=no)'로 판단"}

    if not clean(activity.get("product_service")):
        return {"result_state": "정보_추가_필요", "clarifying_question": _INFO_QUESTION,
                "state_reason": "구조화 단계가 '무엇을 파는지'를 뽑지 못함"}

    top = pool[:3]
    groups = {g for g in (_section_group(c.get("biz_large_names", "")) for c in top) if g}
    role_boundary = len(groups) >= 2

    ensemble_ok = bool(raw_top1_code) and clean(selected_code) == clean(raw_top1_code)
    conf_ok = (not _AUTO_REQUIRE_HIGH) or clean(confidence_level) == "high"
    if ensemble_ok and conf_ok and not role_boundary:
        return {"result_state": "추천_가능", "clarifying_question": "", "state_reason": ""}

    if role_boundary:
        return {"result_state": "사용자_확인_필요", "clarifying_question": _ROLE_QUESTION,
                "state_reason": f"상위 후보가 역할 경계에 걸침({', '.join(sorted(groups))})"}

    a, b = top[0], (top[1] if len(top) > 1 else top[0])
    q = f"'{a['business_name']}'과(와) '{b['business_name']}' 중 어느 쪽에 더 가깝나요?"
    why = "신뢰도 낮음" if not conf_ok else "원문검색↔재판정 불일치"
    return {"result_state": "사용자_확인_필요", "clarifying_question": q,
            "state_reason": f"{why} (conf={confidence_level or '?'})"}


def match_business_code(
    seed: str,
    problem_or_opportunity: str,
    solution_approach: str,
    is_offline_store: bool | None = None,
    region: str = "",
    use_llm_rerank: bool = True,
) -> dict[str, Any]:
    seed = clean(seed)
    problem = clean(problem_or_opportunity)
    solution = clean(solution_approach)
    region = clean(region)

    validate_inputs(seed, problem, solution, is_offline_store)

    llm_model, embedding_model = load_env()
    client = _openai_client()

    ref_df = load_reference()       # 아래 3개 전부 lru_cache — 2번째 호출부터 즉시 반환
    lookup = load_lookup()
    collection = open_chroma(embedding_model)

    activities = extract_activities(
        client, llm_model, seed, problem, solution, is_offline_store,
    )

    activity_results = []

    for activity in activities:
        queries = build_queries(activity)
        v = vector_search_multi(client, collection, embedding_model, queries)
        k = keyword_search(ref_df, activity)
        pool = build_candidate_pool(v, k, lookup, activity, is_offline_store)

        if use_llm_rerank:
            rr = rerank(client, llm_model, activity, pool, is_offline_store=is_offline_store)
        else:
            top1 = pool[0]
            rr = {
                "selected_candidate": top1,
                "role_alignment": "(LLM 재판정 비활성화)",
                "reason": "pool 1위 그대로 사용",
                "confidence": "low",
                "shortlist": pool[:RERANK_TOP_N],
                "alternatives": pick_alternatives(pool[:RERANK_TOP_N], top1["business_code"]),
            }

        sel = rr["selected_candidate"]
        conf = compute_confidence(rr["confidence"], sel, v)
        activity_results.append({
            "activity": activity,
            "queries": queries,
            "vector_candidates": v,
            "keyword_candidates": k,
            "candidate_pool": pool,
            "selected_candidate": sel,
            "role_alignment": rr["role_alignment"],
            "rerank_reason": rr["reason"],
            "confidence": conf["confidence"],
            "llm_confidence": conf["llm_confidence"],
            "retrieval_margin": conf["retrieval_margin"],
            "found_by_both_searches": conf["found_by_both_searches"],
            "confidence_downgrade_reason": conf["confidence_downgrade_reason"],
            "ai_predicted_score": sel.get("cosine_similarity"),
            "selected_rank": sel.get("candidate_rank"),
            "alternatives": rr["alternatives"],
        })

    primary_result = next(
        (r for r in activity_results if r["activity"]["priority"] == "primary"),
        activity_results[0],
    )

    raw_top1 = raw_text_top1(collection, embedding_model, f"{seed}\n{problem}\n{solution}")
    state = decide_result_state(
        primary_result["activity"],
        primary_result["candidate_pool"],
        primary_result["confidence"],
        primary_result["selected_candidate"]["business_code"],
        raw_top1,
    )

    p = primary_result["selected_candidate"]
    representative = {
        "activity_name": primary_result["activity"]["activity_name"],
        "result_state": state["result_state"],
        "clarifying_question": state["clarifying_question"],
        "state_reason": state["state_reason"],
        "business_code": p["business_code"],
        "business_name": p["business_name"],
        "confidence": primary_result["confidence"],
        "llm_confidence": primary_result["llm_confidence"],
        # 벤치마킹(BEACON/ONS) 반영: 확정값 + 대안 후보를 함께 제공
        "ai_predicted_code": p["business_code"],
        "ai_predicted_score": primary_result["ai_predicted_score"],
        "retrieval_margin": primary_result["retrieval_margin"],
        "candidate_rank": primary_result["selected_rank"],
        "found_by_both_searches": primary_result["found_by_both_searches"],
        "confidence_downgrade_reason": primary_result["confidence_downgrade_reason"],
        "alternatives": primary_result["alternatives"],
        # 이후 UI·DB 계층에서 채운다
        "user_selected_code": None,
        "changed_by_user": False,
    }

    additional = []
    used = {p["business_code"]}

    for r in activity_results:
        if r is primary_result or r["activity"]["priority"] != "secondary":
            continue
        c = r["selected_candidate"]
        if c["business_code"] in used:
            continue
        additional.append({
            "activity_name": r["activity"]["activity_name"],
            "business_code": c["business_code"],
            "business_name": c["business_name"],
            "confidence": r["confidence"],
            "llm_confidence": r["llm_confidence"],
            "ai_predicted_code": c["business_code"],
            "ai_predicted_score": r["ai_predicted_score"],
            "retrieval_margin": r["retrieval_margin"],
            "candidate_rank": r["selected_rank"],
            "found_by_both_searches": r["found_by_both_searches"],
            "confidence_downgrade_reason": r["confidence_downgrade_reason"],
            "alternatives": r["alternatives"],
            "user_selected_code": None,
            "changed_by_user": False,
        })
        used.add(c["business_code"])
        if len(additional) >= 2:
            break

    return {
        "models": {"llm_model": llm_model, "embedding_model": embedding_model},
        "input": {
            "seed": seed,                          # Q1 사업 아이템
            "problem_or_opportunity": problem,      # Q3 문제/기회
            "solution_approach": solution,          # Q4 해결 방식
            "is_offline_store": is_offline_store,   # Q5 매장 운영 여부
            "region": region,                      # Q6 지역 (업종 판정 미사용)
        },
        "activities": activities,
        "activity_results": activity_results,
        "representative_business": representative,
        "additional_businesses": additional,
    }


def print_result(result: dict[str, Any]) -> None:
    print("\n" + "=" * 88)
    print("23번 업종코드 매칭 - v3 (검색 품질 개선)")
    print("=" * 88)
    print(f"LLM: {result['models']['llm_model']}")
    print(f"Embedding: {result['models']['embedding_model']}")
    print(f"지역(검색 미사용): {result['input']['region'] or '(없음)'}")

    print("\n[1. 사업활동 구조화]")
    for i, a in enumerate(result["activities"], start=1):
        print(f"{i}. [{a['priority']}] {a['activity_name']}")
        print(f"   canonical  : {a['canonical_activity']}")
        print(f"   role       : {a['business_role']}")
        print(f"   제품/서비스 : {a['product_service']}")
        print(f"   검색어      : {', '.join(a['search_keywords'])}")

    for i, r in enumerate(result["activity_results"], start=1):
        print("\n" + "-" * 88)
        print(f"[Activity {i}] {r['activity']['activity_name']}  (role={r['activity']['business_role']})")
        print("-" * 88)

        name_by_code = {p["business_code"]: p["business_name"] for p in r["candidate_pool"]}

        def nm(code: str) -> str:
            return (name_by_code.get(code, "?") or "?")[:24]

        print("\n[2. Vector 병합 후보 TOP12]  ※ cosine은 정답확률 아님(후보검색용)")
        for c in r["vector_candidates"][:12]:
            print(
                f"  V{c['vector_rank']:>2} | {c['business_code']} | "
                f"{nm(c['business_code']):24s} | cos={c['cosine_similarity']:.4f} | "
                f"q{c.get('hit_query','-')} | {c.get('hit_doc_type','-')}"
            )

        print("\n[3. Keyword 후보 TOP8]")
        for c in r["keyword_candidates"][:8]:
            print(f"  {c['business_code']} | {nm(c['business_code']):24s} | kw={c['keyword_score']:.3f}")

        print("\n[4. 통합 후보 TOP10 (재판정 입력)]")
        for c in r["candidate_pool"][:10]:
            print(
                f"  TOP{c['candidate_rank']:>2} | {c['business_code']} | {c['business_name'][:24]:24s} | "
                f"both={c['in_both_searches']} | Vrank={c.get('vector_rank','-')} | kw={c.get('keyword_score','-')}"
            )

        s = r["selected_candidate"]
        margin = r["retrieval_margin"]
        margin_s = f"{margin:.4f}" if isinstance(margin, (int, float)) else "-"
        print("\n[5. GPT 재판정]")
        print(f"선택   : {s['business_name']} ({s['business_code']})")
        print(
            f"신뢰도 : {r['confidence']}  (LLM={r['llm_confidence']}"
            + (f", 하향: {r['confidence_downgrade_reason']}" if r['confidence_downgrade_reason'] else "")
            + ")"
        )
        print(f"신호   : 후보순위={r['selected_rank']}  1-2위 유사도차={margin_s}  벡터·키워드동시={r['found_by_both_searches']}")
        print(f"역할확인: {r['role_alignment']}")
        print(f"이유   : {r['rerank_reason']}")
        if r["alternatives"]:
            print("이 업종이 아니라면:")
            for alt in r["alternatives"]:
                sim = alt["retrieval_similarity"]
                sim_s = f"{sim:.4f}" if isinstance(sim, (int, float)) else "-"
                print(f"  · {alt['business_name']} ({alt['business_code']})  검색유사도(참고)={sim_s}")

    rep = result["representative_business"]
    print("\n" + "=" * 88)
    print("[최종 예측]")
    print("=" * 88)
    print(f"결과 상태: {rep['result_state']}"
          + (f"  ({rep['state_reason']})" if rep.get("state_reason") else ""))
    if rep.get("clarifying_question"):
        print(f"확인 질문: {rep['clarifying_question']}")
    print(f"대표 업종: {rep['business_name']} ({rep['business_code']})  [{rep['confidence']}]")
    print(f"대표 활동: {rep['activity_name']}")
    if rep["alternatives"]:
        print("다른 업종 같아요 → 후보:")
        for alt in rep["alternatives"]:
            print(f"  · {alt['business_name']} ({alt['business_code']})")

    if result["additional_businesses"]:
        print("\n함께 해당되는 업종")
        for x in result["additional_businesses"]:
            print(f"- {x['business_name']} ({x['business_code']})  [{x['confidence']}]")
            print(f"  활동: {x['activity_name']}")
            for alt in x["alternatives"]:
                print(f"    · 후보: {alt['business_name']} ({alt['business_code']})")
    else:
        print("\n함께 해당되는 독립 수익업종: 없음")


def _parse_offline(v: str) -> bool | None:
    v = (v or "").strip().lower()
    if v in ("y", "예", "true", "1", "o", "offline", "오프라인"):
        return True
    if v in ("n", "아니오", "false", "0", "x", "online", "온라인"):
        return False
    return None


def interactive_inputs() -> dict[str, Any]:
    return {
        "seed": input("\nQ1 사업 아이템:\n> ").strip(),
        "problem_or_opportunity": input("\nQ3 문제/기회:\n> ").strip(),
        "solution_approach": input("\nQ4 해결 방식:\n> ").strip(),
        "is_offline_store": _parse_offline(
            input("\nQ5 고객이 방문하는 오프라인 매장? (예/아니오, 생략가능):\n> ")),
        "region": input("\nQ6 지역(선택, 업종 판정 미사용):\n> ").strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed")
    parser.add_argument("--problem")
    parser.add_argument("--solution")
    parser.add_argument("--offline", default="", help="Q5 오프라인 매장 여부: 예/아니오 (생략 시 미입력)")
    parser.add_argument("--region", default="")
    parser.add_argument("--no-llm", action="store_true", help="LLM 재판정 없이 pool 1위 사용 (retrieval 평가용)")
    parser.add_argument("--json-out", type=Path, default=None, help="결과 JSON 저장 (Gold Set 구축용)")
    args = parser.parse_args()

    if args.seed and args.problem and args.solution:
        kw = {
            "seed": args.seed,
            "problem_or_opportunity": args.problem,
            "solution_approach": args.solution,
            "is_offline_store": _parse_offline(args.offline),
            "region": args.region,
        }
    else:
        kw = interactive_inputs()

    result = match_business_code(use_llm_rerank=not args.no_llm, **kw)
    print_result(result)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON 저장: {args.json_out.resolve()}")


if __name__ == "__main__":
    main()
