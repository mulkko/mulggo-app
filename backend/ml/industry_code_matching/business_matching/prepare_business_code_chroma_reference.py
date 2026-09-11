from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


# =============================================================================
# prepare_business_code_chroma_reference.py
#
# 목적
# - 원본 "업종코드-표준산업분류 연계표.csv"를 읽는다.
# - 6자리 업종코드가 없는 행은 제외한다.
# - "업종코드 1개 = Chroma 문서 1개"가 되도록 GROUP BY 한다.
# - 같은 업종코드에 연결된 여러 KSIC 11차 분류 정보를 한 행에 모은다.
# - `build_business_code_chroma.py` ChromaDB 구축 스크립트에서 바로 사용할 reference CSV를 만든다.
#
# 주의
# - 원본 CSV는 상단에 제목/다단 헤더가 있으므로 일반 header=0 방식으로 읽지 않는다.
# - 코드 컬럼은 반드시 문자열(str)로 읽어 011001 같은 앞자리 0을 보존한다.
# =============================================================================


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "raw" / "업종코드-표준산업분류 연계표.csv"
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "business_code_chroma_reference_v1.csv"
)


# 원본 CSV의 실제 컬럼 위치.
# 이 파일은 29열 구조이고, 실제 데이터는 pandas 기준 5번째 행(index=5)부터 시작한다.
COLUMN_MAP = {
    1: "serial_no",
    2: "business_code",
    3: "biz_large_code",
    4: "biz_large_name",
    5: "biz_middle_code",
    6: "biz_middle_name",
    7: "biz_small_code",
    8: "biz_small_name",
    9: "biz_sub_code",
    10: "biz_sub_name",
    11: "biz_detail_name",
    12: "business_link_flag",
    13: "ksic_code",
    14: "ksic_large_code",
    15: "ksic_large_name",
    16: "ksic_middle_code",
    17: "ksic_middle_name",
    18: "ksic_small_code",
    19: "ksic_small_name",
    20: "ksic_sub_code",
    21: "ksic_sub_name",
    22: "ksic_detail_name",
    23: "ksic_link_flag",
    24: "main_marker",
    25: "detail_description",
}


def clean_text(value: object) -> str:
    """NaN/None을 빈 문자열로 바꾸고 앞뒤 공백을 정리한다."""
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def ordered_unique(values: Iterable[object]) -> list[str]:
    """입력 순서를 유지하면서 빈 값과 중복을 제거한다."""
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        text = clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)

    return result


def join_unique(values: Iterable[object], sep: str = " | ") -> str:
    """중복 제거한 문자열 목록을 하나의 문자열로 합친다."""
    return sep.join(ordered_unique(values))


def read_source_csv(path: Path) -> pd.DataFrame:
    """
    원본 CSV를 읽고 실제 데이터 구간만 추출한다.

    원본 구조:
    - 0~4행: 제목/설명/다단 헤더
    - 5행부터 실제 데이터
    - 총 29개 열
    """
    if not path.exists():
        raise FileNotFoundError(
            f"원본 파일을 찾을 수 없습니다.\n"
            f"확인 경로: {path}"
        )

    # header=None + dtype=str:
    # 다단 헤더를 임의 컬럼명으로 해석하지 않고,
    # 6자리 업종코드의 앞자리 0도 유지한다.
    raw = pd.read_csv(
        path,
        header=None,
        dtype=str,
        encoding="utf-8-sig",
        keep_default_na=True,
    )

    if raw.shape[1] < 26:
        raise ValueError(
            f"예상한 원본 구조와 다릅니다. "
            f"최소 26열을 기대했지만 현재 {raw.shape[1]}열입니다."
        )

    # 실제 데이터는 pandas row index 5부터 시작
    data = raw.iloc[5:].copy()

    # 필요한 열만 선택하고 의미 있는 컬럼명 부여
    data = data[list(COLUMN_MAP.keys())].rename(columns=COLUMN_MAP)

    # 전 컬럼 문자열 정리
    for col in data.columns:
        data[col] = data[col].map(clean_text)

    return data


def validate_business_codes(df: pd.DataFrame) -> None:
    """업종코드가 6자리 숫자 문자열인지 검사한다."""
    invalid = df.loc[
        ~df["business_code"].str.fullmatch(r"\d{6}", na=False),
        "business_code",
    ]

    if not invalid.empty:
        examples = invalid.drop_duplicates().head(10).tolist()
        raise ValueError(
            "6자리 숫자 형식이 아닌 업종코드가 발견되었습니다.\n"
            f"예시: {examples}"
        )


def make_embedding_text(row: dict[str, str]) -> str:
    """
    `build_business_code_chroma.py`에서 Embedding할 기준 문서 텍스트를 만든다.

    업종코드 자체보다 업종 계층명, 세세분류 활동명,
    연결된 KSIC와 세부설명을 의미 정보로 충분히 넣는다.
    """
    parts: list[str] = [
        f"업종코드: {row['business_code']}",
        f"업종 대분류: {row['biz_large_names']}",
        f"업종 중분류: {row['biz_middle_names']}",
        f"업종 소분류: {row['biz_small_names']}",
        f"업종 세분류: {row['biz_sub_names']}",
        f"업종 세세분류 및 활동명: {row['biz_detail_names']}",
        f"연계 KSIC 11차 코드: {row['linked_ksic_codes']}",
        f"연계 KSIC 11차 분류명: {row['linked_ksic_names']}",
    ]

    if row["main_ksic_codes"]:
        parts.append(f"주요 연계 KSIC 코드: {row['main_ksic_codes']}")

    if row["main_ksic_names"]:
        parts.append(f"주요 연계 KSIC 분류명: {row['main_ksic_names']}")

    if row["detail_descriptions"]:
        parts.append(f"세부설명: {row['detail_descriptions']}")

    return "\n".join(part for part in parts if not part.endswith(": "))


def aggregate_by_business_code(data: pd.DataFrame) -> pd.DataFrame:
    """
    1,789개 연계행을 6자리 업종코드 기준으로 묶어
    '업종코드 1개 = 문서 1개' 구조로 만든다.
    """

    # 업종코드가 비어 있는 행은 KSIC만 있고 대응 국세청 업종코드가 없는 행이다.
    # 최종 목표가 6자리 업종코드 매칭이므로 기준 DB에서 제외한다.
    valid = data.loc[data["business_code"] != ""].copy()

    validate_business_codes(valid)

    records: list[dict[str, str | int]] = []

    for business_code, group in valid.groupby("business_code", sort=False):
        # 원본의 "메인" 컬럼은 값이 있는 연결행을 주요 연계로 보존한다.
        # 값 자체(1/2)도 버리지 않고 별도 컬럼에 남긴다.
        main_rows = group.loc[group["main_marker"] != ""]

        record: dict[str, str | int] = {
            "business_code": business_code,

            "biz_large_codes": join_unique(group["biz_large_code"]),
            "biz_large_names": join_unique(group["biz_large_name"]),

            "biz_middle_codes": join_unique(group["biz_middle_code"]),
            "biz_middle_names": join_unique(group["biz_middle_name"]),

            "biz_small_codes": join_unique(group["biz_small_code"]),
            "biz_small_names": join_unique(group["biz_small_name"]),

            "biz_sub_codes": join_unique(group["biz_sub_code"]),
            "biz_sub_names": join_unique(group["biz_sub_name"]),

            "biz_detail_names": join_unique(group["biz_detail_name"]),

            "linked_ksic_codes": join_unique(group["ksic_code"]),
            "linked_ksic_names": join_unique(group["ksic_detail_name"]),

            "main_ksic_codes": join_unique(main_rows["ksic_code"]),
            "main_ksic_names": join_unique(main_rows["ksic_detail_name"]),
            "main_relation_values": join_unique(main_rows["main_marker"]),

            "detail_descriptions": join_unique(group["detail_description"]),

            # 검증/디버깅용
            "source_row_count": int(len(group)),
        }

        record["embedding_text"] = make_embedding_text(record)  # type: ignore[arg-type]
        records.append(record)

    result = pd.DataFrame(records)

    # 출력 순서는 업종코드 오름차순으로 정렬해 사람이 확인하기 쉽게 한다.
    result = result.sort_values("business_code").reset_index(drop=True)

    return result


def print_summary(
    source_data: pd.DataFrame,
    result: pd.DataFrame,
    output_path: Path,
) -> None:
    """실행 후 사람이 바로 확인할 핵심 검증값을 출력한다."""
    no_business_code = int((source_data["business_code"] == "").sum())

    print("\n" + "=" * 70)
    print("prepare_business_code_chroma_reference.py: 전처리 완료")
    print("=" * 70)
    print(f"원본 연계행 수             : {len(source_data):,}")
    print(f"업종코드 없는 제외 행      : {no_business_code:,}")
    print(
        f"유효 연계행 수             : "
        f"{(source_data['business_code'] != '').sum():,}"
    )
    print(f"고유 6자리 업종코드 수     : {len(result):,}")
    print(f"출력 파일                  : {output_path}")
    print("=" * 70)

    print("\n[앞 3개 업종코드]")
    print(
        result[
            [
                "business_code",
                "biz_detail_names",
                "linked_ksic_codes",
                "linked_ksic_names",
                "source_row_count",
            ]
        ]
        .head(3)
        .to_string(index=False)
    )

    print("\n[Embedding text 예시]")
    print("-" * 70)
    print(result.iloc[0]["embedding_text"])
    print("-" * 70)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="6자리 업종코드 기준 Chroma reference CSV 생성"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help=f"원본 CSV 경로 (기본값: {DEFAULT_INPUT})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"출력 CSV 경로 (기본값: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    source_data = read_source_csv(args.input)
    result = aggregate_by_business_code(source_data)

    args.output.parent.mkdir(parents=True, exist_ok=True)

    result.to_csv(
        args.output,
        index=False,
        encoding="utf-8-sig",
    )

    print_summary(source_data, result, args.output)


if __name__ == "__main__":
    main()
