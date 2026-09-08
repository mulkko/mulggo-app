# market/population.py
#
# 상주인구(주민등록인구) 조회 + 생활/유동인구 상대점수(percentile) 계산.
# 원본: backend/analysis_report/notebooks/market/population.ipynb
#
# 두 함수 다 순수함수 — 데이터는 호출부가 DataFrame으로 읽어서 넘긴다.
# (데이터 소스를 로컬 파일로 계속 쓸지 DB로 옮길지는 아직 미정이라 여기서
# 직접 로딩하지 않는다.)

import pandas as pd


def get_resident_population(df_dong_code: pd.DataFrame, df_resident: pd.DataFrame,
                             sido: str, sigungu: str, dong: str) -> dict:
    """
    상주인구(주민등록인구) 조회 함수

    행정동코드 데이터에서 동 이름에 해당하는 행정기관코드를 찾은 뒤,
    그 코드로 주민등록인구 데이터에서 총인구수를 조회한다.
    이 데이터는 '고양시 덕양구'처럼 구가 있는 시도 시군구 컬럼에
    이미 합쳐진 형태로 들어있어(유동인구 데이터와 다른 구조), 별도
    fallback 없이 레벨='행정동' 필터링만으로 정확히 매칭 가능.

    Parameters
    ----------
    df_dong_code : pd.DataFrame
        행정동코드 데이터 (시도, 시군구, 행정동(행정기관명), 행정기관코드, 레벨 컬럼 필요)
    df_resident : pd.DataFrame
        주민등록인구 데이터 (행정동코드, 총인구수 컬럼 필요)
    sido, sigungu, dong : str
        사용자가 선택한 시/도, 시군구, 동

    Returns
    -------
    dict
        {
            "dong_code": str,
            "region_name": str,
            "resident_population": int or None
        }
    """
    def normalize(s):
        return str(s).replace(" ", "").strip()

    dong_level = df_dong_code[df_dong_code['레벨'] == '행정동'].copy()

    target = dong_level[
        (dong_level['시도'].apply(normalize) == normalize(sido)) &
        (dong_level['시군구'].apply(normalize) == normalize(sigungu)) &
        (dong_level['행정동(행정기관명)'].apply(normalize) == normalize(dong))
    ]

    if len(target) == 0:
        raise ValueError(f"'{sido} {sigungu} {dong}'에 해당하는 행정동코드를 찾을 수 없습니다.")

    dong_code = target['행정기관코드'].iloc[0]

    pop_row = df_resident[
        df_resident['행정동코드'].astype(str) == str(dong_code)
    ]

    if len(pop_row) == 0:
        return {"dong_code": str(dong_code), "region_name": dong, "resident_population": None}

    return {
        "dong_code": str(dong_code),
        "region_name": dong,
        "resident_population": int(pop_row['총인구수'].iloc[0])
    }


def compute_footfall_score(df_pop_relabeled: pd.DataFrame, sido: str, sigungu: str, dong: str = None) -> dict:
    """
    생활인구/유동인구 상대 점수(percentile) 계산 함수

    데이터 특징: 유동인구 그룹에는 세 가지 형태가 섞여 있음
    1) 행정동 단위로 세분화된 경우 (예: 경기 성남시 분당구 구미동)
    2) 동으로 안 쪼개고 시 전체를 하나로 뭉친 경우 - 행정동 칸에 시군구와
       똑같은 이름을 넣어 표시함 (예: 강원 강릉시 -> 시군구=강릉시, 행정동=강릉시)
    3) '구가 있는 시'라서 시군구=시 이름, 행정동=구 이름으로 나뉜 경우
       (예: 시군구=고양시, 행정동=덕양구 - TA에서 "고양시 덕양구"로 넘어올 수 있음)
    이 순서대로 순차적으로 매칭을 시도(fallback)한다.

    같은 데이터 그룹(생활인구 vs 유동인구) 안에서만 percentile을 계산해야
    비교 범위가 다른 지역끼리 비교되는 왜곡을 막을 수 있다.

    Parameters
    ----------
    df_pop_relabeled : pd.DataFrame
        경기도 라벨 통일 전처리된 유동인구 데이터
        (전국_통합_생활인구_유동인구_260902_경기유동인구통일_fin_prep.csv)
    sido, sigungu : str
        사용자가 선택한 시/도, 시군구 (예: "고양시" 또는 "고양시 덕양구" 둘 다 지원)
    dong : str, optional
        사용자가 선택한 행정동

    Returns
    -------
    dict
        {
            "data_type": "생활인구" or "유동인구",
            "region_level": "행정동" / "시군구" / "시군구(구 단위)",
            "region_name": str,
            "raw_value": int or None,      # 원본 평균인구값
            "score": float or None,        # 0~100 percentile (같은 data_type 그룹 내 상대 위치)
            "basis": str or None           # 화면 표기용 안내 문구
        }
    """
    def normalize(s):
        return str(s).replace(" ", "").strip()

    life_pop = df_pop_relabeled[df_pop_relabeled['구분'] == '생활인구'].copy()
    life_pop['percentile'] = life_pop['평균인구값'].rank(pct=True) * 100

    floating_pop = df_pop_relabeled[df_pop_relabeled['구분'] == '유동인구'].copy()
    floating_pop['percentile'] = floating_pop['평균인구값'].rank(pct=True) * 100

    # 1차: 생활인구(서울)에서 동 단위 매칭
    target = pd.DataFrame()
    if dong is not None:
        target = life_pop[
            (life_pop['시도'].apply(normalize) == normalize(sido)) &
            (life_pop['시군구'].apply(normalize) == normalize(sigungu)) &
            (life_pop['행정동'].apply(normalize) == normalize(dong))
        ]

    if len(target) > 0:
        data_type, region_level, region_name = "생활인구", "행정동", dong
    else:
        # 2차: 유동인구에서 동 단위 매칭 (분당구 등 세분화된 지역)
        target = pd.DataFrame()
        if dong is not None:
            target = floating_pop[
                (floating_pop['시도'].apply(normalize) == normalize(sido)) &
                (floating_pop['시군구'].apply(normalize) == normalize(sigungu)) &
                (floating_pop['행정동'].apply(normalize) == normalize(dong))
            ]

        if len(target) > 0:
            data_type, region_level, region_name = "유동인구", "행정동", dong
        else:
            # 3차: 동으로 안 쪼개고 시 전체로 뭉친 경우 (행정동==시군구, 강릉시 등)
            target = floating_pop[
                (floating_pop['시도'].apply(normalize) == normalize(sido)) &
                (floating_pop['시군구'].apply(normalize) == normalize(sigungu)) &
                (floating_pop['행정동'].apply(normalize) == floating_pop['시군구'].apply(normalize))
            ]
            data_type, region_level, region_name = "유동인구", "시군구", sigungu

            if len(target) == 0:
                # 4차: '구가 있는 시' 케이스 - "고양시 덕양구"처럼 넘어오면 시/구로 분리해 재매핑
                parts = sigungu.split()
                if len(parts) == 2:
                    city_part, gu_part = parts
                    target = floating_pop[
                        (floating_pop['시도'].apply(normalize) == normalize(sido)) &
                        (floating_pop['시군구'].apply(normalize) == normalize(city_part)) &
                        (floating_pop['행정동'].apply(normalize) == normalize(gu_part))
                    ]
                    data_type, region_level, region_name = "유동인구", "시군구(구 단위)", sigungu

    if len(target) == 0:
        return {
            "data_type": None, "region_level": None, "region_name": sigungu,
            "raw_value": None, "score": None, "basis": None
        }

    raw_value = int(target['평균인구값'].iloc[0])
    score = round(float(target['percentile'].iloc[0]), 1)
    basis = f"{data_type} 기준 {region_level} 중 상위 {round(100 - score, 1)}%"

    return {
        "data_type": data_type,
        "region_level": region_level,
        "region_name": region_name,
        "raw_value": raw_value,
        "score": score,
        "basis": basis
    }
