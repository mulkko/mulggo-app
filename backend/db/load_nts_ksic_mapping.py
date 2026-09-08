"""국세청 업종코드 ↔ KSIC 표준산업분류 대응표 적재 스크립트.

원본: "업종코드-표준산업분류 연계표.csv" (국세청 배포본).
nts_industry_codes(업종코드 마스터) + nts_ksic_mapping(업종코드-KSIC 대응) 두 테이블에 나눠서 넣는다.

정제 규칙 (2026-09-08 확인):
  - 실제 데이터는 6번째 줄부터 시작 (위 5줄은 제목/병합헤더).
  - KSIC 코드 끝에 '+'가 붙은 행(97건)은 "인적용역(직업)으로서의 코드"라는 표시.
    '+' 를 뗀 코드가 ksic_codes에 있으면 그 코드로 매핑하고 mapping_note에 남긴다.
  - '+' 를 떼도 ksic_codes에 없는 코드(90131, 90132, 85502 - ksic_codes 참고표 자체의 누락으로
    확인됨, DA2 확인 필요)는 건너뛰고 목록을 출력한다. 나중에 ksic_codes에 추가되면 재실행하면 됨.
  - 헤더 텍스트가 데이터처럼 섞여 들어간 행, NTS/KSIC 코드가 비어있는 행은 건너뛴다.

실행: python -m backend.db.load_nts_ksic_mapping
"""

import os
import sys

import pandas as pd
from dotenv import load_dotenv
from psycopg2.extras import execute_values

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.connection import get_connection  # noqa: E402

CSV_PATH = os.path.join(PROJECT_ROOT, "data", "업종코드-표준산업분류 연계표.csv")

# 컬럼 위치 (skiprows=5, header=None 기준 — 2026-09-08 확인)
COL_NTS_CODE = 2
COL_NTS_LARGE_CODE, COL_NTS_LARGE_NAME = 3, 4
COL_NTS_MEDIUM_CODE, COL_NTS_MEDIUM_NAME = 5, 6
COL_NTS_SMALL_CODE, COL_NTS_SMALL_NAME = 7, 8
COL_NTS_DETAIL_CODE, COL_NTS_DETAIL_NAME = 9, 10
COL_NTS_NAME = 11  # 세세분류명 (가장 세부 명칭)
COL_KSIC_CODE = 13


def load_and_clean():
    df = pd.read_csv(CSV_PATH, encoding="utf-8-sig", dtype=str, header=None, skiprows=5)

    before = len(df)
    df = df[df[COL_NTS_CODE].notna() & df[COL_KSIC_CODE].notna()]
    # 헤더가 데이터처럼 섞여 들어간 행 제거 (NTS 코드는 항상 숫자)
    df = df[df[COL_NTS_CODE].str.match(r"^\d+$", na=False)]
    print(f"원본 {before}행 -> 결측/헤더혼입 제거 후 {len(df)}행")

    return df


def build_nts_industry_rows(df: pd.DataFrame):
    seen = {}
    for _, r in df.iterrows():
        code = r[COL_NTS_CODE]
        if code in seen:
            continue
        seen[code] = (
            code,
            r[COL_NTS_NAME],
            r[COL_NTS_LARGE_CODE], r[COL_NTS_LARGE_NAME],
            r[COL_NTS_MEDIUM_CODE], r[COL_NTS_MEDIUM_NAME],
            r[COL_NTS_SMALL_CODE], r[COL_NTS_SMALL_NAME],
            r[COL_NTS_DETAIL_CODE], r[COL_NTS_DETAIL_NAME],
        )
    return list(seen.values())


def build_mapping_rows(df: pd.DataFrame, valid_ksic_codes: set):
    rows = []
    skipped = []
    for _, r in df.iterrows():
        nts_code = r[COL_NTS_CODE]
        raw_ksic = r[COL_KSIC_CODE]
        is_occupation = raw_ksic.endswith("+")
        ksic_code = raw_ksic.rstrip("+")

        if ksic_code not in valid_ksic_codes:
            skipped.append((nts_code, raw_ksic))
            continue

        note = "인적용역(직업) 기준 코드 — 원본 표기 '{}' 에서 '+' 제거".format(raw_ksic) if is_occupation else None
        rows.append((nts_code, ksic_code, note))
    return rows, skipped


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM nts_industry_codes")
    if cur.fetchone()[0] > 0:
        print("nts_industry_codes에 이미 데이터가 있습니다. 중복 적재를 막기 위해 중단합니다.")
        conn.close()
        return
    cur.execute("SELECT COUNT(*) FROM nts_ksic_mapping")
    if cur.fetchone()[0] > 0:
        print("nts_ksic_mapping에 이미 데이터가 있습니다. 중복 적재를 막기 위해 중단합니다.")
        conn.close()
        return

    cur.execute("SELECT code FROM ksic_codes")
    valid_ksic_codes = {row[0] for row in cur.fetchall()}

    df = load_and_clean()

    industry_rows = build_nts_industry_rows(df)
    mapping_rows, skipped = build_mapping_rows(df, valid_ksic_codes)

    execute_values(
        cur,
        """
        INSERT INTO nts_industry_codes
            (code, name, large_code, large_name, medium_code, medium_name,
             small_code, small_name, detail_code, detail_name)
        VALUES %s
        """,
        industry_rows,
    )
    print(f"nts_industry_codes: {len(industry_rows)}건 적재")

    execute_values(
        cur,
        """
        INSERT INTO nts_ksic_mapping (nts_code, ksic_code, mapping_note)
        VALUES %s
        """,
        mapping_rows,
    )
    print(f"nts_ksic_mapping: {len(mapping_rows)}건 적재")

    conn.commit()
    conn.close()

    if skipped:
        print()
        print(f"건너뛴 매핑 {len(skipped)}건 (ksic_codes에 코드 없음 — DA2 확인 필요):")
        for nts_code, raw_ksic in skipped:
            print(f"  nts_code={nts_code}, ksic_code(원본)={raw_ksic}")


if __name__ == "__main__":
    main()
