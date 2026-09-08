# backend/preprocessing/load_ksic_codes.py
#
# data/ksic_clean_v2.csv -> ksic_codes 테이블 시드 적재.
#
# ksic_codes는 "KSIC 코드 -> 이름/계층" 조회용 사전이다. 공고 매칭이 뱉는
# ksic_codes_matched(TEXT[])의 코드를 사람이 읽을 이름/계층으로 풀거나,
# 나중에 profile_business_types.ksic_code(FK) 저장 시 무결성 근거로 쓴다.
#
# 소스: data/ksic_clean_v2.csv (분류기 explicit_match.py가 쓰는 바로 그 파일).
#   같은 파일을 소스로 써야 "분류기가 내는 코드 = 이 테이블의 코드"가 어긋나지
#   않는다. 국세청(nts) 연계는 이번 범위 밖 (path a - 유저/공고 둘 다
#   텍스트->분류기->KSIC 로 통일해 비교, 국세청 코드 미사용).
#
# CSV 컬럼 -> 테이블 컬럼:
#   KSIC_코드        -> code        (세세분류 5자리, PK)
#   KSIC_세세분류명   -> name
#   KSIC_대분류코드   -> large_code   / KSIC_대분류명 -> large_name
#   KSIC_중분류코드   -> medium_code  / KSIC_중분류명 -> medium_name
#   KSIC_소분류코드   -> small_code   / KSIC_소분류명 -> small_name
#   KSIC_세분류코드   -> detail_code  / KSIC_세분류명 -> detail_name
#   (embedding_text 는 이 테이블로 안 넣는다)
#
# 재실행 안전: code 기준 UPSERT. 삭제/TRUNCATE 안 함(다른 테이블이
# ksic_codes를 FK로 참조하므로 TRUNCATE가 막힘).
#
# 실행: python -m backend.preprocessing.load_ksic_codes

import csv
import os

from psycopg2.extras import execute_values

from backend.db.connection import get_connection

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CSV_PATH = os.path.join(PROJECT_ROOT, "data", "ksic_clean_v2.csv")

# (CSV 컬럼, 테이블 컬럼) 순서 고정
COLUMN_MAP = [
    ("KSIC_코드", "code"),
    ("KSIC_세세분류명", "name"),
    ("KSIC_대분류코드", "large_code"),
    ("KSIC_대분류명", "large_name"),
    ("KSIC_중분류코드", "medium_code"),
    ("KSIC_중분류명", "medium_name"),
    ("KSIC_소분류코드", "small_code"),
    ("KSIC_소분류명", "small_name"),
    ("KSIC_세분류코드", "detail_code"),
    ("KSIC_세분류명", "detail_name"),
]
CSV_COLS = [c for c, _ in COLUMN_MAP]
DB_COLS = [d for _, d in COLUMN_MAP]


def _read_rows() -> list[tuple]:
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"KSIC 시드 파일이 없습니다: {CSV_PATH}")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in CSV_COLS if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV에 필요한 컬럼이 없습니다: {missing}")

        rows = []
        for line in reader:
            values = [(line[c] or "").strip() for c in CSV_COLS]
            if not values[0] or not values[1]:  # code, name 은 NOT NULL
                continue
            rows.append(tuple(v or None for v in values))
    return rows


def load() -> int:
    rows = _read_rows()
    if not rows:
        print("적재할 행이 없습니다.")
        return 0

    columns_sql = ", ".join(DB_COLS)
    update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in DB_COLS if c != "code")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        execute_values(
            cursor,
            f"""
            INSERT INTO ksic_codes ({columns_sql})
            VALUES %s
            ON CONFLICT (code) DO UPDATE SET {update_sql}
            """,
            rows,
        )
        connection.commit()
        cursor.execute("SELECT count(*) FROM ksic_codes")
        total = cursor.fetchone()[0]
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(f"UPSERT {len(rows)}건 완료 · ksic_codes 총 {total}행")
    return len(rows)


if __name__ == "__main__":
    load()
