# backend/preprocessing/sync_kstartup_announcements.py
#
# announcements_raw_kstartup -> announcements. sync_bizinfo_announcements.py와
# 완전히 같은 구조(9단계 staging)다 - 다른 건 소스별 필드명과 아래 2가지뿐:
#
#   1) 지역: extract_region() 대신 normalize_kstartup_region() 사용
#      (backend/preprocessing/extract_region.py에 이미 있음 - 새로 안 만듦)
#   2) 업종: decide_industry()를 아예 호출하지 않는다. 2026-09-04 팀 결정
#      (253건 재검증 결과 매칭 시도해도 대부분 기관명 우연 충돌이라 신뢰
#      불가) 그대로 "업종무관(기본값)"으로 고정 - backend/preprocessing/
#      pipeline.py::process_kstartup_notice()가 이미 이렇게 함.
#
# [정제 로직 출처] "모집중만 유지 / 신청대상 텍스트 병합 / 업력·연령 단일화"
# 로직은 2026-09-07에 사용자가 별도로 검증해온 15_clean_kstartup_raw_v2.py
# 를 그대로 포팅했다(다시 설계 안 함) - merge_apply_target/collapse_business_age/
# extract_age_from_target 등 함수명·동작 동일.
#
# [필드 매핑 기준] ERD(0904_DB업로드) + final_project/transform_kstartup.py의
# 기존 결정을 그대로 따름: host_org_name<-pbanc_ntrp_nm, supervising_org<-
# sprv_inst, contact<-biz_prch_dprt_nm, category<-supt_biz_clsfc.
#
# [알려진 한계]
#   1) announcements_raw_kstartup 실제 raw 데이터가 지금 없다 - 먼저
#      backend/crawler/kstartup_seed_loader.py로 1회 적재해야 이 파일이
#      읽을 대상이 생긴다.
#   2) target_age_groups는 ERD가 TEXT[] 배열이라, v2가 만드는 단일 문자열
#      ("전연령" 등)을 1개짜리 배열로 감싼다(사용자 확인, 2026-09-07).
#   3) schema.sql에 announcements_raw_kstartup/announcements 정의가 없다 -
#      sync_bizinfo_announcements.py와 같은 문제, 여기서도 안 고침.

import html
import math
import re
from datetime import date, datetime

import pandas as pd

from backend.db.connection import get_connection
from backend.preprocessing.extract_region import normalize_kstartup_region

SNAPSHOT_DATE = date.today()

LONG_TEXT_FIELDS = {"aply_excl_trgt_ctnt", "aply_trgt_ctnt", "pbanc_ctnt", "aply_mthd_etc_istc"}

TARGET_REFERENCE_PATTERNS = [
    r"^\s*[-–—]\s*$",
    r"^\s*(없음|해당없음|해당 없음|미기재)\s*$",
    r"^\s*(전체|제한없음|제한 없음)\s*$",
    r"^\s*(각\s*)?(지원사업\s*)?(모집\s*)?공고문\s*(참고|참조)\s*$",
    r"^\s*(상세\s*)?(내용\s*)?공고문\s*(참고|참조)\s*$",
]


# ==================================================================
# 0. RAW 조회
# ==================================================================

def load_raw_kstartup_from_postgres(only_unprocessed: bool = False, limit: int | None = None) -> pd.DataFrame:
    """limit: 소량만 먼저 확인하거나 여러 번에 나눠 돌릴 때 씀 (sync_bizinfo_announcements.py와 동일 이유)."""
    conn = get_connection()
    try:
        if only_unprocessed:
            query = """
                SELECT r.* FROM announcements_raw_kstartup r
                LEFT JOIN announcements a
                  ON a.source = 'kstartup' AND a.raw_kstartup_id = r.raw_kstartup_id
                WHERE a.raw_kstartup_id IS NULL
                ORDER BY r.raw_kstartup_id
            """
        else:
            query = "SELECT * FROM announcements_raw_kstartup ORDER BY raw_kstartup_id"
        if limit:
            query += f" LIMIT {int(limit)}"
        return pd.read_sql(query, conn)
    finally:
        conn.close()


# ==================================================================
# 1. 기본 전처리 (15_clean_kstartup_raw_v2.py 포팅, 로직 동일)
# ==================================================================

def _is_blank(v):
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def _normalize_text(v, preserve_newlines=False):
    if _is_blank(v):
        return None
    text = html.unescape(str(v))
    text = text.replace("_x000D_", "")
    text = text.replace("\xa0", " ")
    text = text.replace("​", "")
    text = text.replace("﻿", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if preserve_newlines:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        text = "\n".join(lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _parse_date(v):
    if _is_blank(v):
        return None
    s = str(v).strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _format_date(v):
    d = _parse_date(v)
    return d.isoformat() if d else None


def _target_content_is_meaningful(text):
    t = _normalize_text(text) or ""
    if not t:
        return False
    for pattern in TARGET_REFERENCE_PATTERNS:
        if re.fullmatch(pattern, t, flags=re.I):
            return False
    if len(t) <= 30 and re.search(r"공고문.*(?:참고|참조)", t):
        return False
    return True


def _merge_apply_target(aply_trgt, aply_trgt_ctnt):
    detailed = _normalize_text(aply_trgt_ctnt, preserve_newlines=True)
    coarse = _normalize_text(aply_trgt)
    if detailed and _target_content_is_meaningful(detailed):
        return detailed
    return coarse


def _extract_age_from_target(target_text):
    t = _normalize_text(target_text) or ""
    if not t:
        return None
    m = re.search(
        r"(?:만\s*)?(\d{1,2})\s*세?\s*(?:이상\s*)?[~∼\-–]\s*(?:만\s*)?(\d{1,2})\s*세\s*(?:이하)?", t
    )
    if m:
        lo, hi = map(int, m.groups())
        if lo <= hi and 0 <= lo <= 99 and 0 <= hi <= 99:
            return f"만 {lo}세~{hi}세"
    lows = [int(x) for x in re.findall(r"(?:만\s*)?(\d{1,2})\s*세\s*이상", t)]
    highs = [int(x) for x in re.findall(r"(?:만\s*)?(\d{1,2})\s*세\s*이하", t)]
    lows = [x for x in lows if 0 <= x <= 99]
    highs = [x for x in highs if 0 <= x <= 99]
    if lows and highs:
        lo, hi = min(lows), max(highs)
        if lo <= hi:
            return f"만 {lo}세~{hi}세"
    if lows:
        return f"만 {min(lows)}세 이상"
    if highs:
        return f"만 {max(highs)}세 이하"
    return None


def _collapse_structured_age(raw_age):
    t = _normalize_text(raw_age) or ""
    if not t:
        return "전연령"
    tokens = [x.strip() for x in t.split(",") if x.strip()]
    s = set(tokens)
    u20, y20_39, a40 = "만 20세 미만", "만 20세 이상 ~ 만 39세 이하", "만 40세 이상"
    if {u20, y20_39, a40}.issubset(s):
        return "전연령"
    if {y20_39, a40}.issubset(s) and u20 not in s:
        return "만 20세 이상"
    if {u20, y20_39}.issubset(s) and a40 not in s:
        return "만 39세 이하"
    if s == {y20_39}:
        return y20_39
    if s == {u20}:
        return u20
    if s == {a40}:
        return a40
    if len(tokens) == 1:
        return tokens[0]
    return " 또는 ".join(tokens)


def _extract_business_age_from_target(target_text):
    t = _normalize_text(target_text) or ""
    if not t:
        return None
    if re.search(r"업력\s*무관|업력\s*제한\s*(?:없음|없)|업력제한\s*(?:없음|없)", t):
        return {"unrestricted": True, "pre": "예비창업" in t, "years": None}
    pre = bool(re.search(r"예비\s*창업|예비창업", t))
    years = []
    for pat in [
        r"(?:창업(?:\s*후)?|업력|기창업자?|창업기업|설립)\D{0,12}?(\d{1,2})\s*년\s*(?:이내|미만)",
        r"(\d{1,2})\s*년\s*(?:이내|미만)\s*(?:기창업자|창업자|기업)",
    ]:
        for x in re.findall(pat, t):
            y = int(x)
            if 0 < y <= 30:
                years.append(y)
    months = []
    for x in re.findall(r"(\d{1,2})\s*개월\s*미만", t):
        m = int(x)
        if 0 < m <= 120:
            months.append(m)
    years.extend([max(1, math.ceil(m / 12)) for m in months])
    if years or pre:
        return {"unrestricted": False, "pre": pre, "years": max(years) if years else None}
    return None


def _collapse_business_age(raw_enyy, target_text):
    x = _extract_business_age_from_target(target_text)
    if x:
        if x["unrestricted"]:
            return "업력무관"
        if x["pre"] and x["years"]:
            return f"예비창업자~{x['years']}년미만"
        if x["pre"]:
            return "예비창업자"
        if x["years"]:
            return f"{x['years']}년미만"
    t = _normalize_text(raw_enyy) or ""
    if not t:
        return "업력무관"
    tokens = [x.strip() for x in t.split(",") if x.strip()]
    pre = "예비창업자" in tokens
    nums = [int(m.group(1)) for tok in tokens if (m := re.fullmatch(r"(\d{1,2})년미만", tok))]
    if nums:
        y = max(nums)
        return f"예비창업자~{y}년미만" if pre else f"{y}년미만"
    if pre:
        return "예비창업자"
    return "업력무관"


TEXT_FIELDS = [
    "biz_pbanc_nm", "pbanc_ntrp_nm", "sprv_inst", "biz_prch_dprt_nm",
    "supt_biz_clsfc", "supt_regin", "aply_trgt", "aply_trgt_ctnt",
    "aply_excl_trgt_ctnt", "biz_trgt_age", "biz_enyy",
]


def clean_kstartup(raw_df: pd.DataFrame) -> pd.DataFrame:
    """모집중(rcrt_prgs_yn='Y')이고 마감일이 기준일 이후인 것만 유지 - 마감된
    공고는 애초에 announcements에 안 올린다(15_clean_kstartup_raw_v2.py와
    동일 원칙, final_project의 '마감공고제외' 관행과도 일치)."""
    df = raw_df.copy()

    active_mask = df["rcrt_prgs_yn"].apply(lambda v: (_normalize_text(v) or "").upper() == "Y")
    end_dates = df["pbanc_rcpt_end_dt"].apply(_parse_date)
    not_expired = end_dates.apply(lambda d: d is None or d >= SNAPSHOT_DATE)
    df = df[active_mask & not_expired].copy()

    if df["pbanc_sn"].duplicated().any():
        df = df.drop_duplicates(subset="pbanc_sn", keep="last")

    for col in TEXT_FIELDS:
        if col in df.columns:
            preserve = col in LONG_TEXT_FIELDS
            df[col] = df[col].apply(lambda v, p=preserve: _normalize_text(v, preserve_newlines=p))
    if "pbanc_ctnt" in df.columns:
        df["pbanc_ctnt"] = df["pbanc_ctnt"].apply(lambda v: _normalize_text(v, preserve_newlines=True))

    df["pbanc_rcpt_bgng_dt"] = df["pbanc_rcpt_bgng_dt"].apply(_format_date)
    df["pbanc_rcpt_end_dt"] = df["pbanc_rcpt_end_dt"].apply(_format_date)

    merged_target = [
        _merge_apply_target(r.get("aply_trgt"), r.get("aply_trgt_ctnt")) for _, r in df.iterrows()
    ]
    df["_merged_target"] = merged_target
    df["biz_enyy"] = [
        _collapse_business_age(r.get("biz_enyy"), t) for (_, r), t in zip(df.iterrows(), merged_target)
    ]
    df["biz_trgt_age"] = [
        _extract_age_from_target(t) or _collapse_structured_age(r.get("biz_trgt_age"))
        for (_, r), t in zip(df.iterrows(), merged_target)
    ]

    return df


# ==================================================================
# 2~3. 공통 필드 변환 (ERD + final_project/transform_kstartup.py 기존 결정)
# ==================================================================

_METHOD_LABELS = [
    ("aply_mthd_eml_rcpt_istc", "이메일"), ("aply_mthd_fax_rcpt_istc", "팩스"),
    ("aply_mthd_vst_rcpt_istc", "방문"), ("aply_mthd_onli_rcpt_istc", "온라인"),
    ("aply_mthd_pssr_rcpt_istc", "우편"), ("aply_mthd_etc_istc", "기타"),
]


def _build_apply_method(r):
    parts = [str(r[c]).strip() for c, _ in _METHOD_LABELS if c in r and not _is_blank(r[c])]
    return "\n".join(parts) or None


def transform_kstartup_to_common(clean_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in clean_df.iterrows():
        rows.append({
            "source": "kstartup",
            "raw_bizinfo_id": None,
            "raw_kstartup_id": r.get("raw_kstartup_id"),
            "_pbanc_sn": r.get("pbanc_sn"),
            "_supt_regin": r.get("supt_regin"),

            "title": r.get("biz_pbanc_nm"),
            "content": r.get("pbanc_ctnt"),

            "host_org_name": r.get("pbanc_ntrp_nm"),
            "supervising_org": r.get("sprv_inst"),
            "contact": r.get("biz_prch_dprt_nm"),

            "category": r.get("supt_biz_clsfc"),
            "target_summary": r.get("_merged_target"),
            "business_age_condition": r.get("biz_enyy"),
            "_biz_trgt_age_single": r.get("biz_trgt_age"),

            "apply_start_date": r.get("pbanc_rcpt_bgng_dt"),
            "apply_end_date": r.get("pbanc_rcpt_end_dt"),
            "apply_method": _build_apply_method(r),
            "detail_page_url": r.get("detl_pg_url"),

            "management_no": r.get("prch_cnpl_no"),

            "collected_at": r.get("collected_at"),
            # announcements.updated_at은 NOT NULL. K-Startup raw엔 갱신시각
            # 필드가 없으므로 수집 시각(collected_at)으로 채운다.
            "updated_at": r.get("collected_at"),
        })
    return pd.DataFrame(rows)


def parse_target_conditions(common_df: pd.DataFrame) -> pd.DataFrame:
    """target_age_groups: ERD가 TEXT[]라서 단일 문자열을 1개짜리 배열로
    감싼다(사용자 확인, 2026-09-07). business_age_condition은 이미
    clean_kstartup()에서 계산됨."""
    df = common_df.copy()
    df["target_age_groups"] = df["_biz_trgt_age_single"].apply(lambda v: [v] if v else [])
    return df


def normalize_support_fields(common_df: pd.DataFrame) -> pd.DataFrame:
    """category는 supt_biz_clsfc 원본값을 그대로 씀(팀 기존 결정) - 지금은
    통과만, 나중 세분화 자리로 남김."""
    return common_df


# ==================================================================
# 4. 지역 매핑 (기존 normalize_kstartup_region() 재사용 - 새로 안 만듦)
# ==================================================================

def map_regions(common_df: pd.DataFrame) -> pd.DataFrame:
    df = common_df.copy()
    regions_col, status_col, needs_review_col = [], [], []
    for _, r in df.iterrows():
        result = normalize_kstartup_region(r.get("_supt_regin") or "")
        status = result.get("status", "")
        regions_col.append(result.get("regions") or [])
        status_col.append(status)
        needs_review_col.append(status.startswith("inferred_") or status == "unparsed")
    df["regions"] = regions_col
    df["region_status"] = status_col
    df["region_needs_review"] = needs_review_col
    return df


# ==================================================================
# 5. KSIC 매핑 - 2026-09-04 팀 결정대로 시도 자체를 안 함
# ==================================================================

def map_ksic(common_df: pd.DataFrame) -> pd.DataFrame:
    """K-Startup은 253건 재검증 결과 기관명 우연 충돌이 대부분이라 매칭을
    아예 시도하지 않기로 함(2026-09-04, backend/preprocessing/pipeline.py::
    process_kstartup_notice()와 동일 정책). decide_industry() 호출 안 함."""
    df = common_df.copy()
    df["ksic_codes_matched"] = [[] for _ in range(len(df))]
    df["ksic_names_matched"] = [[] for _ in range(len(df))]
    df["ksic_codes_excluded"] = [[] for _ in range(len(df))]
    df["ksic_status"] = "업종무관(기본값)"
    return df


# ==================================================================
# 6. 최종 검증
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
    df = common_df.copy()
    problems = []
    for idx, r in df.iterrows():
        errs = []
        if not r.get("source"):
            errs.append("source 없음")
        if r.get("source") == "kstartup" and not r.get("raw_kstartup_id"):
            errs.append("raw_kstartup_id 없음")
        if not r.get("title"):
            errs.append("title 없음")
        if not isinstance(r.get("regions"), list):
            errs.append("regions가 배열 타입이 아님")
        if not isinstance(r.get("target_age_groups"), list):
            errs.append("target_age_groups가 배열 타입이 아님")
        if r.get("apply_start_date") and r.get("apply_end_date"):
            if str(r["apply_start_date"]) > str(r["apply_end_date"]):
                errs.append("apply_start_date가 apply_end_date보다 늦음")
        if errs:
            problems.append({"row_index": idx, "raw_kstartup_id": r.get("raw_kstartup_id"), "errors": errs})

    dup = df[df["source"] == "kstartup"]["raw_kstartup_id"].duplicated()
    if dup.any():
        for idx in df.index[dup]:
            problems.append({"row_index": idx, "raw_kstartup_id": df.loc[idx, "raw_kstartup_id"],
                              "errors": ["같은 raw_kstartup_id가 이 배치 안에서 중복"]})

    bad_idx = {p["row_index"] for p in problems}
    final_df = df.drop(index=list(bad_idx))[FINAL_COLUMNS].reset_index(drop=True)
    review_df = pd.DataFrame(problems)
    return final_df, review_df


# ==================================================================
# 7. UPSERT (raw_kstartup_id 기준)
# ==================================================================
#
# [2026-09-08] sync_bizinfo_announcements.py에서 발견된 NUL(0x00) 버그와
# 동일한 패턴이라 같이 고쳤음. kstartup은 API 텍스트(pbanc_ctnt 등)라 지금까지
# NUL이 안 걸렸을 뿐, 언젠가 걸릴 수 있어 예방 차원 — bizinfo 쪽 원인 상세는
# 그 파일 upsert_announcements() 위 주석 참고.
# 같은 이유로 배치 전체 commit()도 1건씩 commit()하도록 바꿨음(일관성 + 실패
# 내성) — kstartup은 무거운 첨부 추출이 없어서 재실행 비용 문제는 원래 없었지만,
# 한 행 실패가 나머지 전체를 롤백시키는 구조 자체는 동일했음.

ARRAY_COLUMNS = {"regions", "target_age_groups", "ksic_codes_matched", "ksic_names_matched", "ksic_codes_excluded"}
INSERT_COLUMNS = FINAL_COLUMNS


def _strip_nul(v):
    """PostgreSQL text 컬럼은 NUL(0x00)을 저장 못 함. 저장 직전에 제거."""
    if isinstance(v, str):
        return v.replace("\x00", "")
    if isinstance(v, list):
        return [x.replace("\x00", "") if isinstance(x, str) else x for x in v]
    return v


def upsert_announcements(final_df: pd.DataFrame) -> int:
    if final_df.empty:
        return 0
    conn = get_connection()
    try:
        cur = conn.cursor()
        columns_sql = ", ".join(INSERT_COLUMNS)
        placeholders = ", ".join(["%s"] * len(INSERT_COLUMNS))
        update_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in INSERT_COLUMNS if c != "raw_kstartup_id")
        sql = f"""
            INSERT INTO announcements ({columns_sql})
            VALUES ({placeholders})
            ON CONFLICT (raw_kstartup_id) WHERE source = 'kstartup'
            DO UPDATE SET {update_sql}
        """
        n = 0
        failed = []
        for _, r in final_df.iterrows():
            values = [_strip_nul(list(r[c]) if c in ARRAY_COLUMNS else r[c]) for c in INSERT_COLUMNS]
            try:
                cur.execute(sql, values)
                conn.commit()
                n += 1
            except Exception as e:
                conn.rollback()
                failed.append((r.get("raw_kstartup_id"), str(e)))

        if failed:
            print(f"upsert_announcements: {len(failed)}건 저장 실패(건너뜀, 다음 재실행 때 재시도됨):")
            for raw_id, err in failed[:10]:
                print(f"  raw_kstartup_id={raw_id}: {err}")
            if len(failed) > 10:
                print(f"  ... 외 {len(failed) - 10}건")

        return n
    finally:
        conn.close()


# ==================================================================
# 실행
# ==================================================================

def run(only_unprocessed: bool = True, limit: int | None = None):
    raw_df = load_raw_kstartup_from_postgres(only_unprocessed=only_unprocessed, limit=limit)
    print(f"RAW 조회: {len(raw_df)}건")
    if raw_df.empty:
        return

    clean_df = clean_kstartup(raw_df)
    print(f"모집중 필터 후: {len(clean_df)}건")
    if clean_df.empty:
        # [2026-09-08 버그 수정] 전부 필터링돼서 0건이면 pd.DataFrame([])가
        # 컬럼 없는 빈 DataFrame이 되어 이후 단계(parse_target_conditions 등)에서
        # KeyError('_biz_trgt_age_single')로 죽었음 - 실측 확인(raw 21건 전부
        # 마감이라 여기서 0건 됨). raw_df.empty와 동일하게 여기서도 조기 종료.
        return
    common_df = transform_kstartup_to_common(clean_df)
    common_df = parse_target_conditions(common_df)
    common_df = normalize_support_fields(common_df)
    common_df = map_regions(common_df)
    common_df = map_ksic(common_df)
    final_df, review_df = validate_announcements(common_df)

    print(f"검증 통과: {len(final_df)}건 / 검토 대상: {len(review_df)}건")
    if not review_df.empty:
        print(review_df.to_string())

    n = upsert_announcements(final_df)
    print(f"UPSERT 완료: {n}건")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="테스트/분할 실행용: 이번 실행에서 처리할 최대 건수")
    args = parser.parse_args()
    run(limit=args.limit)
