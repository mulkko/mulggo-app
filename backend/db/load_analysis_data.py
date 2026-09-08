# backend/db/load_analysis_data.py
#
# backend/analysis_report/{market,tech_startup} 함수들이 쓸 원본 데이터를
# 5개 테이블(administrative_dong, resident_population, living_population,
# commercial_districts, venture_companies)에 적재하는 1회성 스크립트.
#
# [2026-09-08] 원본 파일은 팀원에게 받아 E:\3차프로젝트\데이터\ 에 둔 상태.
# 대용량 원본이라 이 프로젝트(data/) 안으로 옮기지 않고 그 경로에서 바로 읽는다
# (data/README.md 원칙 — 대용량 원본은 저장소에 안 둠).
#
# [표준산업분류코드 형식 차이] 원본 파일은 "I56221"처럼 대분류 알파벳 + 5자리
# 코드를 쓰는데, DB의 ksic_codes.code는 5자리 숫자만 저장한다(예: "56221").
# 앞 알파벳 한 글자를 떼면 대부분 일치함을 확인했다(commercial_districts
# 479->43, venture_companies 934->1 불일치로 감소). 그래도 남는 소수 불일치
# 코드는 ksic_codes 테이블 자체의 결측(예: 90132 — nts_ksic_mapping 주석에도
# 이미 기록된 known gap)이라, 그런 경우 ksic_code를 NULL로 넣는다(행 자체는
# 살리고 업종 연결만 비움) — FK 제약 위반으로 전체 배치가 롤백되는 것 방지.
#
# 재실행 안전성: 각 테이블 로딩 전에 TRUNCATE 해서, 스크립트가 중간에 실패해도
# 다시 돌리면 중복 없이 안전하게 재적재된다.

import glob
import os
import sys

import pandas as pd
from psycopg2.extras import execute_values

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=True)

from backend.db.connection import get_connection

DATA_DIR = r"E:\3차프로젝트\데이터"
BATCH_SIZE = 5000


def strip_ksic_prefix(code):
    """'I56221' -> '56221'. 이미 숫자만 있으면 그대로 둔다."""
    if pd.isna(code):
        return None
    code = str(code).strip()
    return code[1:] if code and code[0].isalpha() else code


def nn(value):
    """pandas NaN/NaT -> None (psycopg2가 NaN을 못 넘김)."""
    return None if pd.isna(value) else value


def load_administrative_dong(cur):
    print("[1/5] administrative_dong 적재 중...")
    df = pd.read_csv(os.path.join(DATA_DIR, "행정동코드표.xls"), encoding="utf-8-sig")
    cur.execute("TRUNCATE administrative_dong CASCADE")
    rows = [
        (str(r["행정기관코드"]), r["시도"], nn(r.get("시군구")), nn(r.get("행정동(행정기관명)")), r["레벨"])
        for _, r in df.iterrows()
    ]
    execute_values(
        cur,
        "INSERT INTO administrative_dong (code, sido, sigungu, dong_name, level) VALUES %s "
        "ON CONFLICT (code) DO NOTHING",
        rows,
        page_size=BATCH_SIZE,
    )
    print(f"      -> {len(rows)}건")


def load_resident_population(cur):
    print("[2/5] resident_population 적재 중...")
    df = pd.read_csv(os.path.join(DATA_DIR, "주민등록인구.xls"), encoding="utf-8-sig")
    cur.execute("TRUNCATE resident_population")
    rows = [(str(r["행정동코드"]), int(r["총인구수"])) for _, r in df.iterrows()]
    execute_values(
        cur,
        "INSERT INTO resident_population (dong_code, total_population) VALUES %s",
        rows,
        page_size=BATCH_SIZE,
    )
    print(f"      -> {len(rows)}건")


def load_living_population(cur):
    print("[3/5] living_population 적재 중...")
    df = pd.read_csv(os.path.join(DATA_DIR, "전국_생활인구_유동인구_통합.csv"), encoding="utf-8-sig")
    cur.execute("TRUNCATE living_population")
    rows = [
        (r["시도"], r["시군구"], r["행정동"], str(r["행정코드"]), float(r["평균인구값"]), r["구분"], nn(r.get("비고")))
        for _, r in df.iterrows()
    ]
    execute_values(
        cur,
        "INSERT INTO living_population "
        "(sido, sigungu, dong_name, admin_code, avg_population, population_type, remarks) "
        "VALUES %s",
        rows,
        template="(%s, %s, %s, %s, %s, %s, %s::jsonb)",
        page_size=BATCH_SIZE,
    )
    print(f"      -> {len(rows)}건")


def load_commercial_districts(cur, known_ksic_codes):
    print("[4/5] commercial_districts 적재 중 (17개 파일, 시간이 좀 걸림)...")
    cur.execute("TRUNCATE commercial_districts")
    total = 0
    files = sorted(glob.glob(os.path.join(DATA_DIR, "소상공인 상권", "*.xls")))
    for f in files:
        df = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
        rows = []
        for _, r in df.iterrows():
            code = strip_ksic_prefix(r["표준산업분류코드"])
            if code not in known_ksic_codes:
                code = None
            rows.append((
                str(r["상가업소번호"]), r["상호명"],
                nn(r.get("상권업종대분류명")), nn(r.get("상권업종중분류명")), nn(r.get("상권업종소분류명")),
                code, nn(r.get("표준산업분류명")),
                nn(r.get("시도명")), nn(r.get("시군구명")),
                str(r["행정동코드"]) if not pd.isna(r.get("행정동코드")) else None, nn(r.get("행정동명")),
                nn(r.get("경도")), nn(r.get("위도")),
            ))
        execute_values(
            cur,
            "INSERT INTO commercial_districts "
            "(store_id, store_name, category_large, category_medium, category_small, "
            " ksic_code, ksic_name, sido_name, sigungu_name, dong_code, dong_name, longitude, latitude) "
            "VALUES %s ON CONFLICT (store_id) DO NOTHING",
            rows,
            page_size=BATCH_SIZE,
        )
        total += len(rows)
        print(f"      - {os.path.basename(f)}: {len(rows)}건 (누적 {total}건)")
    print(f"      -> 총 {total}건")


def load_venture_companies(cur, known_ksic_codes):
    print("[5/5] venture_companies 적재 중...")
    cur.execute("ALTER TABLE venture_companies ADD COLUMN IF NOT EXISTS sigungu VARCHAR(50)")
    df = pd.read_csv(os.path.join(DATA_DIR, "벤처기업명단.xls"), encoding="utf-8-sig")
    cur.execute("TRUNCATE venture_companies")
    rows = []
    for _, r in df.iterrows():
        code = strip_ksic_prefix(r["표준산업분류코드"])
        if code not in known_ksic_codes:
            code = None
        rows.append((
            r["업체명"], nn(r.get("벤처확인유형")), nn(r.get("업종명(11차)")), code, nn(r.get("주생산품")),
            nn(r.get("벤처유효시작일")), nn(r.get("벤처유효종료일")), nn(r.get("주소")), nn(r.get("시군구")),
        ))
    execute_values(
        cur,
        "INSERT INTO venture_companies "
        "(company_name, venture_type, industry_name_11th, ksic_code, main_product, "
        " venture_valid_start_date, venture_valid_end_date, address, sigungu) "
        "VALUES %s",
        rows,
        page_size=BATCH_SIZE,
    )
    print(f"      -> {len(rows)}건")


def main():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT code FROM ksic_codes")
        known_ksic_codes = {r[0] for r in cur.fetchall()}

        load_administrative_dong(cur)
        load_resident_population(cur)
        load_living_population(cur)
        load_commercial_districts(cur, known_ksic_codes)
        load_venture_companies(cur, known_ksic_codes)

        conn.commit()
        print("\n전체 커밋 완료.")

        print("\n최종 row count 확인:")
        for t in ["administrative_dong", "resident_population", "living_population",
                  "commercial_districts", "venture_companies"]:
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"  {t}: {cur.fetchone()[0]}건")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
