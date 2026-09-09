"""commercial_districts 테이블을 메인 DB에서 분석용 별도 DB로 이관.

배경(2026-09-08): commercial_districts(전국 상가업소 270만 건, ~741MB)가
메인 Supabase 무료 플랜 저장 용량(500MB)을 초과시켜 프로젝트 전체가
읽기전용으로 잠기는 문제가 생김. 이 테이블은 users/announcements 등과
FK로 안 엮여 있어(ksic_codes/administrative_dong 참조는 있지만 이 두
테이블은 작아서 그대로 메인 DB에 둠) 별도 DB로 분리해도 기존 기능에
영향 없음.

메인 DB는 지금 읽기전용이라 SELECT만 가능 - 여기서는 읽기만 하고,
쓰기는 전부 새 분석용 DB(get_analysis_connection())로 간다.

실행: python -m backend.db.migrate_commercial_districts
"""

import sys
import time

from psycopg2.extras import execute_values

from backend.db.connection import get_connection, get_analysis_connection

BATCH_SIZE = 20000

COLUMNS = [
    "store_id", "store_name", "category_large", "category_medium",
    "category_small", "ksic_code", "ksic_name", "sido_name",
    "sigungu_name", "dong_code", "dong_name", "longitude", "latitude",
]


def main():
    src_conn = get_connection()
    dst_conn = get_analysis_connection()

    try:
        src_cur = src_conn.cursor(name="commercial_districts_export")  # 서버사이드 커서 - 270만건을 한번에 메모리로 안 올림
        src_cur.itersize = BATCH_SIZE
        src_cur.execute(f"SELECT {', '.join(COLUMNS)} FROM commercial_districts ORDER BY store_id")

        dst_cur = dst_conn.cursor()
        columns_sql = ", ".join(COLUMNS)
        placeholders = ", ".join(["%s"] * len(COLUMNS))

        total = 0
        start = time.time()
        while True:
            rows = src_cur.fetchmany(BATCH_SIZE)
            if not rows:
                break
            execute_values(
                dst_cur,
                f"INSERT INTO commercial_districts ({columns_sql}) VALUES %s ON CONFLICT (store_id) DO NOTHING",
                rows,
            )
            dst_conn.commit()
            total += len(rows)
            elapsed = time.time() - start
            print(f"{total}건 이관 완료 ({elapsed:.0f}초 경과)", flush=True)

        print(f"완료: 총 {total}건, {time.time() - start:.0f}초 소요")
    finally:
        src_conn.close()
        dst_conn.close()


if __name__ == "__main__":
    main()
