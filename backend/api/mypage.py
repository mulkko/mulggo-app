# 마이페이지 - 프로필 요약/수정 API.
#
# [2026-09-09] 로그인 시 user_id를 프론트에 저장하는 세션 처리가 아직 없어서
# (LoginForm.tsx가 로그인 성공해도 user_id를 버림 - 별도로 고쳐야 함), 지금은
# user_id를 쿼리 파라미터로 직접 받는다. 로그인 세션이 붙으면 이 파라미터를
# 그 세션에서 채우도록 프론트만 바꾸면 되고, 이 API 자체는 안 바뀐다.
#
# business_profiles만 연동한다.
# [2026-09-14] apply_status(지원내역)도 GET /apply-status로 연동함 - 이전엔 0건이라
# 범위에서 뺐었는데(2026-09-09), backend/api/matching.py에 POST·DELETE .../apply가
# 생기면서 채워지기 시작함.
# [2026-09-10] bookmarks(찜하기), fill-history(채우기 이용내역)는 연동함 - 다른 프로필
# API와 달리 user_id를 쿼리 파라미터가 아니라 로그인 세션(Depends(get_current_user_id))
# 으로 받는다. 찜하기 토글/채우기(POST .../bookmark, GET .../fill)가 backend/api/
# matching.py에 이미 세션 기준으로 만들어져 있어서 같은 기능끼리는 인증 방식을 맞추는
# 게 맞다고 판단(다른 프로필 API는 세션 연동 전에 만들어진 것들이라 그대로 둠).
# [2026-09-12] idea_refinement_sessions도 diagnosis.py(POST /api/diagnosis/start)가
# 실제로 채우기 시작하면서 연동함(GET /reports) - bookmarks/fill-history와 같은 이유로
# 로그인 세션 기준.

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
                   bp.business_name, bp.industry_text, bp.regions, bp.business_age_months,
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
         industry_text, regions, business_age_months, annual_revenue, employee_count,
         founder_age_group, company_size, has_biz_cert) = row

        # 사업자등록증 등록 시 검색/확정한 업종코드(KSIC) - business_profiles.industry_text와는
        # 별개 테이블(profile_business_types)이라 따로 조회. 여러 번 재등록했으면 가장 최근
        # 것(business_type_id 최댓값)을 쓴다 - is_primary는 재등록 시 갱신 안 되는 문제가
        # 있어(2026-09-11 확인) 믿을 수 없음.
        # [2026-09-14] 같은 김에 업태/종목(business_category/business_item)도 같이 조회 -
        # ProfileEditV2 디자인 포팅(마이페이지 "사업자 정보" 섹션)에 필요해짐.
        ksic_code = ksic_name = business_category = business_item = None
        if profile_id is not None:
            cur.execute(
                """
                SELECT pbt.ksic_code, kc.name, pbt.business_category, pbt.business_item
                FROM profile_business_types pbt
                LEFT JOIN ksic_codes kc ON kc.code = pbt.ksic_code
                WHERE pbt.profile_id = %s
                ORDER BY pbt.business_type_id DESC
                LIMIT 1
                """,
                (profile_id,),
            )
            ksic_row = cur.fetchone()
            if ksic_row:
                ksic_code, ksic_name, business_category, business_item = ksic_row

        # [2026-09-14] 사업자등록증 원본 필드(biz_registration_docs) - ProfileEditV2
        # 디자인의 "사업자 정보" 섹션(사업자번호/법인등록번호/대표자명/개업연월일/생년월일/
        # 사업장·본점 소재지)에 필요. 전부 OCR로 확정된 값이라 읽기전용으로만 보여준다
        # (기업유형처럼 재등록 팝업으로만 바뀜, 이 화면에서 직접 수정 불가).
        biz_no = corp_no = biz_doc_company_name = ceo_name = None
        open_date = birth_date = business_address = head_address = None
        if profile_id is not None:
            cur.execute(
                """
                SELECT biz_no, corp_no, company_name, ceo_name, open_date, birth_date,
                       business_address, head_address
                FROM biz_registration_docs
                WHERE profile_id = %s
                ORDER BY document_id DESC
                LIMIT 1
                """,
                (profile_id,),
            )
            doc_row = cur.fetchone()
            if doc_row:
                (biz_no, corp_no, biz_doc_company_name, ceo_name,
                 open_date, birth_date, business_address, head_address) = doc_row
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
            "regions": regions,
            "business_age_months": business_age_months,
            "annual_revenue": annual_revenue,
            "employee_count": employee_count,
            "founder_age_group": founder_age_group,
            "company_size": company_size,
            "ksic_code": ksic_code,
            "ksic_name": ksic_name,
            "business_category": business_category,
            "business_item": business_item,
            "has_biz_cert": bool(has_biz_cert),
            "biz_no": biz_no,
            "corp_no": corp_no,
            "biz_doc_company_name": biz_doc_company_name,
            "ceo_name": ceo_name,
            "open_date": open_date.isoformat() if open_date else None,
            "birth_date": birth_date.isoformat() if birth_date else None,
            "business_address": business_address,
            "head_address": head_address,
        },
    })


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    business_name: str | None = None
    industry_text: str | None = None
    regions: list[str] | None = None
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


@router.delete("/fill-history/{application_id}")
def delete_fill_history(application_id: int, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "채우기 이용내역" 항목 삭제 - 본인 소유(profile_id)인 것만 지운다."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            return JSONResponse(content={"success": False}, status_code=404)
        profile_id = row[0]
        cur.execute(
            "DELETE FROM applications WHERE application_id = %s AND profile_id = %s",
            (application_id, profile_id),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"success": True})


@router.get("/apply-status")
def list_apply_status(user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "나의 지원내역". [2026-09-14] apply_status는 지원 취소해도 행을
    안 지우고 is_applied만 false로 바꾸는 구조라(이력 보존), is_applied=true인 것만
    걸러서 보여준다. backend/api/matching.py::set_applied()/unset_applied() 참고."""
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
            SELECT a.announcement_id, a.title, aps.checked_at
            FROM apply_status aps
            JOIN announcements a ON a.announcement_id = aps.announcement_id
            WHERE aps.profile_id = %s AND aps.is_applied = true
            ORDER BY aps.checked_at DESC NULLS LAST
            """,
            (profile_id,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    data = [
        {
            "id": str(announcement_id),
            "title": title,
            "status": "지원함",
            "date": checked_at.strftime("%Y.%m.%d") if checked_at else "-",
        }
        for announcement_id, title, checked_at in rows
    ]
    return JSONResponse(content={"success": True, "data": data})


@router.get("/reports")
def list_reports(user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "나의 분석 리포트" 목록. idea_refinement_sessions 중 상권/기술창업
    분석이 끝난 세션(market_analysis 또는 tech_analysis가 채워짐 - backend/api/
    diagnosis.py::_run_report_in_background가 채운다)만 보여준다. 업종명은 저장 시점에
    같이 안 남겨서(테이블엔 KSIC/국세청코드만 있음) resolved_nts_codes[0]을
    nts_industry_codes에서 다시 찾아 붙인다.

    [2026-09-14, 사용자 확인] summary는 psst_problem(사용자가 적은 아이디어 원문)이
    아니라 프로토타입(마이페이지, 17번 페이지) 원본 카드 문구 그대로: "업종코드 {코드}
    · {동} 주변 상권 동향"(카페형=오프라인) / "업종코드 {코드} · 업종 및 특허 분석
    지표"(기술창업형=온라인)."""
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
            SELECT session_id, resolved_nts_codes, business_operation_type, region, created_at
            FROM idea_refinement_sessions
            WHERE profile_id = %s AND (market_analysis IS NOT NULL OR tech_analysis IS NOT NULL)
            ORDER BY created_at DESC
            """,
            (profile_id,),
        )
        rows = cur.fetchall()

        data = []
        for session_id, nts_codes, business_operation_type, region, created_at in rows:
            industry_name = None
            nts_code = nts_codes[0] if nts_codes else None
            if nts_code:
                cur.execute("SELECT name FROM nts_industry_codes WHERE code = %s", (nts_code,))
                found = cur.fetchone()
                industry_name = found[0] if found else None

            code_label = f"업종코드 {nts_code}" if nts_code else "업종코드 미확인"
            if business_operation_type == "오프라인":
                dong = (region or "").split(" ")[-1] if region else ""
                summary = f"{code_label} · {dong} 주변 상권 동향" if dong else f"{code_label} · 주변 상권 동향"
            else:
                summary = f"{code_label} · 업종 및 특허 분석 지표"

            data.append(
                {
                    "id": str(session_id),
                    "industry": industry_name or "업종 미확인",
                    "summary": summary,
                    "createdAt": created_at.strftime("%Y.%m.%d"),
                }
            )
    finally:
        conn.close()

    return JSONResponse(content={"success": True, "data": data})


@router.delete("/reports/{session_id}")
def delete_report(session_id: int, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "나의 분석 리포트" 항목 삭제 - 본인 소유(profile_id)인 것만 지운다."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            return JSONResponse(content={"success": False}, status_code=404)
        profile_id = row[0]
        cur.execute(
            "DELETE FROM idea_refinement_sessions WHERE session_id = %s AND profile_id = %s",
            (session_id, profile_id),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"success": True})


@router.delete("/apply-history/{submission_id}")
def delete_apply_history(submission_id: int, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    """마이페이지 "나의 지원내역" 항목 삭제 - 본인 소유(profile_id)인 것만 지운다.

    [2026-09-14] 지원내역 대응 테이블은 schema.sql에 없는 apply_status임(describe_table로
    실측 확인 - PK는 submission_id). 목록 조회(GET) 자체가 아직 없어서 지금은 삭제
    API/프론트 핸들러만 미리 만들어두는 것까지가 범위(사용자 확인) - 조회 기능을 만들 때
    이 엔드포인트를 그대로 연결하면 된다."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row is None:
            return JSONResponse(content={"success": False}, status_code=404)
        profile_id = row[0]
        cur.execute(
            "DELETE FROM apply_status WHERE submission_id = %s AND profile_id = %s",
            (submission_id, profile_id),
        )
        conn.commit()
    finally:
        conn.close()
    return JSONResponse(content={"success": True})
