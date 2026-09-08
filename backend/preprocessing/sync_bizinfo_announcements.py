# backend/preprocessing/sync_bizinfo_announcements.py
#
# [2026-09-07] announcements_raw_bizinfo -> announcements 전체 파이프라인.
#
#     raw_df   = load_raw_bizinfo_from_postgres()
#     clean_df = clean_bizinfo(raw_df)
#     common_df = transform_bizinfo_to_common(clean_df)
#     common_df = parse_target_conditions(common_df)
#     common_df = normalize_support_fields(common_df)
#     common_df = map_regions(common_df)
#     common_df = map_ksic(common_df)
#     final_df = validate_announcements(common_df)
#     upsert_announcements(final_df)
#
# 이 파일이 새로 만드는 건 "각 단계를 잇는 배관"뿐이다. 판단 로직(지역/업종)은
# 전부 기존 함수를 그대로 부른다 - 다시 구현하지 않는다:
#   - extract_region()   <- backend/preprocessing/extract_region.py (안 고침)
#   - decide_industry()  <- backend/ml/classifier/decide_industry.py (안 고침,
#     2026-09-07 기준 final_project/ksic_core보다 오래된 버전이라는 걸 알고
#     있음 - 이번 작업 범위에서 동기화는 의도적으로 제외함, 사용자 확인함)
#   - get_notice_full_text() <- backend/preprocessing/extract_all_texts.py
#   - _needs_region_review()  <- build_announcement_csv.py에 있던 걸 그대로 가져옴
#
# [필드 매핑 기준] docs/announcement_csv_columns.md(2026-09-05, 팀 확정본)를
# 그대로 따른다 - host_org_name=수행기관(exc_instt_nm), supervising_org=
# 소관기관(jrsd_instt_nm), category=대분류+중분류 합친 문자열 1개.
# company_type/support_field_large/medium 같은 팀 미검토 컬럼은 넣지 않는다.
#
# [알려진 한계 - 지금 고치지 않고 여기 기록만 함]
#   1) schema.sql엔 announcements_raw_bizinfo/announcements 테이블 정의가
#      없다(더 단순한 announcements_raw/announcements_parsed만 있음). 근데
#      crawler/bizinfo_api.py::save_to_db()는 이미 announcements_raw_bizinfo에
#      INSERT하는 코드가 있다 - 즉 실제 Supabase DB엔 이 테이블이 schema.sql
#      밖에서(수동으로, 또는 다른 스크립트로) 이미 만들어져 있을 가능성이
#      높다. 이 파일도 같은 전제(테이블이 실제로는 존재한다)로 작성했다.
#      만약 없다면 이 파일 실행 전에 먼저 테이블을 만들어야 한다.
#   2) [2026-09-07 수정 완료] refrnc_nm(문의처 원본, 실제 raw CSV에서 값 확인:
#      1589건 중 1588건에 담당기관+연락처 텍스트 존재)이 crawler의 INSERT
#      컬럼 목록에서 빠져있던 걸 발견해서 추가했다(bizinfo_api.py). 이
#      파일의 RAW_COLUMNS/TEXT_FIELDS에도 반영함. 단, 실제 Supabase의
#      announcements_raw_bizinfo 테이블 자체에 refrnc_nm 컬럼이 없으면
#      크롤러 INSERT가 실패한다 - 실행 전에 반드시 그 테이블에
#      `ALTER TABLE announcements_raw_bizinfo ADD COLUMN refrnc_nm TEXT;`
#      부터 해야 한다(이 파일에서 DDL을 직접 실행하지는 않음). 그리고 이
#      수정 이전에 이미 수집된 행들은 refrnc_nm이 비어있으므로(크롤러를
#      재실행하지 않는 한) contact가 여전히 None으로 남는다.
#   3) announcements 테이블 자체가 DB에 없다면 6번 함수(upsert_announcements)
#      실행 시 에러가 난다 - 이것도 스키마 쪽 문제라 여기서 해결 안 함.

import json

import pandas as pd

from backend.db.connection import get_connection
from backend.preprocessing.extract_region import extract_region
from backend.preprocessing.extract_all_texts import get_notice_full_text
from backend.ml.classifier.decide_industry import decide_industry, needs_human_review

# ==================================================================
# 0. RAW 조회
# ==================================================================

RAW_COLUMNS = [
    "raw_bizinfo_id", "pblanc_id", "pblanc_nm", "trget_nm", "jrsd_instt_nm",
    "exc_instt_nm", "bsns_sumry_cn", "pldir_sport_realm_lclas_code_nm",
    "pldir_sport_realm_mlsfc_code_nm", "reqst_begin_end_de", "reqst_mth_papers_cn",
    "hashtags", "pblanc_url", "rcept_engn_hmpg_url", "file_nm", "print_flpth_nm",
    "print_file_nm", "flpth_nm", "inqire_co", "creat_pnttm", "updt_pnttm",
    "refrnc_nm", "source_raw", "collected_at",
]


def load_raw_bizinfo_from_postgres(only_unprocessed: bool = False) -> pd.DataFrame:
    """announcements_raw_bizinfo 전체(또는 아직 announcements에 없는 것만)를
    DataFrame으로 읽어온다. pandas.read_sql이 psycopg2 커넥션을 그대로 받는다."""
    conn = get_connection()
    try:
        if only_unprocessed:
            query = """
                SELECT r.* FROM announcements_raw_bizinfo r
                LEFT JOIN announcements a
                  ON a.source = 'bizinfo' AND a.raw_bizinfo_id = r.raw_bizinfo_id
                WHERE a.raw_bizinfo_id IS NULL
            """
        else:
            query = "SELECT * FROM announcements_raw_bizinfo"
        return pd.read_sql(query, conn)
    finally:
        conn.close()


# ==================================================================
# 1. 기본 전처리 (기존 scripts/14_clean_bizinfo_raw.py와 동일 원칙,
#    컬럼명만 DB의 snake_case에 맞춤)
# ==================================================================

import re


def _clean_text(v):
    """NULL이라고 무조건 '없음'/0을 넣지 않는다 - 원본 의미를 보존한다.
    _x000D_ 제거, NBSP/zero-width space 제거, CRLF 통일, 연속 공백 정리,
    빈 문자열은 NULL로."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v)
    t = t.replace("_x000D_", "\n")
    t = t.replace("﻿", "")          # BOM
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = t.replace("\xa0", " ")           # NBSP
    t = t.replace("​", "")          # zero-width space
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    t = t.strip()
    return t or None


def _clean_html_field(v):
    """bsns_sumry_cn 등 HTML 섞인 필드. ksic_core.text_clean.clean_html()과
    동일 로직(mulkko엔 이 모듈이 없어서 필요한 부분만 인라인) - 태그 제거
    후 다시 한 번 _clean_text로 정규화."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    t = str(v)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"</p\s*>", "\n", t, flags=re.IGNORECASE)
    t = re.sub(r"<[^>]+>", "", t)
    import html as _html
    t = _html.unescape(t)
    return _clean_text(t)


def _parse_timestamp(v):
    """creat_pnttm/updt_pnttm/collected_at -> PostgreSQL timestamp 호환
    datetime. 실패하면 임의 보정하지 않고 None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        ts = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(ts) else ts
    except Exception:
        return None


TEXT_FIELDS = [
    "pblanc_nm", "trget_nm", "jrsd_instt_nm", "exc_instt_nm",
    "pldir_sport_realm_lclas_code_nm", "pldir_sport_realm_mlsfc_code_nm",
    "reqst_mth_papers_cn", "reqst_begin_end_de", "hashtags", "refrnc_nm",
]
URL_FIELDS = ["pblanc_url", "rcept_engn_hmpg_url", "print_flpth_nm", "flpth_nm"]
TIMESTAMP_FIELDS = ["creat_pnttm", "updt_pnttm", "collected_at"]


def clean_bizinfo(raw_df: pd.DataFrame) -> pd.DataFrame:
    """순수 기본 정제만 한다 - 지역/업종 판단, 추천, LLM 추론은 여기 넣지
    않는다(scripts/14_clean_bizinfo_raw.py와 동일 원칙)."""
    df = raw_df.copy()

    # 1) 중복: pblanc_id 기준, updt_pnttm 최신 우선(없으면 마지막 수집행 우선).
    #    RAW 테이블 행을 지우는 게 아니라 "전처리 결과에서 쓸 대표 행"만 고른다.
    if df["pblanc_id"].duplicated().any():
        df = df.sort_values(
            by=["updt_pnttm", "collected_at"], na_position="first"
        ).drop_duplicates(subset="pblanc_id", keep="last")

    for col in TEXT_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(_clean_text)
    if "bsns_sumry_cn" in df.columns:
        df["bsns_sumry_cn"] = df["bsns_sumry_cn"].apply(_clean_html_field)
    for col in URL_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(_clean_text)  # 공백/개행만 정리, URL 자체는 안 바꿈
    for col in TIMESTAMP_FIELDS:
        if col in df.columns:
            df[col] = df[col].apply(_parse_timestamp)

    return df


# ==================================================================
# 2. 신청기간 파싱 (원문 보존 + 파싱 가능한 것만 날짜 생성)
# ==================================================================

_DATE_PATTERNS = [
    r"(\d{4})-(\d{2})-(\d{2})",
    r"(\d{4})\.(\d{2})\.(\d{2})",
    r"(\d{4})/(\d{2})/(\d{2})",
]
_OPEN_ENDED_HINTS = {
    "예산소진시마감": r"예산\s*소진|모집\s*완료|모집\s*마감|모집규모\s*충족",
    "상시모집": r"상시|수시|연중",
    "선착순마감": r"선착순|선순",
    "세부사업별상이": r"세부사업별\s*상이|차수별\s*상이|분기별\s*상이|지원(?:분야|별)\s*상이",
}


def _find_date(text):
    for pat in _DATE_PATTERNS:
        m = re.search(pat, text)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def parse_apply_period(raw):
    """'2026-08-24 ~ 2026-09-11' / '2026.08.24 ~ 2026.09.11' 등 -> (start, end).
    상시/예산소진 등 고정 마감일이 없는 문장은 임의 날짜를 만들지 않는다."""
    if not raw:
        return None, None, "미기재"

    parts = re.split(r"~|∼|〜", raw, maxsplit=1)
    start = _find_date(parts[0]) if parts else None
    end = _find_date(parts[1]) if len(parts) > 1 else None

    if start and end:
        return start, end, "기간지정"
    if start and not end:
        return start, None, "시작일만기재"

    for period_type, pattern in _OPEN_ENDED_HINTS.items():
        if re.search(pattern, raw):
            return None, None, period_type
    return None, None, "기타"


# ==================================================================
# 3. 공통 필드 변환 (docs/announcement_csv_columns.md 팀 확정 매핑)
# ==================================================================

def transform_bizinfo_to_common(clean_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in clean_df.iterrows():
        start_date, end_date, period_type = parse_apply_period(r.get("reqst_begin_end_de"))

        lclas = r.get("pldir_sport_realm_lclas_code_nm") or ""
        mlsfc = r.get("pldir_sport_realm_mlsfc_code_nm") or ""
        category = " > ".join(p for p in [lclas, mlsfc] if p) or None

        rows.append({
            "source": "bizinfo",
            "raw_bizinfo_id": r.get("raw_bizinfo_id"),
            "raw_kstartup_id": None,
            "_pblanc_id": r.get("pblanc_id"),  # map_ksic/map_regions에서만 씀, 최종 컬럼 아님
            "_pblanc_nm": r.get("pblanc_nm"),
            "_bsns_sumry_cn": r.get("bsns_sumry_cn"),
            "_jrsd_instt_nm": r.get("jrsd_instt_nm"),
            "_print_flpth_nm": r.get("print_flpth_nm"),
            "_hashtags": r.get("hashtags"),

            "title": r.get("pblanc_nm"),
            "content": r.get("bsns_sumry_cn"),  # map_ksic에서 첨부원문 추출 후 대체될 수 있음

            "host_org_name": r.get("exc_instt_nm"),        # 팀 확정: 수행기관
            "supervising_org": r.get("jrsd_instt_nm"),     # 팀 확정: 소관기관
            "contact": r.get("refrnc_nm"),  # 팀 확정: 문의처 (2026-09-07 크롤러 INSERT 컬럼에 추가 완료)

            "category": category,
            "target_summary": r.get("trget_nm"),

            "apply_start_date": start_date,
            "apply_end_date": end_date,
            "_apply_period_type": period_type,  # 내부 참고용, 최종 컬럼 아님(팀 스키마에 없음)

            "apply_method": r.get("reqst_mth_papers_cn"),
            "detail_page_url": r.get("pblanc_url"),

            "management_no": None,  # 중복공고 판별 로직 자체가 아직 없음(팀 결정, 2026-09-05)

            "collected_at": r.get("collected_at"),
            # announcements.updated_at은 NOT NULL. 원본 updt_pnttm이 없으면
            # 수집 시각(collected_at)으로 폴백한다 (임의 시각을 만들지 않음).
            "updated_at": r.get("updt_pnttm") or r.get("collected_at"),
        })
    return pd.DataFrame(rows)


# ==================================================================
# 4. 대상조건 파싱 (bizinfo는 원본에 없어서 항상 NULL - 임의 추론 금지)
# ==================================================================

def parse_target_conditions(common_df: pd.DataFrame) -> pd.DataFrame:
    """target_age_groups/business_age_condition: bizinfo API엔 이 정보 자체가
    없다(팀 확정, 2026-09-05). 다른 소스(K-Startup 등) 연동 시 그쪽 어댑터가
    채운다 - 여기서 bizinfo 값으로 추론해서 채우지 않는다."""
    df = common_df.copy()
    df["target_age_groups"] = None
    df["business_age_condition"] = None
    return df


# ==================================================================
# 5. 지원분야 정규화 (지금은 category 하나로 이미 끝남 - 자리만 유지)
# ==================================================================

def normalize_support_fields(common_df: pd.DataFrame) -> pd.DataFrame:
    """category는 transform_bizinfo_to_common()에서 이미 '대분류 > 중분류'로
    합쳐졌다. 이 단계는 나중에 지원분야를 더 세분화하기로 팀이 결정하면
    로직을 넣을 자리로 남겨둔다 - 지금은 통과만 시킨다."""
    return common_df


# ==================================================================
# 6. 지역 매핑 (기존 extract_region() 재사용 - 새로 안 만듦)
# ==================================================================

def map_regions(common_df: pd.DataFrame) -> pd.DataFrame:
    df = common_df.copy()
    regions_col, status_col, needs_review_col = [], [], []

    for _, r in df.iterrows():
        result = extract_region(
            r.get("_pblanc_nm") or "",
            r.get("_jrsd_instt_nm") or "",
            r.get("_bsns_sumry_cn") or "",
            full_text=r.get("content") or "",
        )
        status = result.get("status", "")
        regions_col.append(result.get("regions") or [])
        status_col.append(status)
        needs_review_col.append(status.startswith("inferred_") or status == "unparsed")

    df["regions"] = regions_col
    df["region_status"] = status_col
    df["region_needs_review"] = needs_review_col
    return df


# ==================================================================
# 7. KSIC 업종코드 매핑 (기존 decide_industry() 재사용 - 새로 안 만듦)
# ==================================================================

def map_ksic(common_df: pd.DataFrame, use_llm_fallback: bool = False) -> pd.DataFrame:
    df = common_df.copy()
    codes_col, names_col, excluded_col, status_col, content_col = [], [], [], [], []

    for _, r in df.iterrows():
        # 첨부파일 원문 추출 - 무거운 단계라 실제 운영에선 캐시(이미 추출된
        # 적 있으면 재추출 안 함) 붙이는 걸 권장하지만, 이번 범위(연결 지점
        # 구성)에선 매번 호출하는 가장 단순한 형태로 둔다.
        full_text, _extract_status = get_notice_full_text(r.get("_print_flpth_nm") or "")
        full_text = full_text or ""
        content = full_text or r.get("content") or ""

        match_text = " | ".join(
            p for p in [r.get("_pblanc_nm") or "", r.get("_hashtags") or "", full_text] if p
        )
        result = decide_industry(match_text, use_llm_fallback=use_llm_fallback) if match_text.strip() else None

        codes_col.append(result["확정코드"] if result else [])
        names_col.append(result["확정업종명"] if result else [])
        excluded_col.append([x["코드"] for x in (result.get("제외업종") or [])] if result else [])
        status_col.append(result["확정단계"] if result else "특정불가")
        content_col.append(content)

    df["ksic_codes_matched"] = codes_col
    df["ksic_names_matched"] = names_col
    df["ksic_codes_excluded"] = excluded_col
    df["ksic_status"] = status_col
    df["content"] = content_col  # 첨부원문이 있으면 사업개요 요약 대신 그걸로 교체
    return df


# ==================================================================
# 8. 최종 검증
# ==================================================================

FINAL_COLUMNS = [
    "source", "raw_bizinfo_id", "raw_kstartup_id",
    "title", "content",
    "host_org_name", "supervising_org", "contact",
    "category", "target_summary", "target_age_groups", "business_age_condition",
    "apply_start_date", "apply_end_date", "apply_method", "detail_page_url",
    "regions", "region_status", "region_needs_review",
    "ksic_codes_matched", "ksic_names_matched", "ksic_codes_excluded", "ksic_status",
    "management_no", "collected_at", "updated_at",
]


def validate_announcements(common_df: pd.DataFrame):
    """검증 실패 행은 조용히 버리지 않고 (통과분, 검토대상) 두 DataFrame으로
    나눠서 둘 다 반환한다 - 호출부가 검토대상을 로그/별도 테이블로 처리."""
    df = common_df.copy()
    problems = []

    for idx, r in df.iterrows():
        errs = []
        if not r.get("source"):
            errs.append("source 없음")
        if r.get("source") == "bizinfo" and not r.get("raw_bizinfo_id"):
            errs.append("raw_bizinfo_id 없음")
        if not r.get("title"):
            errs.append("title 없음")
        if not isinstance(r.get("regions"), list):
            errs.append("regions가 배열 타입이 아님")
        if not isinstance(r.get("ksic_codes_matched"), list):
            errs.append("ksic_codes_matched가 배열 타입이 아님")
        if r.get("ksic_status") not in ("업종무관", "특정불가", "확인필요") and not r.get("ksic_codes_matched"):
            errs.append(f"ksic_status={r.get('ksic_status')}인데 확정코드가 비어있음 - 일관성 확인 필요")
        if r.get("apply_start_date") and r.get("apply_end_date"):
            if str(r["apply_start_date"]) > str(r["apply_end_date"]):
                errs.append("apply_start_date가 apply_end_date보다 늦음")

        if errs:
            problems.append({"row_index": idx, "raw_bizinfo_id": r.get("raw_bizinfo_id"), "errors": errs})

    dup = df[df["source"] == "bizinfo"]["raw_bizinfo_id"].duplicated()
    if dup.any():
        for idx in df.index[dup]:
            problems.append({"row_index": idx, "raw_bizinfo_id": df.loc[idx, "raw_bizinfo_id"],
                              "errors": ["같은 raw_bizinfo_id가 이 배치 안에서 중복"]})

    bad_idx = {p["row_index"] for p in problems}
    final_df = df.drop(index=list(bad_idx))[FINAL_COLUMNS].reset_index(drop=True)
    review_df = pd.DataFrame(problems)
    return final_df, review_df


# ==================================================================
# 9. UPSERT (raw_bizinfo_id 기준 - pblanc_id가 아니라 DB 내부 PK로 충돌 판정)
# ==================================================================

ARRAY_COLUMNS = {"regions", "ksic_codes_matched", "ksic_names_matched", "ksic_codes_excluded"}
INSERT_COLUMNS = FINAL_COLUMNS  # 순서 동일하게 유지


def upsert_announcements(final_df: pd.DataFrame) -> int:
    """source='bizinfo'인 행은 raw_bizinfo_id로 UPSERT한다(ERD 설계상
    announcements.raw_bizinfo_id가 announcements_raw_bizinfo의 PK를 참조하는
    FK이자 자연 유니크 키 - 같은 원본 공고를 재수집해도 행이 늘지 않음).
    지역/업종 매핑까지 끝난 완성된 행만 이 함수로 들어온다는 전제 -
    불완전한 상태로 먼저 INSERT하고 나중에 UPDATE하는 방식은 안 씀."""
    if final_df.empty:
        return 0

    conn = get_connection()
    try:
        cur = conn.cursor()
        columns_sql = ", ".join(INSERT_COLUMNS)
        placeholders = ", ".join(["%s"] * len(INSERT_COLUMNS))
        update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in INSERT_COLUMNS if c != "raw_bizinfo_id")

        sql = f"""
            INSERT INTO announcements ({columns_sql})
            VALUES ({placeholders})
            ON CONFLICT (raw_bizinfo_id) WHERE source = 'bizinfo'
            DO UPDATE SET {update_sql}
        """

        n = 0
        for _, r in final_df.iterrows():
            values = [list(r[c]) if c in ARRAY_COLUMNS else r[c] for c in INSERT_COLUMNS]
            cur.execute(sql, values)
            n += 1
        conn.commit()
        return n
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ==================================================================
# 실행
# ==================================================================

def run(only_unprocessed: bool = True, use_llm_fallback: bool = False):
    raw_df = load_raw_bizinfo_from_postgres(only_unprocessed=only_unprocessed)
    print(f"RAW 조회: {len(raw_df)}건")
    if raw_df.empty:
        return

    clean_df = clean_bizinfo(raw_df)
    common_df = transform_bizinfo_to_common(clean_df)
    common_df = parse_target_conditions(common_df)
    common_df = normalize_support_fields(common_df)
    common_df = map_regions(common_df)
    common_df = map_ksic(common_df, use_llm_fallback=use_llm_fallback)
    final_df, review_df = validate_announcements(common_df)

    print(f"검증 통과: {len(final_df)}건 / 검토 대상: {len(review_df)}건")
    if not review_df.empty:
        print(review_df.to_string())

    n = upsert_announcements(final_df)
    print(f"UPSERT 완료: {n}건")


if __name__ == "__main__":
    run()
