# tech_startup/venture.py
#
# 유사 벤처기업 카운트 / 투자유형 구성 / 동종산업 밀집도.
# 원본: backend/analysis_report/notebooks/tech_startup/venture.ipynb

import datetime  # noqa: F401  (원본 노트북 의존성 유지 — count_venture_type의 날짜 계산은 pandas Timestamp로 처리)

import pandas as pd


def count_similar_venture_companies(df_venture: pd.DataFrame, target_codes, code_col: str = '표준산업분류코드') -> pd.DataFrame:
    """
    유사 벤처인증기업 리스트 추출 함수

    사용자 업종과 매핑된 표준산업분류코드를 기준으로,
    전체 벤처기업명단에서 동일/유사 업종 기업만 필터링한다.
    이 함수의 반환값(리스트)이 count_venture_type, compute_venture_type_distribution,
    compute_venture_density_grid의 입력으로 재사용된다.

    Parameters
    ----------
    df_venture : pd.DataFrame
        벤처기업명단 전체 데이터
    target_codes : str or list[str]
        국세청 매핑을 거쳐 나온 표준산업분류코드 (여러 개일 수 있음)
    code_col : str
        비교 기준 컬럼명 (기본: 표준산업분류코드)

    Returns
    -------
    pd.DataFrame
        유사 업종에 해당하는 벤처기업 목록 (원본 컬럼 그대로 유지)
    """
    if isinstance(target_codes, str):
        target_codes = [target_codes]

    if code_col not in df_venture.columns:
        raise ValueError(f"'{code_col}' 컬럼이 존재하지 않습니다.")

    similar_companies = df_venture[df_venture[code_col].isin(target_codes)].copy()

    return similar_companies


def count_venture_type(similar_companies: pd.DataFrame, venture_type: str = "벤처투자",
                        period_years: int = 1, reference_date: str = None) -> int:
    """
    유사 벤처기업 중 특정 인증유형 + 최근 N년 이내 신규 인증 카운트

    "이 업종에 최근 투자가 몰리고 있는지"(최근 흐름)를 보여주기 위한 지표.
    누적 전체 건수가 아니라, 벤처유효시작일 기준으로 최근 N년 이내
    신규 인증된 건만 필터링한다.
    (참고: "유사 벤처인증기업 수"는 유형/기간 무관 누적 카운트이고,
    이 함수는 그중 특정 유형 + 최근 기간만 별도로 보는 것 — 서로 다른 지표)

    Parameters
    ----------
    similar_companies : pd.DataFrame
        count_similar_venture_companies()의 반환값
    venture_type : str
        벤처확인유형 값 (혁신성장/벤처투자/연구개발/예비벤처)
        기본값은 "벤처투자" — 실제 투자자(VC 등)로부터 투자를 받아
        인증된 유형으로, "시장에서 실제 투자금이 몰리고 있는지"를
        가장 직접적으로 보여주는 유형이기 때문
    period_years : int
        최근 몇 년 이내로 볼지 (기준: 벤처유효시작일)
    reference_date : str or pd.Timestamp, optional
        기준 날짜 (예: "2026-07-01" 또는 df['컬럼'].max() 같은 Timestamp).
        None이면 코드 실행 시점(오늘) 기준.
        데이터 스냅샷 특성상, 오늘 날짜가 아니라 데이터 안에 실제로
        존재하는 최신 날짜(예: df_venture['벤처유효시작일'].max())를
        넣는 것을 권장 — 파일 발급일과 실제 최신 데이터 시점이
        며칠 이상 어긋날 수 있어 결과가 달라지기 때문

    Returns
    -------
    int
        조건(인증유형 일치 + 최근 N년 이내 시작)에 맞는 기업 수
    """
    # 기준일 설정: 지정 안 하면 오늘 날짜, 지정하면 그 값 사용
    if reference_date:
        ref = pd.Timestamp(reference_date)
    else:
        ref = pd.Timestamp.now()

    # 기준일에서 N년 전 날짜 계산 → 이 날짜 이후 시작된 건만 "최근"으로 인정
    cutoff_date = ref - pd.DateOffset(years=period_years)

    filtered = similar_companies[
        (similar_companies['벤처확인유형'] == venture_type) &
        (similar_companies['벤처유효시작일'] >= cutoff_date)
    ]

    return len(filtered)


def compute_venture_type_distribution(similar_companies: pd.DataFrame) -> pd.DataFrame:
    """유사 벤처기업의 인증유형(혁신성장/벤처투자/연구개발/예비벤처) 구성비 계산"""
    counts = similar_companies['벤처확인유형'].value_counts().reset_index()
    counts.columns = ['인증유형', '건수']
    counts['비율(%)'] = (counts['건수'] / counts['건수'].sum() * 100).round(1)

    # 반올림 오차 보정: 합계가 100이 되도록 마지막 행에서 차이만큼 조정
    diff = round(100 - counts['비율(%)'].sum(), 1)
    counts.loc[counts.index[-1], '비율(%)'] += diff

    return counts


def compute_venture_density_grid(similar_companies: pd.DataFrame, grid_cols: int = 6, grid_rows: int = 3) -> dict:
    """
    동종산업 밀집도 격자화 함수 (시군구 단위)

    벤처기업명단에는 위경도가 없어 물리적 반경 계산이 불가능하므로,
    실제 지리적 좌표가 아닌 "시군구별 유사기업 개수"를 격자 형태로
    배치하는 추상적 시각화용 함수.
    시군구를 유사기업 수가 많은 순으로 정렬한 뒤 격자 칸에 순서대로 배치한다
    (실제 지리적 위치와는 무관 - 화면 문구 "개별 성공 확률 아님"과 일치하는 개념).

    Parameters
    ----------
    similar_companies : pd.DataFrame
        count_similar_venture_companies()의 반환값 (시군구 컬럼 포함된 데이터 기준)
    grid_cols : int
        격자 가로 칸 수 (기본 6, 화면 시안 기준)
    grid_rows : int
        격자 세로 칸 수 (기본 3, 화면 시안 기준)

    Returns
    -------
    dict
        {
            "grid_cols": int,
            "grid_rows": int,
            "cells": [{"x":.., "y":.., "count":.., "sigungu":..}, ...],  # 상위 grid_cols*grid_rows개만 포함
            "total_sigungu_count": int,
            "shown_sigungu_count": int,
            "total_company_count": int,
            "shown_company_count": int
        }
    """
    if '시군구' not in similar_companies.columns:
        raise ValueError("'시군구' 컬럼이 존재하지 않습니다.")

    sigungu_counts = (
        similar_companies['시군구']
        .value_counts()
        .reset_index()
    )
    sigungu_counts.columns = ['시군구', '건수']

    max_cells = grid_cols * grid_rows
    cells = []
    for idx, row in sigungu_counts.iterrows():
        if idx >= max_cells:
            break
        x = idx % grid_cols
        y = idx // grid_cols
        cells.append({
            "x": x,
            "y": y,
            "count": int(row['건수']),
            "sigungu": row['시군구']
        })

    return {
        "grid_cols": grid_cols,
        "grid_rows": grid_rows,
        "cells": cells,
        "total_sigungu_count": len(sigungu_counts),
        "shown_sigungu_count": len(cells),
        "total_company_count": int(sigungu_counts['건수'].sum()),
        "shown_company_count": sum(c['count'] for c in cells)
    }
