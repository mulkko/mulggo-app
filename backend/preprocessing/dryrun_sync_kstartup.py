# backend/preprocessing/dryrun_sync_kstartup.py
#
# sync_kstartup_announcements 파이프라인 "미리보기(dry-run)".
# dryrun_sync_bizinfo.py 와 동일 원리 — 마지막 DB 저장만 건너뛰고 엑셀로 저장.
# (K-Startup 은 첨부파일 다운로드/업종판정이 없어서 빠름)
#
# 실행:
#   python -m backend.preprocessing.dryrun_sync_kstartup            # 기본 10건
#   python -m backend.preprocessing.dryrun_sync_kstartup --limit 30

import argparse
import datetime as dt
import io
import os
import sys

import pandas as pd

# Windows 콘솔(cp949)에서 한글/특수문자 출력 시 UnicodeEncodeError 방지
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

from backend.db.connection import get_connection
from backend.preprocessing import sync_kstartup_announcements as S


def load_n(limit: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(
            f"SELECT * FROM announcements_raw_kstartup ORDER BY collected_at DESC, raw_kstartup_id DESC LIMIT {int(limit)}",
            conn,
        )
    finally:
        conn.close()


def _flatten(df):
    df = df.copy()
    for c in df.columns:
        s = df[c]
        if s.apply(lambda v: isinstance(v, (list, dict))).any():
            df[c] = s.apply(lambda v: "" if v is None or (isinstance(v, (list, dict)) and not v) else str(v))
        elif s.apply(lambda v: hasattr(v, "tzinfo") and v.tzinfo is not None).any():
            df[c] = s.apply(lambda v: "" if v is None else str(v))
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print(f"[1/6] RAW {args.limit}건 조회 ...")
    raw_df = load_n(args.limit)
    print(f"      {len(raw_df)}건 로드")
    if raw_df.empty:
        print("raw 데이터가 없습니다."); return

    print("[2/6] 기본 정제 + 모집중 필터 ...")
    clean_df = S.clean_kstartup(raw_df)
    print(f"      모집중/미마감 필터 후: {len(clean_df)}건")
    if clean_df.empty:
        print("필터 후 남은 게 없습니다."); return

    print("[3/6] 공통 필드 변환 ...")
    common_df = S.transform_kstartup_to_common(clean_df)
    common_df = S.parse_target_conditions(common_df)
    common_df = S.normalize_support_fields(common_df)

    print("[4/6] 지역 매핑 (normalize_kstartup_region) ...")
    common_df = S.map_regions(common_df)

    print("[5/6] 업종 매핑 (K-Startup은 '업종무관(기본값)' 고정) ...")
    common_df = S.map_ksic(common_df)

    print("[6/6] 검증 (DB 저장은 안 함) ...")
    final_df, review_df = S.validate_announcements(common_df)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        f"dryrun_sync_kstartup_{stamp}.xlsx",
    )
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        _flatten(final_df).to_excel(w, sheet_name="통과분", index=False)
        if not review_df.empty:
            _flatten(review_df).to_excel(w, sheet_name="검토대상", index=False)

    print("\n" + "=" * 60)
    print(f"검증 통과: {len(final_df)}건 / 검토 대상: {len(review_df)}건")
    print("=" * 60)
    if not final_df.empty:
        cols = ["title", "host_org_name", "supervising_org", "contact", "regions",
                "region_status", "ksic_status", "business_age_condition", "target_age_groups",
                "apply_start_date", "apply_end_date"]
        cols = [c for c in cols if c in final_df.columns]
        with pd.option_context("display.max_colwidth", 40, "display.width", 220):
            print(final_df[cols].to_string())
    if not review_df.empty:
        print("\n--- 검토 대상 ---")
        print(review_df.to_string())
    print(f"\n엑셀 저장: {out}")


if __name__ == "__main__":
    main()
