# backend/preprocessing/dryrun_sync_bizinfo.py
#
# sync_bizinfo_announcements 파이프라인 "미리보기(dry-run)".
#   - announcements_raw_bizinfo 에서 N건만 읽어
#   - 실제 파이프라인 단계를 전부 실행하되(지역판정/첨부다운로드/업종판정 포함)
#   - 마지막 DB 저장(upsert_announcements)만 건너뛰고
#   - 결과를 엑셀 파일로 저장한다.
#
# DB에는 아무것도 쓰지 않는다. 커밋 대상 아님(로컬 확인용).
#
# 실행:
#   python -m backend.preprocessing.dryrun_sync_bizinfo            # 기본 10건
#   python -m backend.preprocessing.dryrun_sync_bizinfo --limit 20
#   python -m backend.preprocessing.dryrun_sync_bizinfo --skip-attachments   # 첨부 다운로드 생략(빠름)

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
from backend.preprocessing import sync_bizinfo_announcements as S


def load_n(limit: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql(
            f"SELECT * FROM announcements_raw_bizinfo ORDER BY collected_at DESC LIMIT {int(limit)}",
            conn,
        )
    finally:
        conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--skip-attachments", action="store_true",
                    help="map_ksic의 첨부파일 다운로드/추출을 생략(사업개요 텍스트만으로 업종판정)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    print(f"[1/6] RAW {args.limit}건 조회 ...")
    raw_df = load_n(args.limit)
    print(f"      {len(raw_df)}건 로드")
    if raw_df.empty:
        print("raw 데이터가 없습니다."); return

    print("[2/6] 기본 정제 ...")
    clean_df = S.clean_bizinfo(raw_df)

    print("[3/6] 공통 필드 변환 ...")
    common_df = S.transform_bizinfo_to_common(clean_df)
    common_df = S.parse_target_conditions(common_df)
    common_df = S.normalize_support_fields(common_df)

    print("[4/6] 지역 매핑 (extract_region) ...")
    common_df = S.map_regions(common_df)

    if args.skip_attachments:
        print("[5/6] 업종 매핑 (첨부 생략, 사업개요 텍스트만) ...")
        _orig = S.get_notice_full_text
        S.get_notice_full_text = lambda *a, **k: (None, "skipped")
        try:
            common_df = S.map_ksic(common_df, use_llm_fallback=False)
        finally:
            S.get_notice_full_text = _orig
    else:
        print("[5/6] 업종 매핑 (첨부파일 다운로드 포함 - 시간 걸릴 수 있음) ...")
        common_df = S.map_ksic(common_df, use_llm_fallback=False)

    print("[6/6] 검증 (DB 저장은 안 함) ...")
    final_df, review_df = S.validate_announcements(common_df)

    # ---- 결과 저장 ----
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = args.out or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        f"dryrun_sync_bizinfo_{stamp}.xlsx",
    )

    def _flatten(df):
        df = df.copy()
        for c in df.columns:
            s = df[c]
            if s.apply(lambda v: isinstance(v, (list, dict))).any():
                df[c] = s.apply(lambda v: "" if v is None or (isinstance(v, (list, dict)) and not v) else str(v))
            elif s.apply(lambda v: hasattr(v, "tzinfo") and v.tzinfo is not None).any():
                # Excel은 timezone 붙은 시각을 못 씀 -> 문자열로
                df[c] = s.apply(lambda v: "" if v is None else str(v))
        return df

    with pd.ExcelWriter(out, engine="openpyxl") as w:
        _flatten(final_df).to_excel(w, sheet_name="통과분", index=False)
        if not review_df.empty:
            _flatten(review_df).to_excel(w, sheet_name="검토대상", index=False)

    # ---- 콘솔 요약 ----
    print("\n" + "=" * 60)
    print(f"검증 통과: {len(final_df)}건 / 검토 대상: {len(review_df)}건")
    print("=" * 60)
    if not final_df.empty:
        cols = ["title", "host_org_name", "contact", "regions", "region_status",
                "ksic_status", "ksic_codes_matched", "apply_start_date", "apply_end_date"]
        cols = [c for c in cols if c in final_df.columns]
        with pd.option_context("display.max_colwidth", 45, "display.width", 200):
            print(final_df[cols].to_string())
    if not review_df.empty:
        print("\n--- 검토 대상(검증 실패) ---")
        print(review_df.to_string())

    print(f"\n엑셀 저장: {out}")


if __name__ == "__main__":
    main()
