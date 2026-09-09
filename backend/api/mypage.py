# 마이페이지 - 프로필 요약/수정 API.
#
# [2026-09-09] 로그인 시 user_id를 프론트에 저장하는 세션 처리가 아직 없어서
# (LoginForm.tsx가 로그인 성공해도 user_id를 버림 - 별도로 고쳐야 함), 지금은
# user_id를 쿼리 파라미터로 직접 받는다. 로그인 세션이 붙으면 이 파라미터를
# 그 세션에서 채우도록 프론트만 바꾸면 되고, 이 API 자체는 안 바뀐다.
#
# business_profiles만 연동한다 - bookmarks/applications/apply_status/
# idea_refinement_sessions는 실제 DB에 0건이라(연동해도 항상 빈 목록) 지금
# 범위에서 제외함(사용자 확인, 2026-09-09).

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

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
            SELECT u.name, u.email, bp.profile_type, bp.entity_type_code, et.name,
                   bp.business_name, bp.industry_text, bp.region, bp.business_age_months,
                   bp.annual_revenue, bp.employee_count, bp.founder_age_group
            FROM users u
            LEFT JOIN business_profiles bp ON bp.user_id = u.user_id
            LEFT JOIN entity_types et ON et.code = bp.entity_type_code
            WHERE u.user_id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()

    if row is None:
        return _error(404, f"user_id={user_id} 회원을 찾을 수 없습니다.", "USER_NOT_FOUND")

    (name, email, profile_type, entity_type_code, entity_type_name, business_name,
     industry_text, region, business_age_months, annual_revenue, employee_count,
     founder_age_group) = row

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
        },
    })


class ProfileUpdateRequest(BaseModel):
    business_name: str | None = None
    industry_text: str | None = None
    region: str | None = None
    business_age_months: int | None = None
    annual_revenue: int | None = None
    employee_count: int | None = None
    founder_age_group: str | None = None
    entity_type_code: str | None = None


@router.put("/profile")
def update_profile(user_id: int, payload: ProfileUpdateRequest) -> JSONResponse:
    # exclude_unset: 요청 본문에 아예 없던 필드는 건드리지 않는다. ProfileEdit.tsx가
    # entity_type_code처럼 이 화면에서 안 다루는 필드는 애초에 안 보내는데, 값이
    # 없다고 None으로 덮어써서 기존 값을 지워버리면 안 되기 때문 (실측 버그로 확인).
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        return _error(400, "수정할 필드가 없습니다.", "NO_FIELDS")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        if cur.fetchone() is None:
            return _error(404, f"user_id={user_id}에 해당하는 business_profiles가 없습니다.", "PROFILE_NOT_FOUND")

        set_clause = ", ".join(f"{col} = %s" for col in fields)
        cur.execute(
            f"UPDATE business_profiles SET {set_clause}, updated_at = now() WHERE user_id = %s",
            (*fields.values(), user_id),
        )
        conn.commit()
    finally:
        conn.close()

    return JSONResponse(content={"success": True, "data": {"user_id": user_id}})
