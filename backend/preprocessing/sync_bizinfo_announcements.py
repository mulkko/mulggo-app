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
#   - decide_industry()  <- [2026-09-07] backend/ml/classifier/decide_industry.py를
#     썼음(final_project/ksic_core보다 오래된 버전이라는 걸 알고도 이번 작업 범위에서는
#     의도적으로 제외, 사용자 확인함). [2026-09-13] 이제 ksic_core(Pipeline V2.x,
#     Frozen)로 교체 완료 - backend/ml/classifier/ksic_core_service.py::predict_from_notice_text()
#     (사용자 확인). 반환 스키마가 영문 키로 바뀌어서 아래 map_ksic()에서 기존
#     한글 컬럼명(ksic_stage 등)으로 다시 변환한다.
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
import os

import pandas as pd

from backend.db.connection import get_connection
from backend.preprocessing.extract_region import extract_region
from backend.preprocessing.extract_all_texts import get_notice_full_text
from backend.ml.classifier.ksic_core_service import predict_from_notice_text

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


def load_raw_bizinfo_from_postgres(
    only_unprocessed: bool = False, limit: int | None = None, offset: int | None = None
) -> pd.DataFrame:
    """announcements_raw_bizinfo 전체(또는 아직 announcements에 없는 것만)를
    DataFrame으로 읽어온다. pandas.read_sql이 psycopg2 커넥션을 그대로 받는다.
    limit: 1,500여 건 전체를 매번 다 돌리면 테스트 한 번에 너무 오래 걸려서
    (첨부 다운로드+OCR 포함) 소량만 먼저 확인하거나 여러 번에 나눠 돌릴 때 씀.
    ORDER BY로 순서를 고정해야 limit 호출을 반복할 때 매번 같은/다음 구간이 잡힌다.
    offset: only_unprocessed=False(전체 재검증)일 때 배치로 나눠 돌리는 용도 -
    only_unprocessed=True면 처리된 건이 계속 빠지므로 offset 없이도 다음 구간이
    자동으로 잡히지만, False에서는 매번 같은 앞부분만 잡히는 걸 막아야 해서 필요."""
    conn = get_connection()
    try:
        if only_unprocessed:
            query = """
                SELECT r.* FROM announcements_raw_bizinfo r
                LEFT JOIN announcements a
                  ON a.source = 'bizinfo' AND a.raw_bizinfo_id = r.raw_bizinfo_id
                WHERE a.raw_bizinfo_id IS NULL
                ORDER BY r.raw_bizinfo_id
            """
        else:
            query = "SELECT * FROM announcements_raw_bizinfo ORDER BY raw_bizinfo_id"
        if limit:
            query += f" LIMIT {int(limit)}"
        if offset:
            query += f" OFFSET {int(offset)}"
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
            "_flpth_nm": r.get("flpth_nm"),  # map_ksic 첨부 추출 폴백용 - 전체 첨부파일 URL 목록("@" 구분)
            "_file_nm": r.get("file_nm"),  # map_ksic 로그(실행 결과 화면)에만 씀 - 원본 첨부파일명(확장자 포함)
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
# 7. KSIC 업종코드 매핑 (ksic_core_service.predict_from_notice_text() 재사용 - 새로 안 만듦,
#    [2026-09-13] 구버전 decide_industry()에서 교체)
# ==================================================================

def _normalize_stage(out: dict) -> str:
    """predict_from_notice_text()의 stage 필드를 신뢰하지 않고 ksic_codes/scope_decision만으로
    "확정단계"(기존 한글 어휘)를 다시 계산한다. preprocessing/pipeline.py::normalize_stage()와
    동일 로직(DA2가 자체 평가 스크립트에서 쓰는 canonical_stage()와 동일 - T1/독립110
    전체 검증됨, 사용자 확인, 2026-09-13) - 그 이유는 그쪽 주석 참고."""
    codes = out.get("ksic_codes") or []
    if codes:
        return "복수산업" if len(codes) > 1 else "세세분류"
    if out.get("scope_decision") == "ALL_INDUSTRIES":
        return "업종무관"
    return "특정불가"


def _get_notice_full_text_with_fallback(print_flpth_nm: str | None, flpth_nm: str | None):
    """대표 첨부(print_flpth_nm) 하나만 쓰면, 그게 하필 깨진 파일(서버가 0바이트로
    응답)일 때 나머지 첨부(flpth_nm, 전체 첨부 URL 목록)에 실제로 읽을 수 있는
    파일이 있어도 그냥 실패 처리됐다. [2026-09-11 raw_bizinfo_id=92 실측] print_flpth_nm
    쪽 첨부 4개 중 1개만 정상인데 대표로 지정된 게 하필 나머지였고, flpth_nm 쪽은
    4개 다 정상이었음. 대표 파일이 비거나 실패하면 flpth_nm의 첨부를 순서대로
    시도해서 처음 성공하는 걸 쓴다."""
    # [2026-09-12] pandas가 이 컬럼 전체가 NULL인 배치에서 dtype을 float64로 잡아서
    # 값이 문자열이 아니라 float('nan')으로 오는 경우가 있다 - `if x:` 만으론 못 거른다
    # (nan은 파이썬에서 참으로 취급됨, 실측: raw_bizinfo_id=5에서 매번 여기서 죽어서
    # "전체 재검증"이 3건 이후로 항상 중단됐음). isinstance로 진짜 문자열만 통과시킨다.
    if not isinstance(print_flpth_nm, str):
        print_flpth_nm = None
    if not isinstance(flpth_nm, str):
        flpth_nm = None

    candidates = []
    if print_flpth_nm:
        candidates.append(print_flpth_nm)
    if flpth_nm:
        candidates += [u for u in flpth_nm.split("@") if u and u not in candidates]

    if not candidates:
        return None, "no_url"

    last_text, last_status = None, "no_url"
    for url in candidates:
        last_text, last_status = get_notice_full_text(url)
        if last_status.startswith("success"):
            return last_text, last_status
    return last_text, last_status

def map_ksic(common_df: pd.DataFrame, use_llm_fallback: bool = False) -> pd.DataFrame:
    df = common_df.copy()
    codes_col, names_col, excluded_col, status_col, content_col = [], [], [], [], []

    # [2026-09-09] 첨부파일(신청서 양식/공고문) 원문 추출은 다운로드+OCR이라
    # 무거운 단계. bizinfo_attachment_text_cache 에 먼저 있는지 보고, 없을 때만
    # 실제로 추출해서 성공한 것만 캐시에 저장한다. 이 실행이 이후 단계(검증/
    # upsert)에서 실패하거나 서버가 중간에 죽어도, 재실행 때 이미 뽑아둔 첨부는
    # 다시 다운로드+OCR 하지 않는다. announcements 에 그 행이 성공적으로 들어가면
    # (같은 텍스트가 announcements.content 에도 남으므로) 캐시 행은
    # upsert_announcements() 에서 바로 지운다 - 계속 쌓이는 테이블이 아니다.
    cache_conn = get_connection()
    total = len(df)
    try:
        cache_cur = cache_conn.cursor()
        for i, (_, r) in enumerate(df.iterrows(), start=1):
            raw_id = r.get("raw_bizinfo_id")

            cache_cur.execute(
                "SELECT full_text FROM bizinfo_attachment_text_cache WHERE raw_bizinfo_id = %s", (raw_id,)
            )
            cached = cache_cur.fetchone()
            if cached:
                full_text = cached[0] or ""
                extract_status = "success(cache)"
            else:
                full_text, extract_status = _get_notice_full_text_with_fallback(
                    r.get("_print_flpth_nm"), r.get("_flpth_nm")
                )
                # 첨부원문(OCR/pdfplumber/pyhwp)에 간혹 NUL(0x00)이 섞여 들어오는데,
                # PostgreSQL text 컬럼은 NUL을 저장 못 해서 캐시 INSERT 자체가
                # 죽는다(upsert_announcements()가 이미 _strip_nul로 겪은 것과 동일
                # 원인) - 캐시에 넣기 전에도 똑같이 제거해야 한다.
                full_text = _strip_nul(full_text) or ""
                if extract_status.startswith("success") and raw_id is not None:
                    cache_cur.execute(
                        """
                        INSERT INTO bizinfo_attachment_text_cache (raw_bizinfo_id, full_text, extract_status)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (raw_bizinfo_id) DO UPDATE
                        SET full_text = EXCLUDED.full_text, extract_status = EXCLUDED.extract_status, cached_at = now()
                        """,
                        (raw_id, full_text, extract_status),
                    )
                    cache_conn.commit()
            content = full_text or r.get("content") or ""

            match_text = " | ".join(
                p for p in [r.get("_pblanc_nm") or "", r.get("_hashtags") or "", full_text] if p
            )
            result = predict_from_notice_text(match_text, use_llm_fallback=use_llm_fallback) if match_text.strip() else None
            ksic_stage = _normalize_stage(result) if result else "특정불가"

            # 관리자 화면 실행 로그에는 파일별 처리 단계 진단(디폴트로 안 찍음,
            # EXTRACT_DEBUG=1이면 찍힘) 대신 건별 "번호 | 본문추출 | 업종분류"
            # 성공/실패 요약 한 줄만 항상 남긴다.
            extract_ok = extract_status.startswith("success")
            ksic_ok = ksic_stage != "특정불가"
            # [2026-09-11] raw_bizinfo_id는 우리 DB 내부 번호라 기업마당 원문 사이트에서
            # 못 찾는다 - 실패 건 수정작업하려면 실제 공고번호(pblanc_id)가 필요해서 추가.
            # 첨부파일명(file_nm, 확장자 포함 - 여러 개면 "@"로 이어붙어 있음)도 같이 찍어서
            # 어떤 파일 형식에서 실패하는지 바로 보이게 한다.
            print(
                f"[{i}/{total}] raw_bizinfo_id={raw_id} pblanc_id={r.get('_pblanc_id')} | "
                f"첨부파일={r.get('_file_nm') or '-'} | "
                f"본문추출 {'성공' if extract_ok else '실패'}({extract_status}) | "
                f"업종분류 {'성공' if ksic_ok else '실패'}({ksic_stage})"
            )

            codes_col.append(result["ksic_codes"] if result else [])
            names_col.append(result["ksic_names"] if result else [])
            excluded_col.append([x["code"] for x in (result.get("excluded") or []) if x.get("code")] if result else [])
            status_col.append(ksic_stage)
            content_col.append(content)
    finally:
        cache_conn.close()

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
#
# ─────────────────────────────────────────────────────────────────
# [버그 수정 - 2026-09-08]
#
#   전체 실행(관리자 "통합 반영(임시)" 버튼 -> POST /admin/sync?source=bizinfo)이
#   1,559건 전부 처리(검증 통과 1559건)한 뒤, 마지막 upsert_announcements()의
#   cur.execute(sql, values) 에서 아래 에러로 죽었음:
#
#     ValueError: A string literal cannot contain NUL (0x00) characters.
#
#   원인: 첨부파일 원문 추출(OCR / pdfplumber / pyhwp)에서 간혹 NUL(0x00)
#   바이트가 섞여 content 필드에 들어오는데, PostgreSQL text 컬럼은 NUL을
#   저장 못 함. 걸러내질 않아서 1건이라도 걸리면 배치 전체 롤백 ->
#   announcements 에 bizinfo 행이 하나도 안 들어갔음.
#
#   수정: 저장 직전에 str / list[str] 값에서 "\x00" 제거 (_strip_nul, 아래).
#   sync_kstartup_announcements.py 의 upsert_announcements 도 같은 패턴이라
#   같이 고쳤음 (kstartup은 API 텍스트라 아직 안 걸렸을 뿐, 잠재적으로 동일 위험).
#
#   [2026-09-08 추가 수정] 위 NUL 버그 때문에 그동안 재실행할 때마다
#   announcements 에 저장된 게 하나도 없어서(only_unprocessed=True 여도)
#   1,559건 첨부 재다운로드 + 재OCR 로 몇 시간씩 다시 걸렸음 — 원인은
#   upsert_announcements()가 전체 배치를 한 번에 commit()해서, 1건이라도
#   실패하면 이미 처리한 나머지도 전부 롤백됐기 때문. 별도 캐시 테이블/파일을
#   새로 만드는 대신, 1건씩 바로 commit()하도록 바꿔서 해결 — 이러면 중간에
#   실패해도 그 전까지 저장된 행은 남고, only_unprocessed=True인 재실행 시
#   (load_raw_bizinfo_from_postgres의 LEFT JOIN ... WHERE a.raw_bizinfo_id
#   IS NULL 필터가) 이미 저장된 행은 자동으로 건너뛴다 - 즉 announcements
#   테이블 자체가 캐시 역할을 한다. 실패한 개별 행은 예외를 밖으로 던지지
#   않고 모아서 마지막에 로그로만 남긴다(한 건 실패가 나머지를 막지 않게).
# ─────────────────────────────────────────────────────────────────

ARRAY_COLUMNS = {"regions", "ksic_codes_matched", "ksic_names_matched", "ksic_codes_excluded"}
INSERT_COLUMNS = FINAL_COLUMNS  # 순서 동일하게 유지


def _strip_nul(v):
    """PostgreSQL text 컬럼은 NUL(0x00)을 저장 못 하는데, 첨부파일 원문
    추출(OCR/pdfplumber/pyhwp) 결과에 간혹 섞여 들어온다. 저장 직전에 제거.

    그리고 값이 None인 컬럼이 섞인 행을 final_df.iterrows()로 순회하면
    pandas가 그 None을 float('nan')으로 바꿔서 내보낸다(컬럼 dtype이
    문자열이어도 row Series로 합쳐지는 순간 생김) - apply_start_date처럼
    date 컬럼에 이게 들어가면 "'NaN'::float" 캐스팅 에러로 저장이 실패함.
    NaN은 자기 자신과도 같지 않다(v != v)는 성질로 판별해 None으로 되돌린다."""
    if isinstance(v, float) and v != v:
        return None
    if isinstance(v, str):
        return v.replace("\x00", "")
    if isinstance(v, list):
        return [x.replace("\x00", "") if isinstance(x, str) else x for x in v]
    return v


# [2026-09-09] 신청서류 첨부(announcement_attachments) 채우기.
# file_nm/flpth_nm은 같은 순서로 "@" 이어붙인 목록(여러 첨부) - raw 테이블에 이미
# 있는 값이라 별도 API 호출 없이 그대로 쪼개서 넣는다. zip 안에 뭐가 들었는지는
# 못 열어보므로 zip 자체를 그냥 파일 하나로 취급한다(사용자 확인, 2026-09-09).
_APPLICATION_FORM_HINTS = ("신청서", "양식")


def _file_type_of(file_name: str) -> str | None:
    ext = os.path.splitext(file_name)[1].lstrip(".").lower()
    return ext or None


def _attachment_role_of(file_name: str) -> str:
    return "신청서양식" if any(h in file_name for h in _APPLICATION_FORM_HINTS) else "붙임"


def _replace_attachments(cur, announcement_id: int, file_nm: str | None, flpth_nm: str | None) -> None:
    """announcement_attachments를 이 공고 기준으로 통째로 갈아끼운다(재실행 시
    중복 누적 방지) - DELETE 후 INSERT."""
    cur.execute("DELETE FROM announcement_attachments WHERE announcement_id = %s", (announcement_id,))
    # pd.isna(): file_nm/flpth_nm이 raw_df(pd.read_sql 결과)에서 온 값이라
    # None 대신 NaN(float)으로 올 수 있다 - 이번 세션에서 겪은 것과 동일한 함정.
    if pd.isna(file_nm) or pd.isna(flpth_nm):
        return

    names = [n for n in file_nm.split("@") if n]
    urls = [u for u in flpth_nm.split("@") if u]
    if len(names) != len(urls):
        # 개수가 안 맞으면(원본 데이터 이상) 매칭을 신뢰할 수 없으므로 건너뛴다.
        return

    for name, url in zip(names, urls):
        cur.execute(
            """
            INSERT INTO announcement_attachments
                (announcement_id, file_name, file_type, attachment_role, source_url, collected_at)
            VALUES (%s, %s, %s, %s, %s, now())
            """,
            (announcement_id, name, _file_type_of(name), _attachment_role_of(name), url),
        )


def upsert_announcements(final_df: pd.DataFrame, attachments_by_raw_id: dict | None = None) -> int:
    """source='bizinfo'인 행은 raw_bizinfo_id로 UPSERT한다(ERD 설계상
    announcements.raw_bizinfo_id가 announcements_raw_bizinfo의 PK를 참조하는
    FK이자 자연 유니크 키 - 같은 원본 공고를 재수집해도 행이 늘지 않음).
    지역/업종 매핑까지 끝난 완성된 행만 이 함수로 들어온다는 전제 -
    불완전한 상태로 먼저 INSERT하고 나중에 UPDATE하는 방식은 안 씀.

    attachments_by_raw_id: {raw_bizinfo_id: (file_nm, flpth_nm)} - 넘기면 UPSERT
    직후(announcement_id를 알아야 FK를 채울 수 있어서 이 시점에만 가능) 신청서류
    첨부까지 announcement_attachments에 같이 채운다."""
    if final_df.empty:
        return 0

    attachments_by_raw_id = attachments_by_raw_id or {}
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
            RETURNING announcement_id
        """

        n = 0
        failed = []
        for _, r in final_df.iterrows():
            # NaN -> None 처리는 _strip_nul()이 한다 (아래 함수 docstring 참고).
            values = [_strip_nul(list(r[c]) if c in ARRAY_COLUMNS else r[c]) for c in INSERT_COLUMNS]
            raw_id = r.get("raw_bizinfo_id")
            try:
                cur.execute(sql, values)
                announcement_id = cur.fetchone()[0]

                if raw_id in attachments_by_raw_id:
                    file_nm, flpth_nm = attachments_by_raw_id[raw_id]
                    _replace_attachments(cur, announcement_id, file_nm, flpth_nm)

                conn.commit()
                n += 1
                # [2026-09-09] announcements에 성공적으로 들어갔으니(같은 텍스트가
                # announcements.content에도 남음) 첨부 원문 캐시는 더 필요 없다.
                if raw_id is not None:
                    cur.execute(
                        "DELETE FROM bizinfo_attachment_text_cache WHERE raw_bizinfo_id = %s",
                        (raw_id,),
                    )
                    conn.commit()
            except Exception as e:
                conn.rollback()
                failed.append((raw_id, str(e)))

        if failed:
            print(f"upsert_announcements: {len(failed)}건 저장 실패(건너뜀, 다음 재실행 때 재시도됨):")
            for raw_id, err in failed[:10]:
                print(f"  raw_bizinfo_id={raw_id}: {err}")
            if len(failed) > 10:
                print(f"  ... 외 {len(failed) - 10}건")

        return n
    finally:
        conn.close()


# ==================================================================
# 실행
# ==================================================================

def run(
    only_unprocessed: bool = True,
    use_llm_fallback: bool = False,
    limit: int | None = None,
    offset: int | None = None,
):
    raw_df = load_raw_bizinfo_from_postgres(only_unprocessed=only_unprocessed, limit=limit, offset=offset)
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

    attachments_by_raw_id = dict(zip(raw_df["raw_bizinfo_id"], zip(raw_df["file_nm"], raw_df["flpth_nm"])))
    n = upsert_announcements(final_df, attachments_by_raw_id)
    print(f"UPSERT 완료: {n}건")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="테스트/분할 실행용: 이번 실행에서 처리할 최대 건수")
    parser.add_argument("--offset", type=int, default=None, help="--all과 같이 배치 나눠 돌릴 때 시작 위치")
    parser.add_argument(
        "--all",
        action="store_true",
        help="이미 announcements에 반영된 공고도 포함해 전부 다시 처리(재검증/로그 확인용). "
        "기본은 아직 반영 안 된 것만 처리",
    )
    args = parser.parse_args()
    run(only_unprocessed=not args.all, limit=args.limit, offset=args.offset)
