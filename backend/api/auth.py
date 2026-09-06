# 로그인/회원가입 엔드포인트
# backend/auth/login.py, signup.py의 검증 로직을 그대로 호출만 한다.
# CLAUDE.md 8번(API 응답 포맷) 기준 — {"success", "data"} / {"success", "error":{"message","code"}}.

import os
import shutil

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile
from pydantic import BaseModel

from backend.auth.login import login
from backend.auth.signup import process_biz_cert_ocr, signup

router = APIRouter(prefix="/api/auth", tags=["auth"])

UPLOAD_DIR = os.path.join("data", "uploads", "biz_registration")


class AuthUserData(BaseModel):
    user_id: int
    email: str
    name: str


class AuthErrorDetail(BaseModel):
    message: str
    code: str


class AuthResponse(BaseModel):
    success: bool
    data: AuthUserData | None = None
    error: AuthErrorDetail | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


_ERROR_STATUS = {
    "VALIDATION_ERROR": 400,
    "UNAUTHORIZED": 401,
    "DUPLICATE_EMAIL": 409,
}


@router.post("/login", response_model=AuthResponse)
def login_endpoint(payload: LoginRequest, response: Response) -> AuthResponse:
    result = login(payload.email, payload.password)

    if not result["success"]:
        code = result["code"]
        response.status_code = _ERROR_STATUS.get(code, 400)
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message=" ".join(result["errors"]), code=code),
        )

    user = result["user"]
    response.status_code = 200
    return AuthResponse(
        success=True,
        data=AuthUserData(user_id=user["user_id"], email=user["email"], name=user["name"]),
    )


@router.post("/admin-login", response_model=AuthResponse)
def admin_login_endpoint(payload: LoginRequest, response: Response) -> AuthResponse:
    # 로그인 로직 자체는 재사용하고, 관리자 화면 전용으로 is_admin만 서버에서 추가 검증.
    # (프론트에서만 막으면 우회 가능하므로 반드시 여기서 확인해야 함.)
    result = login(payload.email, payload.password)

    if not result["success"]:
        code = result["code"]
        response.status_code = _ERROR_STATUS.get(code, 400)
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message=" ".join(result["errors"]), code=code),
        )

    user = result["user"]
    if not user["is_admin"]:
        response.status_code = 403
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message="관리자 권한이 없는 계정입니다.", code="FORBIDDEN"),
        )

    response.status_code = 200
    return AuthResponse(
        success=True,
        data=AuthUserData(user_id=user["user_id"], email=user["email"], name=user["name"]),
    )


@router.post("/signup", response_model=AuthResponse)
def signup_endpoint(
    response: Response,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    agree_terms: bool = Form(...),
    agree_privacy: bool = Form(...),
    biz_cert_file: UploadFile | None = File(None),
) -> AuthResponse:
    result = signup(name, email, password, password_confirm, agree_terms, agree_privacy)

    if not result["success"]:
        code = result["code"]
        response.status_code = _ERROR_STATUS.get(code, 400)
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message=" ".join(result["errors"]), code=code),
        )

    user = result["user"]

    # 사업자등록증은 선택 사항 — 있으면 저장만 하고 OCR은 백그라운드에서 처리.
    # 실패해도 회원가입 자체엔 영향 없음(로그만 남김, process_biz_cert_ocr 내부에서 처리).
    if biz_cert_file is not None and biz_cert_file.filename:
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        save_path = os.path.join(UPLOAD_DIR, f"{user['user_id']}_{biz_cert_file.filename}")
        with open(save_path, "wb") as f:
            shutil.copyfileobj(biz_cert_file.file, f)
        background_tasks.add_task(
            process_biz_cert_ocr, user["user_id"], save_path, biz_cert_file.filename
        )

    response.status_code = 201
    return AuthResponse(success=True, data=AuthUserData(**user))
