# 공고 매칭 리스트 조회 API.
# 지금은 필터 없이 전체 목록만 반환한다 - FilterPage(기업유형/지원분야/업력/연령)
# 연동은 이 API가 먼저 자리잡은 뒤 쿼리 파라미터로 이어붙일 예정.

import os
import tempfile
from datetime import date

import requests
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from backend.assistant.hwpx_fill import fill_hwpx_all
from backend.assistant.pipeline import _load_mapping
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


@router.get("")
def list_announcements(offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict:
    """"더보기" 버튼 방식 페이지네이션. limit+1건을 조회해서, limit보다 많이
    돌아오면 다음 페이지가 더 있다는 뜻이므로 has_more=True로 알려준다."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM announcements")
        total = cur.fetchone()[0]
        cur.execute(
            """
            SELECT announcement_id, host_org_name, title, apply_end_date
            FROM announcements
            ORDER BY collected_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit + 1, offset),
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
        }
        for announcement_id, host_org_name, title, apply_end_date in rows
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
def get_announcement_detail(announcement_id: int) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT title, content, host_org_name, supervising_org, target_summary,
                   apply_method, contact, apply_start_date, apply_end_date,
                   detail_page_url
            FROM announcements WHERE announcement_id = %s
            """,
            (announcement_id,),
        )
        row = cur.fetchone()
        if row is None:
            return {"success": False, "error": {"message": "공고를 찾을 수 없습니다.", "code": "NOT_FOUND"}}

        (title, content, host_org_name, supervising_org, target_summary,
         apply_method, contact, apply_start_date, apply_end_date,
         detail_page_url) = row

        docs = _fetch_docs(announcement_id, conn)
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
            # [2026-09-09] 해시태그 로직은 사용자가 직접 확인 중 - 우선 빈 문자열.
            "hashtags": "",
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
