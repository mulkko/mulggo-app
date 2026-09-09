# tech_startup/patent_forecast.py
#
# KIPRIS 특허 출원건수 조회 + 과거 추이 기반 시계열 예측(선형회귀) + 백테스트.
# 원본: backend/analysis_report/notebooks/tech_startup/patent_forecast.ipynb
#
# [환경변수] KIPRIS_API_KEY, OPENAI_API_KEY 필요 (.env.example 참고).
# llm_match.py와 동일한 원칙으로, 클라이언트는 모듈 import 시점이 아니라
# 함수 호출 시점에 생성한다 — 이 모듈을 import만 하고 실제로 안 쓰는 코드가
# 키 미설정 때문에 죽는 걸 방지.

import json
import re
import time
import xml.etree.ElementTree as ET
from os import environ

import httpx
import numpy as np
import requests
from dotenv import load_dotenv
from openai import OpenAI
from sklearn.linear_model import LinearRegression

load_dotenv()

KIPRIS_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getAdvancedSearch"


def _openai_client() -> OpenAI:
    # KIPRIS 응답이 gzip/br 압축을 지원하지 않아 원본 노트북에서 확인된 것과
    # 동일하게, OpenAI 클라이언트 쪽은 Accept-Encoding을 끈 커스텀 http client를 쓴다.
    custom_http_client = httpx.Client(headers={"Accept-Encoding": "identity"})
    return OpenAI(api_key=environ.get("OPENAI_API_KEY"), http_client=custom_http_client)


# ----------------------------------------------------------------------
# 특허 검색 키워드 생성 (슬롯 3개 → LLM → "도메인 단어 + 기능 단어" 키워드)
#
# [2026-09-09 개선] 기존엔 "정확히 2단어"만 요구해서, 모델이 도메인 단어
# (예: "농업", "스마트팜")를 버리고 기능 단어(예: "온습도 관리")만 남기는
# 경향이 있었다. "온습도 관리"는 업종 불문 너무 광범위해서 특허 검색 정확도가
# 떨어진다. 개선점:
#   1. "도메인 단어 + 기능 단어" 구조를 명시하고, 실패 사례를 나쁜 예시로 삽입
#   2. 결과에 도메인 단서가 전혀 없으면 딱 1회만 재시도 (무한루프 방지)
#   3. 모델을 gpt-5-nano → gpt-5-mini (3개 필드 종합 압축에 nano가 약함 —
#      아이디어 카드 기능에서도 같은 패턴 확인됨)
# ----------------------------------------------------------------------

_KEYWORD_SYSTEM_PROMPT = """너는 창업 아이디어를 특허 검색 키워드로 변환하는 도우미다.

[출력 규칙]
반드시 아래 구조로 키워드를 만든다: "도메인 단어 + 핵심 기능 단어" (총 2~3단어)
- 도메인 단어: 관심분야를 나타내는 단어. 관심분야가 너무 넓으면(예: "농업") 문제/해결방식에서
  더 구체적인 도메인 힌트(예: "스마트팜", "시설재배")를 찾아 대신 쓴다.
- 핵심 기능 단어: 문제를 해결하는 핵심 기술이나 방식을 나타내는 단어.
- 두 단어는 절대 하나로 합쳐지거나 생략되지 않는다. 도메인 단어를 빼고 기능 단어만
  남기는 것이 가장 흔한 실수이니 특히 주의한다.

[나쁜 예시 — 이렇게 하면 안 됨]
입력: 관심분야="농업", 문제="방울토마토 재배 시 온습도 관리가 어려움",
해결방식="스마트팜 자동 제어시스템"
나쁜 출력: {"keyword": "온습도 관리"}
→ 왜 나쁜가: 기능 단어("온습도 관리")만 남고 도메인 단어가 완전히 사라졌다. "온습도 관리"는
농업뿐 아니라 냉동창고, 반도체 공정, 건물 공조 등 업종 불문 너무 광범위한 검색어라
특허 검색 정확도가 크게 떨어진다.

[좋은 예시]
같은 입력에 대해:
{"keyword": "스마트팜 온습도"}
→ 해결방식에 등장한 구체적 도메인 힌트("스마트팜")를 도메인 단어로 채택하고, 문제의 핵심
기능("온습도" 관리)과 조합해서 특허 검색 시 농업/시설재배 분야로 범위가 좁혀지도록 했다.

[출력 형식]
아래 JSON 형식으로만 답한다. 다른 설명, 마크다운 코드블록은 포함하지 않는다.
{"keyword": "여기에 키워드"}
"""


def _build_keyword_user_prompt(seed_interest: str, problem_to_solve: str, solution_approach: str) -> str:
    return (
        f"관심분야: {seed_interest}\n"
        f"문제: {problem_to_solve}\n"
        f"해결방식: {solution_approach}"
    )


def _looks_domain_free(keyword: str, seed_interest: str, solution_approach: str) -> bool:
    """
    아주 단순한 휴리스틱: 관심분야/해결방식에 등장한 단어가 키워드에 하나도
    안 겹치면 도메인 정보가 날아갔을 가능성이 높다고 본다. 완벽한 검증은 아니고
    "온습도 관리"처럼 완전히 기능어만 남는 경우를 걸러내는 최소 안전망.
    """
    source_tokens = set(re.findall(r"[가-힣A-Za-z0-9]+", f"{seed_interest} {solution_approach}"))
    keyword_tokens = set(re.findall(r"[가-힣A-Za-z0-9]+", keyword))
    # 2글자 이상 토큰만 비교 (조사·짧은 단어 노이즈 제거)
    source_tokens = {t for t in source_tokens if len(t) >= 2}
    keyword_tokens = {t for t in keyword_tokens if len(t) >= 2}
    if not source_tokens:
        return False
    overlap = source_tokens & keyword_tokens
    # 부분 문자열 포함까지 느슨하게 확인 (예: "스마트팜" vs "스마트팜자동제어")
    if not overlap:
        overlap = {s for s in source_tokens for k in keyword_tokens if s in k or k in s}
    return len(overlap) == 0


def _parse_keyword(raw_response: str) -> str:
    """응답에서 keyword 문자열만 안전하게 추출. 실패하면 빈 문자열 (기존엔 KeyError로 죽었음)."""
    if not raw_response:
        return ""
    text = raw_response.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return ""
    return str(parsed.get("keyword", "")).strip()


def _call_keyword_llm(system_prompt: str, user_prompt: str) -> str:
    response = _openai_client().chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_completion_tokens=2000,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def generate_patent_keyword_with_debug(seed_interest: str, problem_to_solve: str, solution_approach: str) -> dict:
    """
    generate_patent_keyword()와 동작은 같지만, LLM에 보낸 프롬프트와 원본 응답까지
    같이 반환한다 — "왜 이 키워드가 나왔는지" 확인할 방법이 없다는 실측 피드백
    (예: 슬롯 3개에 비해 키워드가 너무 뭉뚱그려진 "온도 관리"로 나온 경우)에 대응하기
    위함. get_patent_trend_with_forecast()가 이 함수를 써서 결과에 keyword_debug를 싣는다.

    반환 dict:
      prompt              1차 호출에 쓴 user 프롬프트
      raw_response        1차 호출 원본 응답
      keyword             최종 채택된 키워드 (재시도했으면 재시도 결과)
      retried             도메인 누락으로 재시도했는지 여부 (bool)
      retry_prompt        (재시도 시에만) 보정 지시를 붙인 2차 프롬프트
      retry_raw_response  (재시도 시에만) 2차 호출 원본 응답
    """
    user_prompt = _build_keyword_user_prompt(seed_interest, problem_to_solve, solution_approach)
    raw_response = _call_keyword_llm(_KEYWORD_SYSTEM_PROMPT, user_prompt)
    keyword = _parse_keyword(raw_response)

    debug = {
        "prompt": user_prompt,
        "raw_response": raw_response,
        "keyword": keyword,
        "retried": False,
    }

    # 도메인 정보가 날아간 것으로 의심되면 딱 한 번만 더 강하게 재요청
    if _looks_domain_free(keyword, seed_interest, solution_approach):
        retry_prompt = (
            user_prompt
            + f"\n\n(주의: 방금 만든 키워드 후보 '{keyword}'는 도메인 단어가 빠져 있다. "
              f"관심분야 '{seed_interest}' 또는 해결방식에 담긴 구체적 도메인 단어를 "
              f"반드시 포함시켜서 다시 만들어라.)"
        )
        retry_raw = _call_keyword_llm(_KEYWORD_SYSTEM_PROMPT, retry_prompt)
        retry_keyword = _parse_keyword(retry_raw)
        debug.update({
            "keyword": retry_keyword or keyword,
            "retried": True,
            "retry_prompt": retry_prompt,
            "retry_raw_response": retry_raw,
        })

    return debug


def generate_patent_keyword(seed_interest: str, problem_to_solve: str, solution_approach: str) -> str:
    """슬롯 3개(관심분야/해결과제/해결방식) → 특허검색용 키워드 변환"""
    return generate_patent_keyword_with_debug(seed_interest, problem_to_solve, solution_approach)["keyword"]


def get_patent_count(keyword: str, year: int, field: str = "astrtCont", max_retries: int = 3):
    """키워드+연도 → 해당 연도 특허 출원건수 조회 (KIPRIS Open API)"""
    params = {
        "ServiceKey": environ.get("KIPRIS_API_KEY"),
        field: keyword,
        "applicationDate": f"{year}0101~{year}1231",
        "patent": "true",
        "utility": "true",
        "numOfRows": "1",
        "pageNo": "1",
    }
    for attempt in range(max_retries):
        try:
            res = requests.get(KIPRIS_URL, params=params, timeout=10)
            root = ET.fromstring(res.content)

            success = root.find(".//header/successYN")
            if success is not None and success.text == "N":
                result_msg = root.find(".//header/resultMsg")
                msg = result_msg.text if result_msg is not None else "알 수 없는 오류"
                print(f"API 호출 실패 ({keyword}, {year}년): {msg}")
                return None

            total_count_el = root.find(".//count/totalCount")
            return int(total_count_el.text) if total_count_el is not None else 0

        except requests.exceptions.ConnectionError:
            if attempt < max_retries - 1:
                print(f"연결 끊김 ({keyword}, {year}년) — {attempt+1}번째 재시도 중...")
                time.sleep(2)
            else:
                print(f"연결 끊김 ({keyword}, {year}년) — {max_retries}번 재시도 후 포기")
                return None


def predict_future_years(year_count_dict, exclude_recent=2):
    """
    과거 추이로 다음 해를 예측 (공개지연 구간 제외하고 학습).
    신뢰 가능한 마지막 연도 바로 다음 해(1년 뒤)만 예측한다.
    """
    all_years = sorted(year_count_dict.keys())
    reliable_years = all_years[:-exclude_recent] if exclude_recent > 0 else all_years

    years = np.array(reliable_years).reshape(-1, 1)
    counts = np.array([year_count_dict[y] for y in reliable_years])

    if len(years) < 3:
        return {}

    model = LinearRegression().fit(years, counts)

    next_year = max(reliable_years) + 1   # 2024년까지가 신뢰가능이면 → 2025년 하나만
    predicted = max(0, model.predict([[next_year]])[0])

    return {next_year: round(float(predicted), 1)}


def backtest_forecast(year_count_dict: dict, min_train_years: int = 5) -> tuple:
    """
    워크포워드 백테스트 — 이 모델이 과거에 얼마나 맞았는지 검증.

    과거 여러 시점을 돌아가며 '그 시점까지 데이터로 다음 해 예측 → 실제값과 비교'를 반복.

    반환: (시점별 결과 리스트, 평균절대오차 MAE)
    주의: 공개 지연 때문에 신뢰 못 하는 최근 연도는 호출 전에 이미 제외된 딕셔너리를 넣어야 함
    """
    years_sorted = sorted(year_count_dict.keys())
    results = []

    for i in range(min_train_years, len(years_sorted)):
        train_years = years_sorted[:i]
        test_year = years_sorted[i]

        X_train = np.array(train_years).reshape(-1, 1)
        y_train = np.array([year_count_dict[y] for y in train_years])

        model = LinearRegression()
        model.fit(X_train, y_train)

        predicted = max(0, model.predict([[test_year]])[0])
        actual = year_count_dict[test_year]
        error = abs(predicted - actual)

        results.append({
            "예측시점": test_year,
            "실제값": actual,
            "예측값": round(predicted, 1),
            "오차": round(error, 1),
        })

    if not results:
        return None, None

    mae = round(np.mean([r["오차"] for r in results]), 2)
    return results, mae


def get_patent_trend_with_forecast(seed_interest, problem_to_solve, solution_approach, past_years, exclude_recent=2):
    """전체 파이프라인: 키워드 생성 + 조회기간 확장 + 예측 + 백테스트까지 한 번에"""
    keyword_debug = generate_patent_keyword_with_debug(seed_interest, problem_to_solve, solution_approach)
    keyword = keyword_debug["keyword"]
    print(f"검색 키워드: {keyword}")

    actual = {}
    for yr in past_years:
        actual[yr] = get_patent_count(keyword, yr, field="astrtCont")
        time.sleep(0.3)

    reliable_years = sorted(actual.keys())[:-exclude_recent]
    reliable_actual = {y: actual[y] for y in reliable_years}

    forecast = predict_future_years(reliable_actual, exclude_recent=0)  # 이미 걸러진 걸 넣으니 0
    backtest_results, mae = backtest_forecast(reliable_actual, min_train_years=5)

    return {
        "keyword": keyword,
        "keyword_debug": {
            "prompt": keyword_debug["prompt"],
            "raw_response": keyword_debug["raw_response"],
            "retried": keyword_debug["retried"],
            "retry_prompt": keyword_debug.get("retry_prompt"),
            "retry_raw_response": keyword_debug.get("retry_raw_response"),
        },
        "actual": actual,
        "reliable_years": reliable_years,
        "forecast": forecast,   # 이제 {2025: 값} 딱 하나만 나옴
        "backtest_results": backtest_results,
        "mae": mae,
    }
