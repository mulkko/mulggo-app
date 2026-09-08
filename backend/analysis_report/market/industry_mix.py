# market/industry_mix.py
#
# 반경 내 업종 구성 집계 (화면 표시용, 한글 라벨 기준).
# 원본: backend/analysis_report/notebooks/market/industry_mix.ipynb

import pandas as pd


def get_industry_distribution(nearby_df: pd.DataFrame, level: str = '상권업종소분류명', top_n: int = 4) -> pd.DataFrame:
    """
    인근 업종 분포 집계 함수 (화면 표시용, 한글 라벨 기준)

    사용자가 하려는 업종과 무관하게, 반경 내 업체들의 업종 구성을
    그대로 집계해서 보여주는 함수. (예: "카페 18 / 음식점 13 / ...")
    "동일업종 카운트"(count_same_industry, density.py)와 달리 사용자 업종과의
    매칭/비교 로직이 없으므로 표준산업분류코드 변환 과정이 필요 없음.

    Parameters
    ----------
    nearby_df : pd.DataFrame
        반경 필터링된 결과 (market.density.filter_nearby / analyze_by_dong의 반환값)
    level : str
        집계 기준 컬럼명. 기본값은 소분류명("카페"처럼 구체적인 카테고리 표시용).
        더 넓은 카테고리(예: "음식")로 묶고 싶으면 '상권업종중분류명' 또는
        '상권업종대분류명'으로 지정
    top_n : int
        상위 몇 개 업종까지 반환할지 (기본 4개, 와이어프레임 카드 기준)

    Returns
    -------
    pd.DataFrame
        columns: [업종명, 업체수], 업체수 기준 내림차순 정렬된 상위 top_n개
    """
    # level로 지정한 컬럼이 실제 데이터에 있는지 먼저 확인
    if level not in nearby_df.columns:
        raise ValueError(f"'{level}' 컬럼이 존재하지 않습니다.")

    # 반경 내 업체들을 업종별로 그룹핑해서 개수 집계
    counts = (
        nearby_df[level]
        .value_counts()          # 업종별 개수 세기 (내림차순 자동 정렬)
        .reset_index()           # 인덱스를 컬럼으로 변환
    )
    counts.columns = ['업종명', '업체수']  # 컬럼명 보기 좋게 지정

    # 상위 top_n개만 반환 (와이어프레임엔 4개까지만 표시)
    return counts.head(top_n)
