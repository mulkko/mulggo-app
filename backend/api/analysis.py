# 분석 리포트(상권/기술창업) 엔드포인트
#
# backend/analysis_report/{market,tech_startup}의 순수함수(전부 DataFrame을
# 인자로 받음)에, DB에서 읽어온 데이터를 실어 나르는 역할만 한다 — 판단 로직은
# 다시 구현하지 않는다.
#
# [컬럼명 번역 계층] analysis_report/*.py 안의 함수들은 원래 노트북(엑셀 원본)
# 기준 한글 컬럼명(예: "시도", "총인구수")을 그대로 쓰도록 옮겨졌는데, 실제 DB
# 테이블 컬럼은 영문(snake_case)이다. 그래서 이 파일의 SQL에서 `AS "한글명"`으로
# 별칭을 줘서, DB 스키마가 영문이어도 analysis_report 함수 쪽 코드는 손대지
# 않고 그대로 재사용한다.
#
# [성능] commercial_districts는 272만 행이라 매 요청마다 통째로 안 읽고,
# 요청받은 시도/시군구로 먼저 SQL에서 좁혀서 가져온다.

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import pandas as pd

from backend.db.connection import get_connection
from backend.analysis_report.market import population, industry_mix, density
from backend.analysis_report.tech_startup import venture

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _query_df(sql: str, params: dict | None = None) -> pd.DataFrame:
    connection = get_connection()
    try:
        return pd.read_sql(sql, connection, params=params)
    finally:
        connection.close()


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


# ── 상권 분석 ────────────────────────────────────────────

def _load_administrative_dong() -> pd.DataFrame:
    return _query_df(
        'SELECT sido AS "시도", sigungu AS "시군구", dong_name AS "행정동(행정기관명)", '
        '       code AS "행정기관코드", level AS "레벨" '
        "FROM administrative_dong"
    )


def _load_resident_population() -> pd.DataFrame:
    return _query_df('SELECT dong_code AS "행정동코드", total_population AS "총인구수" FROM resident_population')


def _load_living_population() -> pd.DataFrame:
    return _query_df(
        'SELECT sido AS "시도", sigungu AS "시군구", dong_name AS "행정동", '
        '       avg_population AS "평균인구값", population_type AS "구분" '
        "FROM living_population"
    )


def _load_commercial_districts(sido: str, sigungu: str) -> pd.DataFrame:
    """272만 행 전체가 아니라 요청받은 시도/시군구만 좁혀서 가져온다."""
    return _query_df(
        'SELECT latitude AS "위도", longitude AS "경도", '
        '       sido_name AS "시도명", sigungu_name AS "시군구명", dong_name AS "행정동명", '
        '       ksic_code AS "표준산업분류코드", '
        '       category_large AS "상권업종대분류명", category_medium AS "상권업종중분류명", '
        '       category_small AS "상권업종소분류명" '
        "FROM commercial_districts WHERE sido_name = %(sido)s AND sigungu_name = %(sigungu)s",
        params={"sido": sido, "sigungu": sigungu},
    )


@router.get("/market")
def get_market_report(sido: str, sigungu: str, dong: str, ksic_code: str | None = None) -> JSONResponse:
    """
    상권 분석 리포트. 필수: sido/sigungu/dong (드롭다운 선택값).
    ksic_code를 같이 주면 그 업종 기준 동일업종 밀집도까지 계산한다(안 주면 null).
    """
    try:
        resident = population.get_resident_population(_load_administrative_dong(), _load_resident_population(), sido, sigungu, dong)
        footfall = population.compute_footfall_score(_load_living_population(), sido, sigungu, dong)
    except ValueError as e:
        return _error(400, str(e), "REGION_NOT_FOUND")

    district_df = _load_commercial_districts(sido, sigungu)
    if district_df.empty:
        return _error(400, f"'{sido} {sigungu}'에 해당하는 상권 데이터가 없습니다.", "DISTRICT_DATA_NOT_FOUND")

    try:
        nearby = density.analyze_by_dong(district_df, sido, sigungu, dong, radius_m=500)
    except ValueError as e:
        return _error(400, str(e), "REGION_NOT_FOUND")

    industry_dist = industry_mix.get_industry_distribution(nearby, level="상권업종소분류명", top_n=4)

    density_grid = None
    if ksic_code:
        center_lat, center_lon = density.get_dong_center(district_df, sido, sigungu, dong)
        same_industry_count = density.count_same_industry(nearby, target_codes=ksic_code)
        density_grid = {
            "same_industry_count": same_industry_count,
            "grid": density.compute_density_grid(nearby, center_lat, center_lon, target_codes=ksic_code),
        }

    return JSONResponse(content={
        "success": True,
        "data": {
            "region": {"sido": sido, "sigungu": sigungu, "dong": dong},
            "resident_population": resident,
            "footfall": footfall,
            "industry_mix": industry_dist.to_dict(orient="records"),
            "density": density_grid,
        },
    })


# ── 기술창업 분석 ──────────────────────────────────────────

def _load_venture_companies() -> pd.DataFrame:
    df = _query_df(
        'SELECT ksic_code AS "표준산업분류코드", venture_type AS "벤처확인유형", '
        '       venture_valid_start_date AS "벤처유효시작일", sigungu AS "시군구" '
        "FROM venture_companies"
    )
    # SQL DATE 컬럼이 read_sql을 거쳐도 dtype이 안전하게 datetime64로 안 잡힐 수 있어
    # (드라이버/버전에 따라 object로 올 수 있음) 명시적으로 변환해서 compute_venture_type의
    # Timestamp 비교(>=)가 항상 되게 한다.
    df["벤처유효시작일"] = pd.to_datetime(df["벤처유효시작일"])
    return df


@router.get("/tech-startup")
def get_tech_startup_report(ksic_code: str) -> JSONResponse:
    """기술창업 분석 리포트. 유사 벤처기업 수 / 최근 투자유형 카운트 / 인증유형 구성 / 밀집도."""
    venture_df = _load_venture_companies()
    similar = venture.count_similar_venture_companies(venture_df, target_codes=ksic_code)

    if len(similar) == 0:
        return JSONResponse(content={
            "success": True,
            "data": {"similar_count": 0, "recent_investment_count": 0, "type_distribution": [], "density_grid": None},
        })

    reference_date = similar["벤처유효시작일"].max()
    recent_investment_count = venture.count_venture_type(similar, venture_type="벤처투자", period_years=1, reference_date=reference_date)
    type_distribution = venture.compute_venture_type_distribution(similar)
    density_grid = venture.compute_venture_density_grid(similar)

    return JSONResponse(content={
        "success": True,
        "data": {
            "similar_count": len(similar),
            "recent_investment_count": recent_investment_count,
            "type_distribution": type_distribution.to_dict(orient="records"),
            "density_grid": density_grid,
        },
    })
