# 공고 매칭 리스트 조회 API.
# FilterPage(기업유형/지원분야/업력/연령) 4개 그룹 전부 쿼리 파라미터로 연동됨.

import os
import tempfile
from datetime import date

import requests
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import FileResponse

from backend.assistant.hwpx_fill import fill_hwpx_all
from backend.assistant.pipeline import _load_mapping
from backend.auth.session import get_current_user_id, get_optional_user_id
from backend.db.connection import get_connection

router = APIRouter(prefix="/api/matching", tags=["matching"])

DEFAULT_LIMIT = 20
MAPPING_XLSX = os.path.join("data", "field_mapping.xlsx")


def _format_dday(apply_end_date: date | None) -> str:
    if apply_end_date is None:
        return "상시모집"
    remaining = (apply_end_date - date.today()).days
    if remaining < 0:
        return "마감"
    return f"모집중 D-{remaining}"


SORT_OPTIONS = {
    # [2026-09-09 수정] 그냥 apply_end_date ASC만 하면 이미 지난 마감일이 날짜가
    # 빠르다는 이유로 맨 위로 옴("마감임박"인데 이미 마감된 게 1등) - 실측 확인.
    # 안 지난 것(false=0) 먼저, 그중 임박한 순, 그다음 지난 것(true=1) 순.
    # NULL(상시모집 등 마감일 없음)은 Postgres 기본 정렬 규칙상 ASC 맨 뒤로 감
    # - 두 정렬 기준 다 마찬가지라 결과적으로 맨 마지막.
    #
    # [2026-09-10 수정] 끝에 announcement_id를 2차 정렬로 추가함. collected_at은
    # 배치 크롤 시각이라 동점이 매우 흔하고(실측: 활성 공고 1,764건 중 distinct
    # collected_at이 5개뿐, 한 그룹이 1,417건), apply_end_date도 "상시모집"(NULL)
    # 922건이 전부 동점 - 정렬 기준에 동점이 있으면 Postgres가 쿼리마다 순서를
    # 다르게 줄 수 있어서, "더보기" 페이지네이션(LIMIT/OFFSET)이 같은 행을 다시
    # 보여주거나 건너뛰는 문제가 있었음. 유니크한 announcement_id를 마지막
    # 기준으로 추가해서 동점을 완전히 없애 순서를 고정한다.
    "deadline": "(apply_end_date < CURRENT_DATE) ASC, apply_end_date ASC, announcement_id DESC",
    "recent": "collected_at DESC, announcement_id DESC",
}


@router.get("")
def list_announcements(
    offset: int = 0,
    limit: int = DEFAULT_LIMIT,
    ksic: str = "",
    region: str = "",
    company: str = "",
    biz_age: str = "",
    field: str = "",
    age: str = "",
    sort: str = "recent",
) -> dict:
    """"더보기" 버튼 방식 페이지네이션. limit+1건을 조회해서, limit보다 많이
    돌아오면 다음 페이지가 더 있다는 뜻이므로 has_more=True로 알려준다.

    ksic: 콤마로 구분된 KSIC 코드 목록 (예: "C,01"). 넘기면 공고의
    ksic_codes_matched 배열과 하나라도 겹치는 것만 필터. [2026-09-09, 테스트용]
    지금은 업종 드롭다운에 전체 KSIC(1,200여개)가 아니라 실제로 매칭된 것 중
    자주 나오는 몇 개만 넣어서 필터링 자체가 되는지 확인하는 용도.

    region: 콤마로 구분된 시/도 목록 (예: "서울특별시,경기도"). 공고의 regions
    배열과 하나라도 겹치는 것만 필터. regions는 시/군 단위까지만 있고 구 단위는
    없음(extract_region.py 팀 결정 - 오탐 위험 때문에 의도적으로 제외).

    company: 콤마로 구분된 기업유형 목록 (예: "소상공인,중소기업"). target_summary가
    그중 하나와 정확히 일치하는 것만 필터. bizinfo만 값이 있음(kstartup의
    target_summary는 자유 문장이라 이 필터 대상이 아님 - FilterPage.tsx 옵션도
    bizinfo distinct 값 기준으로 만들어져 있음).

    biz_age: 업력 값 하나 (예: "예비창업자", "3년미만", "업력무관"). business_age_condition에
    이 값이 부분 문자열로 포함되면 매칭("=" 아님, "LIKE '%값%'") - kstartup 원본이
    "예비창업자~3년미만"처럼 두 조건을 붙여서 한 값으로 주는 경우가 있어서, "예비창업자"만
    선택해도 "예비창업자~3년미만" 같은 공고가 같이 잡히게 하려는 의도(docs/filter_options_
    review_2026-09-09.xlsx 참고). bizinfo는 이 컬럼 자체가 항상 NULL이라 대상이 아님.

    field: 콤마로 구분된 지원분야 목록 (예: "사업화,정책자금"). announcements.category에
    이 값들 중 하나라도 부분 문자열로 포함되면 매칭(ILIKE ANY). kstartup은 category가
    "사업화"처럼 깨끗한 단일 값이라 그대로 매칭되고, bizinfo는 "창업 > 사업화지원"처럼
    "대분류 > 중분류" 합친 문자열이라 부분 매칭으로 대분류만 선택해도 잡히게 한다
    (docs/filter_options_review_2026-09-09.xlsx "지원분야" 시트 참고).

    age: 사업대상연령 값 하나 (예: "만 40세 이상", "전연령"). announcements.target_age_groups
    (배열, kstartup만 값 있음)와 겹치면 매칭. 실제 distinct 값 그대로 씀(가공된 버킷 없음)
    - docs/filter_options_review_2026-09-09.xlsx "target_age_groups" 시트 참고.

    sort: "recent"(기본, 최근 등록순) 또는 "deadline"(마감임박순)."""
    ksic_codes = [c.strip() for c in ksic.split(",") if c.strip()]
    regions = [r.strip() for r in region.split(",") if r.strip()]
    companies = [c.strip() for c in company.split(",") if c.strip()]
    fields = [f.strip() for f in field.split(",") if f.strip()]
    biz_age = biz_age.strip()
    age = age.strip()
    order_sql = SORT_OPTIONS.get(sort, SORT_OPTIONS["recent"])

    # [2026-09-09] 이미 마감 지난 공고는 리스트에서 아예 뺀다. announcements 원본
    # 데이터는 안 지운다(raw/가공 원칙) - 여기 조회 조건에서만 제외. 마감일이
    # 없는(NULL, 상시모집 등) 공고는 계속 보여줌.
    conditions = ["(apply_end_date IS NULL OR apply_end_date >= CURRENT_DATE)"]
    params: list = []
    if ksic_codes:
        conditions.append("ksic_codes_matched && %s")
        params.append(ksic_codes)
    if regions:
        conditions.append("regions && %s")
        params.append(regions)
    if companies:
        conditions.append("target_summary = ANY(%s)")
        params.append(companies)
    if biz_age:
        conditions.append("business_age_condition LIKE %s")
        params.append(f"%{biz_age}%")
    if fields:
        conditions.append("category ILIKE ANY(%s)")
        params.append([f"%{f}%" for f in fields])
    if age:
        conditions.append("target_age_groups && %s")
        params.append([age])
    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM announcements {where_sql}", params)
        total = cur.fetchone()[0]
        cur.execute(
            f"""
            SELECT a.announcement_id, a.host_org_name, a.title, a.apply_end_date,
                   EXISTS (
                       SELECT 1 FROM announcement_attachments att
                       WHERE att.announcement_id = a.announcement_id
                         AND att.fillable_field_count > 0
                   ) AS fillable
            FROM announcements a
            {where_sql}
            ORDER BY {order_sql}
            LIMIT %s OFFSET %s
            """,
            [*params, limit + 1, offset],
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    has_more = len(rows) > limit
    rows = rows[:limit]

    data = [
        {
            "id": str(announcement_id),
            "agency": host_org_name or "기관명 미기재",
            "dday": _format_dday(apply_end_date),
            "title": title,
            # [2026-09-09] 해시태그 로직은 사용자가 직접 확인 중 - 우선 빈 배열로 둔다.
            "tags": [],
            "fillable": bool(fillable),
        }
        for announcement_id, host_org_name, title, apply_end_date, fillable in rows
    ]
    return {"success": True, "data": data, "has_more": has_more, "total": total}


def _format_period(apply_start_date: date | None, apply_end_date: date | None) -> str:
    if apply_start_date and apply_end_date:
        return f"{apply_start_date:%m.%d} ~ {apply_end_date:%m.%d} 접수"
    if apply_end_date:
        return f"~{apply_end_date:%m.%d} 접수"
    return "상시모집"


def _format_dday_short(apply_end_date: date | None) -> str:
    if apply_end_date is None:
        return "상시모집"
    remaining = (apply_end_date - date.today()).days
    return "마감" if remaining < 0 else f"D-{remaining}"


def _fetch_docs(announcement_id: int, conn) -> list[dict]:
    """신청서류 목록. announcement_attachments는 지금 bizinfo 공고만 채워져 있음
    (kstartup 원본엔 첨부파일 정보 자체가 없어서 자연히 빈 리스트가 나옴).
    fillable: fillable_field_count > 0 (NULL/-1/0은 전부 False - 미확인·실패·매칭없음
    을 굳이 구분해서 보여줄 필요는 없고, 화면엔 "채울 수 있다/없다"만 필요).
    downloadUrl: 채우기 여부와 무관하게 원본 그대로 받아서 직접 작성할 수 있도록."""
    cur = conn.cursor()
    cur.execute(
        "SELECT attachment_id, file_name, source_url, fillable_field_count FROM announcement_attachments "
        "WHERE announcement_id = %s ORDER BY attachment_id",
        (announcement_id,),
    )
    return [
        {
            "attachmentId": attachment_id,
            "fileName": file_name,
            "fillable": bool(fillable_field_count and fillable_field_count > 0),
            "downloadUrl": source_url,
        }
        for attachment_id, file_name, source_url, fillable_field_count in cur.fetchall()
    ]


def _build_biz_cert_from_db(conn):
    """[2026-09-09, 임시] 로그인 세션이 아직 없어서 "누구의 사업자등록증으로
    채울지"를 알 방법이 없다 - DB에 등록된 것 중 가장 먼저 저장된 1건(지금은
    유일하게 있는 profile_id=15, 명현정공)을 채우기 기능 자체가 동작하는지
    확인하는 용도로 쓴다. 로그인이 붙으면 여기를 "현재 로그인한 사용자의
    profile_id" 기준 조회로 바꿔야 한다.

    반환: (biz_cert dict, entity_type) 또는 등록된 사업자등록증이 없으면 None.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT profile_id, entity_type_code, biz_no, corp_no, company_name, ceo_name,
               open_date, birth_date, business_address, head_address
        FROM biz_registration_docs ORDER BY document_id LIMIT 1
        """
    )
    row = cur.fetchone()
    if row is None:
        return None

    (profile_id, entity_type_code, biz_no, corp_no, company_name, ceo_name,
     open_date, birth_date, business_address, head_address) = row

    cur.execute(
        "SELECT business_category, business_item FROM profile_business_types "
        "WHERE profile_id = %s ORDER BY is_primary DESC LIMIT 1",
        (profile_id,),
    )
    cat_row = cur.fetchone()
    biz_type, biz_item = cat_row if cat_row else (None, None)

    entity_type = "법인" if entity_type_code == "corporate" else "개인"
    biz_cert = {
        "trade_name": company_name if entity_type == "개인" else "",
        "corp_name": company_name if entity_type == "법인" else "",
        "ceo_name": ceo_name or "",
        "biz_no": biz_no or "",
        "corp_no": corp_no or "",
        "birth_date": str(birth_date) if birth_date else "",
        "open_date": str(open_date) if open_date else "",
        "address_basic": (head_address or business_address) if entity_type == "법인" else (business_address or ""),
        "biz_type": biz_type or "",
        "biz_item": biz_item or "",
    }
    return biz_cert, entity_type


@router.get("/attachments/{attachment_id}/fill")
def fill_attachment(attachment_id: int, background_tasks: BackgroundTasks):
    """신청서류 원본을 받아서 사업자등록증 정보로 채운 결과를 파일로 돌려준다.
    [임시] 로그인 연결 전까지는 DB에 등록된 사업자등록증 1건으로 채운다
    (_build_biz_cert_from_db 참고) - 기능 자체가 동작하는지 확인하는 용도."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT file_name, source_url, fillable_field_count FROM announcement_attachments "
            "WHERE attachment_id = %s",
            (attachment_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"success": False, "error": {"message": "첨부파일을 찾을 수 없습니다.", "code": "NOT_FOUND"}}
        file_name, source_url, fillable_field_count = row
        if not fillable_field_count or fillable_field_count <= 0:
            return {
                "success": False,
                "error": {"message": "이 서류는 자동채우기를 지원하지 않습니다.", "code": "NOT_FILLABLE"},
            }

        built = _build_biz_cert_from_db(conn)
        if built is None:
            return {
                "success": False,
                "error": {"message": "등록된 사업자등록증 정보가 없습니다.", "code": "NO_BIZ_CERT"},
            }
        biz_cert, entity_type = built
    finally:
        conn.close()

    resp = requests.get(source_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()

    fd, tmp_in = tempfile.mkstemp(suffix=".hwpx")
    os.close(fd)
    fd, tmp_out = tempfile.mkstemp(suffix=".hwpx")
    os.close(fd)
    try:
        with open(tmp_in, "wb") as f:
            f.write(resp.content)
        rules = _load_mapping(MAPPING_XLSX)
        fill_hwpx_all(tmp_in, tmp_out, rules, biz_cert, entity_type, models=None)
    finally:
        os.remove(tmp_in)

    background_tasks.add_task(os.remove, tmp_out)
    out_name = os.path.splitext(file_name)[0] + "_채움.hwpx"
    return FileResponse(tmp_out, filename=out_name, background=background_tasks)


@router.get("/{announcement_id}")
def get_announcement_detail(
    announcement_id: int, user_id: int | None = Depends(get_optional_user_id)
) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.title, a.content, a.host_org_name, a.supervising_org, a.target_summary,
                   a.apply_method, a.contact, a.apply_start_date, a.apply_end_date,
                   a.detail_page_url, b.hashtags
            FROM announcements a
            LEFT JOIN announcements_raw_bizinfo b ON b.raw_bizinfo_id = a.raw_bizinfo_id
            WHERE a.announcement_id = %s
            """,
            (announcement_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"success": False, "error": {"message": "공고를 찾을 수 없습니다.", "code": "NOT_FOUND"}}

        (title, content, host_org_name, supervising_org, target_summary,
         apply_method, contact, apply_start_date, apply_end_date,
         detail_page_url, raw_hashtags) = row

        # 해시태그는 기업마당(bizinfo) 원본에만 있는 필드 (K-Startup 원본엔 없음).
        # 원본은 "경영,전남광주,홍보시책" 처럼 콤마로만 구분돼있어 "#" 붙여서 공백으로 이어붙인다.
        hashtags = " ".join(f"#{t.strip()}" for t in (raw_hashtags or "").split(",") if t.strip())

        docs = _fetch_docs(announcement_id, conn)

        bookmarked = False
        if user_id is not None:
            cur.execute(
                "SELECT 1 FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
                (user_id, announcement_id),
            )
            bookmarked = cur.fetchone() is not None
    finally:
        conn.close()

    agency = " · ".join(p for p in [host_org_name, supervising_org] if p) or "정보 없음"

    return {
        "success": True,
        "data": {
            "id": str(announcement_id),
            "period": _format_period(apply_start_date, apply_end_date),
            "dday": _format_dday_short(apply_end_date),
            "title": title,
            "hashtags": hashtags,
            "bookmarked": bookmarked,
            # [2026-09-09] 사용자 프로필(지역/업종) 연결 전까지는 진짜 개인화된 코멘트를
            # 만들 수 없다 - 근거 없는 맞춤 문구를 지어내지 않고 안내 문구로 대신한다.
            "aiComment": "맞춤 코멘트는 준비 중입니다.",
            "overview": [
                {"label": "소관기관 · 수행기관", "value": agency},
                {"label": "지원 대상", "value": target_summary or "정보 없음"},
                {"label": "신청 방법", "value": apply_method or "정보 없음"},
                {"label": "문의처", "value": contact or "정보 없음"},
            ],
            "content": content or "",
            "docs": docs,
            "homepageUrl": detail_page_url,
        },
    }


@router.post("/{announcement_id}/bookmark")
def add_bookmark(announcement_id: int, user_id: int = Depends(get_current_user_id)) -> dict:
    """찜하기. bookmarks에 (user_id, announcement_id) 유니크 제약이 없어서 INSERT 전에
    직접 존재 여부를 확인한다 - 중복 클릭해도 행이 여러 개 쌓이지 않게."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
            (user_id, announcement_id),
        )
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO bookmarks (user_id, announcement_id, bookmarked_at) VALUES (%s, %s, now())",
                (user_id, announcement_id),
            )
            conn.commit()
    finally:
        conn.close()
    return {"success": True, "data": {"bookmarked": True}}


@router.delete("/{announcement_id}/bookmark")
def remove_bookmark(announcement_id: int, user_id: int = Depends(get_current_user_id)) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM bookmarks WHERE user_id = %s AND announcement_id = %s",
            (user_id, announcement_id),
        )
        conn.commit()
    finally:
        conn.close()
    return {"success": True, "data": {"bookmarked": False}}
