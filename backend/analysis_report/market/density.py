# market/density.py
#
# 반경 필터링(haversine 거리) + 반경 내 동일업종 카운트/밀집도 격자화.
# 원본: backend/analysis_report/notebooks/market/density.ipynb
#
# 히트맵 시각화(matplotlib) 코드는 노트북에만 남겨두고 여기엔 옮기지 않았다 —
# 서비스에서는 compute_density_grid()가 반환하는 격자 dict를 프론트가 직접
# 그린다(백엔드가 이미지를 렌더할 필요 없음).

import numpy as np
import pandas as pd


def haversine(lat1, lon1, lat2, lon2):
    """두 좌표 간 거리(m) 계산"""
    R = 6371000
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    return R * 2 * np.arcsin(np.sqrt(a))


def filter_nearby(df: pd.DataFrame, center_lat: float, center_lon: float, radius_m: float = 500) -> pd.DataFrame:
    """
    반경 필터링 함수

    Parameters
    ----------
    df : pd.DataFrame
        소상공인 상권데이터 (경도, 위도 컬럼 필수)
    center_lat, center_lon : float
        기준점(사용자 입력 위치) 위도/경도
    radius_m : float
        반경(미터), 기본 500m

    Returns
    -------
    pd.DataFrame
        반경 내 업체만 필터링 + distance_m 컬럼 추가, 가까운 순 정렬
    """
    required_cols = {'위도', '경도'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    clean_df = df.dropna(subset=['위도', '경도']).copy()
    clean_df = clean_df[(clean_df['위도'] != 0) & (clean_df['경도'] != 0)]

    clean_df['distance_m'] = haversine(
        center_lat, center_lon,
        clean_df['위도'].values, clean_df['경도'].values
    )

    nearby = clean_df[clean_df['distance_m'] <= radius_m].copy()
    nearby = nearby.sort_values('distance_m').reset_index(drop=True)

    return nearby


def get_dong_center(df: pd.DataFrame, sido: str, sigungu: str, dong: str) -> tuple:
    """
    동 이름 → 대표 좌표(centroid) 계산
    (공백 표기 차이 방지를 위해 정규화 후 비교)
    """
    def normalize(s):
        return str(s).replace(" ", "").strip()

    target = df[
        (df['시도명'].apply(normalize) == normalize(sido)) &
        (df['시군구명'].apply(normalize) == normalize(sigungu)) &
        (df['행정동명'].apply(normalize) == normalize(dong))
    ]

    if len(target) == 0:
        raise ValueError(f"'{sido} {sigungu} {dong}'에 해당하는 데이터가 없습니다.")

    center_lat = target['위도'].mean()
    center_lon = target['경도'].mean()

    return center_lat, center_lon


def analyze_by_dong(df: pd.DataFrame, sido: str, sigungu: str, dong: str, radius_m: float = 500) -> pd.DataFrame:
    """
    동 이름 입력 → 좌표 변환 → 반경 필터링까지 한번에
    """
    center_lat, center_lon = get_dong_center(df, sido, sigungu, dong)
    nearby = filter_nearby(df, center_lat, center_lon, radius_m)
    return nearby


def count_same_industry(nearby_df: pd.DataFrame, target_codes, code_col: str = '표준산업분류코드') -> int:
    """
    반경 내 동일업종 카운트 함수 (표준산업분류코드 기준)
    """
    if isinstance(target_codes, str):
        target_codes = [target_codes]
    if code_col not in nearby_df.columns:
        raise ValueError(f"'{code_col}' 컬럼이 존재하지 않습니다.")
    return int(nearby_df[code_col].isin(target_codes).sum())


def compute_density_grid(
    nearby_df: pd.DataFrame,
    center_lat: float,
    center_lon: float,
    target_codes,
    code_col: str = '표준산업분류코드',
    radius_m: float = 500,
    grid_size: int = 5
) -> dict:
    """
    동일업종 밀집도 격자화 함수 (표준산업분류코드 기준)

    반경 내 업체 중 사용자와 동일업종(target_codes)에 해당하는 업체들만 골라,
    중심좌표 기준 상대 위치를 grid_size x grid_size 격자 칸으로 변환하여
    칸별 밀집도(개수)를 계산한다. 화면의 히트맵/격자 시각화에 그대로 사용 가능.

    Parameters
    ----------
    nearby_df : pd.DataFrame
        반경 필터링된 결과 (filter_nearby / analyze_by_dong의 반환값)
    center_lat, center_lon : float
        기준 중심좌표 (analyze_by_dong 호출 시 get_dong_center로 계산된 값과 동일해야 함)
    target_codes : str or list[str]
        동일업종 판별 기준 표준산업분류코드 (count_same_industry와 동일한 값 사용 권장)
    code_col : str
        코드 비교 컬럼명 (기본: 표준산업분류코드)
    radius_m : float
        반경(미터). nearby_df를 만들 때 사용한 반경과 동일해야 격자 범위가 정확함 (기본 500m)
    grid_size : int
        격자 한 변의 칸 수 (기본 5x5 = 25칸)

    Returns
    -------
    dict
        {
            "grid_size": int,
            "center_cell": [x, y],       # 사용자 위치(중심점)가 위치한 격자 칸
            "cells": [{"x":.., "y":.., "count":..}, ...]  # 업체가 1개 이상 있는 칸만 포함
        }
    """
    if isinstance(target_codes, str):
        target_codes = [target_codes]

    if code_col not in nearby_df.columns:
        raise ValueError(f"'{code_col}' 컬럼이 존재하지 않습니다.")

    # 1. 동일업종만 필터링
    same_industry = nearby_df[nearby_df[code_col].isin(target_codes)].copy()

    # 동일업종이 하나도 없으면 빈 격자 반환 (에러 대신 안전하게 처리)
    if len(same_industry) == 0:
        return {
            "grid_size": grid_size,
            "center_cell": [grid_size // 2, grid_size // 2],
            "cells": []
        }

    # 2. 중심점 기준 상대좌표(m 단위)로 변환
    #    - dx: 동서 방향 거리 (중심보다 동쪽이면 +, 서쪽이면 -)
    #    - dy: 남북 방향 거리 (중심보다 북쪽이면 +, 남쪽이면 -)
    def to_meters(lat, lon, center_lat, center_lon):
        dx = haversine(center_lat, center_lon, center_lat, lon) * np.where(lon > center_lon, 1, -1)
        dy = haversine(center_lat, center_lon, lat, center_lon) * np.where(lat > center_lat, 1, -1)
        return dx, dy

    dx, dy = to_meters(
        same_industry['위도'].values, same_industry['경도'].values,
        center_lat, center_lon
    )
    same_industry['dx'] = dx
    same_industry['dy'] = dy

    # 3. 상대좌표(m)를 격자 칸 인덱스로 변환
    #    전체 반경(지름 = radius_m*2)을 grid_size 칸으로 나눠서 한 칸의 크기(m) 계산
    cell_meters = (radius_m * 2) / grid_size
    same_industry['grid_x'] = (same_industry['dx'] / cell_meters + grid_size // 2).astype(int).clip(0, grid_size - 1)
    same_industry['grid_y'] = (same_industry['dy'] / cell_meters + grid_size // 2).astype(int).clip(0, grid_size - 1)

    # 4. 칸별 업체 개수 집계
    grid_counts = (
        same_industry.groupby(['grid_x', 'grid_y'])
        .size()
        .reset_index(name='count')
    )

    cells = [
        {"x": int(row['grid_x']), "y": int(row['grid_y']), "count": int(row['count'])}
        for _, row in grid_counts.iterrows()
    ]

    return {
        "grid_size": grid_size,
        "center_cell": [grid_size // 2, grid_size // 2],
        "cells": cells
    }
