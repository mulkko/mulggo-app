# 마이페이지 - 프로필 요약/수정 API.
#
# [2026-09-09] 로그인 시 user_id를 프론트에 저장하는 세션 처리가 아직 없어서
# (LoginForm.tsx가 로그인 성공해도 user_id를 버림 - 별도로 고쳐야 함), 지금은
# user_id를 쿼리 파라미터로 직접 받는다. 로그인 세션이 붙으면 이 파라미터를
# 그 세션에서 채우도록 프론트만 바꾸면 되고, 이 API 자체는 안 바뀐다.
#
# business_profiles만 연동한다 - apply_status/idea_refinement_sessions는 실제 DB에
# 0건이라(연동해도 항상 빈 목록) 지금 범위에서 제외함(사용자 확인, 2026-09-09).
# [2026-09-10] bookmarks(찜하기), fill-history(채우기 이용내역)는 연동함 - 다른 프로필
# API와 달리 user_id를 쿼리 파라미터가 아니라 로그인 세션(Depends(get_current_user_id))
# 으로 받는다. 찜하기 토글/채우기(POST .../bookmark, GET .../fill)가 backend/api/
# matching.py에 이미 세션 기준으로 만들어져 있어서 같은 기능끼리는 인증 방식을 맞추는
# 게 맞다고 판단(다른 프로필 API는 세션 연동 전에 만들어진 것들이라 그대로 둠).

import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.api.auth import _validate_biz_cert_file
from backend.api.matching import _format_dday
from backend.auth.session import get_current_user_id
from backend.auth.signup import save_biz_cert_data
from backend.db.connection import get_connection

router = APIRouter(prefix="/api/mypage", tags=["mypage"])


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


@router.get("/profile")
def get_profile(user_id: int) -> JSONResponse:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT u.name, u.email, bp.profile_id, bp.profile_type, bp.entity_type_code, et.name,
                   bp.business_name, bp.industry_text, bp.region, bp.business_age_months,
                   bp.annual_revenue, bp.employee_count, bp.founder_age_group,
                   bp.profile_attributes->>'company_size' AS company_size,
                   EXISTS (
                       SELECT 1 FROM biz_registration_docs d
                       WHERE d.profile_id = bp.profile_id
                   ) AS has_biz_cert
            FROM users u
            LEFT JOIN business_profiles bp ON bp.user_id = u.user_id
            LEFT JOIN entity_types et ON et.code = bp.entity_type_code
            WHERE u.user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        if row is None:
            return _error(404, f"user_id={user_id} 회원을 찾을 수 없습니다.", "USER_NOT_FOUND")

        (name, email, profile_id, profile_type, entity_type_code, entity_type_name, business_name,
         industry_text, region, business_age_months, annual_revenue, employee_count,
         founder_age_group, company_size, has_biz_cert) = row

        # 사업자등록증 등록 시 검색/확정한 업종코드(KSIC) - business_profiles.industry_text와는
        # 별개 테이블(profile_business_types)이라 따로 조회. 여러 번 재등록했으면 가장 최근
        # 것(business_type_id 최댓값)을 쓴다 - is_primary는 재등록 시 갱신 안 되는 문제가
        # 있어(2026-09-11 확인) 믿을 수 없음.
        ksic_code = ksic_name = None
        if profile_id is not None:
            cur.execute(
                """
                SELECT pbt.ksic_code, kc.name
                FROM profile_business_types pbt
                LEFT JOIN ksic_codes kc ON kc.code = pbt.ksic_code
                WHERE pbt.profile_id = %s AND pbt.ksic_code IS NOT NULL
                ORDER BY pbt.business_type_id DESC
                LIMIT 1
                """,
                (profile_id,),
            )
            ksic_row = cur.fetchone()
            if ksic_row:
                ksic_code, ksic_name = ksic_row
    finally:
        conn.close()

    return JSONResponse(content={
        "success": True,
        "data": {
            "name": name,
            "email": email,
            "profile_type": profile_type,
            "entity_type_code": entity_type_code,
            "entity_type_name": entity_type_name,
            "business_name": business_name,
            "industry_text": industry_text,
            "region": region,
            "business_age_months": business_age_months,
            "annual_revenue": annual_revenue,
            "employee_count": employee_count,
            "founder_age_group": founder_age_group,
            "company_size": company_size,
            "ksic_code": ksic_code,
            "ksic_name": ksic_name,
            "has_biz_cert": bool(has_biz_cert),
        },
    })


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    business_name: str | None = None
    industry_text: str | None = None
    region: str | None = None
    business_age_months: int | None = None
    annual_revenue: int | None = None
    employee_count: int | None = None
    founder_age_group: str | None = None
    entity_type_code: str | None = None
    company_size: str | None = None


@router.put("/profile")
def update_profile(user_id: int, payload: ProfileUpdateRequest) -> JSONResponse:
    # exclude_unset: 요청 본문에 아예 없던 필드는 건드리지 않는다. ProfileEdit.tsx가
    # entity_type_code처럼 이 화면에서 안 다루는 필드는 애초에 안 보내는데, 값이
    # 없다고 None으로 덮어써서 기존 값을 지워버리면 안 되기 때문 (실측 버그로 확인).
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _error(400, "수정할 필드가 없습니다.", "NO_FIELDS")

    # name은 business_profiles가 아니라 users 테이블 컬럼이라 따로 뺀다.
    name = fields.pop("name", None)
    # company_size(중소/소상공인/창업벤처)는 전용 컬럼이 아니라 business_profiles.
    # profile_attributes(JSONB, 그동안 미사용)에 키 하나로 넣는다 - 이 하나만 위해
    # 컬럼을 새로 만들지 않음(2026-09-11, 사용자 확인). 요청에 아예 없으면(sentinel)
    # 건드리지 않는다 - exclude_unset과 동일한 원칙.
    _unset = object()
    company_size = fields.pop("company_size", _unset)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        if cur.fetchone() is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        if name is not None:
            cur.execute("UPDATE users SET name = %s WHERE user_id = %s", (name, user_id))

        if company_size is not _unset:
            cur.execute(
                """
                UPDATE business_profiles
                SET profile_attributes = COALESCE(profile_attributes, '{}'::jsonb)
                        || jsonb_build_object('company_size', %s),
                    updated_at = now()
                WHERE user_id = %s
                """,
                (company_size, user_id),
            )

        if fields:
            set_clause = ", ".join(f"{col} = %s" for col in fields)
            cur.execute(
                f"UPDATE business_profiles SET {set_clause}, updated_at = now() WHERE user_id = %s",
                (*fields.values(), user_id),
            )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={"success": True, "data": {"user_id": user_id}})


@router.post("/biz-cert")
def add_biz_cert(user_id: int, file: UploadFile = File(...), biz_cert_data: str = Form(...)) -> JSONResponse:
    """
    등록된 사업자등록증이 없는 사용자가 마이페이지에서 처음 첨부할 때 씀.
    OCR(/api/auth/biz-cert-ocr)로 이미 확인/수정된 값(biz_cert_data)을 그대로 저장만 한다 -
    signup_endpoint(backend/api/auth.py)의 biz_cert_data 처리와 동일한 패턴, 재OCR 없음.
    """
    content = file.file.read()
    validation_error = _validate_biz_cert_file(file.filename or "", content)
    if validation_error:
        return _error(400, validation_error, "FILE_ERROR")

    try:
        fields = json.loads(biz_cert_data)
    except (json.JSONDecodeError, TypeError):
        return _error(400, "잘못된 사업자등록증 데이터입니다.", "INVALID_FIELDS")

    # [2026-09-11] biz_cert_data가 이미 OCR 확정값이라 이미지를 디스크에 저장할 이유가
    # 없음(사용자 확인, 개인정보 최소화) - 값만 저장, 원본 파일은 버림.
    save_biz_cert_data(user_id, None, file.filename or "", fields)

    return JSONResponse(content={"success": True, "data": {"user_id": user_id}})


@router.get("/bookmarks")
def list_bookmarks(user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "관심있는 지원사업" 목록. 카드 형태는 GET /api/matching(리스트)와
    동일하게 맞춘다 - 프론트에서 AnnouncementCard 컴포넌트를 그대로 재사용하므로."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT a.announcement_id, a.host_org_name, a.title, a.apply_end_date
            FROM bookmarks bm
            JOIN announcements a ON a.announcement_id = bm.announcement_id
            WHERE bm.user_id = %s
            ORDER BY bm.bookmarked_at DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    data = [
        {
            "id": str(announcement_id),
            "agency": host_org_name or "기관명 미기재",
            "dday": _format_dday(apply_end_date),
            "title": title,
            "tags": [],
        }
        for announcement_id, host_org_name, title, apply_end_date in rows
    ]
    return JSONResponse(content={"success": True, "data": data})


@router.get("/fill-history")
def list_fill_history(user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "채우기 이용내역". backend/api/matching.py::fill_attachment()가
    채우기 성공 시 applications에 남긴 기록(파일 자체는 저장 안 함 - attachmentId로
    프론트가 /api/matching/attachments/:id/fill을 다시 호출해 즉석 재생성)을 읽는다.
    공고가 마감됐어도 개인 이용기록이라 목록에서 안 빼고 expired만 표시(사용자 확인, 2026-09-10)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            return JSONResponse(content={"success": True, "data": []})
        profile_id = row[0]

        cur.execute(
            """
            SELECT ap.application_id, att.attachment_id, att.file_name,
                   an.title, an.apply_end_date, ap.exported_at
            FROM applications ap
            JOIN announcement_attachments att ON att.attachment_id = ap.attachment_id
            JOIN announcements an ON an.announcement_id = att.announcement_id
            WHERE ap.profile_id = %s
            ORDER BY ap.exported_at DESC
            """,
            (profile_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    data = [
        {
            "id": str(application_id),
            "attachmentId": attachment_id,
            "fileName": file_name,
            "title": title,
            "expired": bool(apply_end_date and apply_end_date < date.today()),
            "exportedAt": exported_at.strftime("%Y.%m.%d") if exported_at else "",
        }
        for application_id, attachment_id, file_name, title, apply_end_date, exported_at in rows
    ]
    return JSONResponse(content={"success": True, "data": data})
