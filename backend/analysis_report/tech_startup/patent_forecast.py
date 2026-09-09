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


def _build_keyword_prompt(seed_interest: str, problem_to_solve: str, solution_approach: str) -> str:
    combined = f"{seed_interest} / {problem_to_solve} / {solution_approach}"
    return f"""다음은 한 창업 아이디어의 핵심 요소입니다.
여기서 특허 검색에 쓸 핵심 기술 키워드를 딱 하나만, 최대한 짧게 뽑아줘.
반드시 2개의 한국어 단어 조합으로 답해 (예: "스마트팜 제어", "온도 센서"). 3개 이상 단어는 절대 쓰지 마.

다음 JSON 형식으로만 답해: {{"keyword": "여기에 키워드"}}

핵심 요소: {combined}"""


def generate_patent_keyword_with_debug(seed_interest: str, problem_to_solve: str, solution_approach: str) -> dict:
    """
    [2026-09-08 추가] generate_patent_keyword()와 똑같이 동작하지만, GPT한테 보낸
    프롬프트와 원본 응답까지 같이 반환한다 — "왜 이 키워드가 나왔는지" 과정을
    확인할 방법이 없다는 실측 피드백(예: 입력 3개 슬롯에 비해 키워드가 너무
    뭉뚱그려진 "온도 관리"로 나온 경우)에 대응하기 위함. get_patent_trend_with_forecast()가
    이 함수를 써서 결과에 keyword_debug를 실어 보낸다.
    """
    prompt = _build_keyword_prompt(seed_interest, problem_to_solve, solution_approach)
    response = _openai_client().chat.completions.create(
        model="gpt-5-nano",
        messages=[{"role": "user", "content": prompt}],
        max_completion_tokens=2000,
        reasoning_effort="low",
        response_format={"type": "json_object"},
    )
    raw_response = response.choices[0].message.content
    keyword = json.loads(raw_response)["keyword"].strip()
    return {"prompt": prompt, "raw_response": raw_response, "keyword": keyword}


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
        "keyword_debug": {"prompt": keyword_debug["prompt"], "raw_response": keyword_debug["raw_response"]},
        "actual": actual,
        "reliable_years": reliable_years,
        "forecast": forecast,   # 이제 {2025: 값} 딱 하나만 나옴
        "backtest_results": backtest_results,
        "mae": mae,
    }
