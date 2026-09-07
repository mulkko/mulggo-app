# 로그인/회원가입 엔드포인트
# backend/auth/login.py, signup.py의 검증 로직을 그대로 호출만 한다.
# CLAUDE.md 8번(API 응답 포맷) 기준 — {"success", "data"} / {"success", "error":{"message","code"}}.

import json
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, File, Form, Response, UploadFile
from pydantic import BaseModel

from backend.assistant.biz_cert_ocr import (
    classify_ocr_error,
    extract_biz_cert,
    get_cached_vision_model,
)
from backend.auth.login import login
from backend.auth.signup import process_biz_cert_ocr, save_biz_cert_data, signup

router = APIRouter(prefix="/api/auth", tags=["auth"])

UPLOAD_DIR = os.path.join("data", "uploads", "biz_registration")

# [테스트->정식] 회원가입용 사업자등록증 업로드 제한. 필요하면 숫자만 바꾸면 됨.
ALLOWED_BIZ_CERT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_BIZ_CERT_SIZE_MB = 10


def _validate_biz_cert_file(filename: str, content: bytes) -> str | None:
    """검증 실패 시 사용자에게 보여줄 한글 메시지, 문제 없으면 None."""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_BIZ_CERT_EXTENSIONS:
        return "jpg, png, pdf 파일만 업로드할 수 있어요."
    if len(content) > MAX_BIZ_CERT_SIZE_MB * 1024 * 1024:
        return f"파일 용량은 {MAX_BIZ_CERT_SIZE_MB}MB 이하만 가능해요."
    return None


def _extracted_to_fields(entity_type: str, biz_cert: dict) -> dict:
    """extract_biz_cert()가 돌려주는 내부 key(dict) -> 프론트에 보여줄 평탄화된 key."""
    return {
        "company_name": biz_cert.get("corp_name") or biz_cert.get("trade_name") or "",
        "ceo_name": biz_cert.get("ceo_name", ""),
        "biz_no": biz_cert.get("biz_no", ""),
        "corp_no": biz_cert.get("corp_no", ""),
        "open_date": biz_cert.get("open_date", ""),
        "birth_date": biz_cert.get("birth_date", ""),
        "business_address": biz_cert.get("address_basic", ""),
        "entity_type": entity_type,
    }


@router.post("/biz-cert-ocr")
async def biz_cert_ocr_endpoint(file: UploadFile = File(...)) -> dict:
    # [회원가입용] 사업자등록증 업로드 -> OCR -> 사용자 확인/수정을 위한 결과 반환.
    # 여기선 DB/디스크에 저장하지 않음 — 사용자가 확인한 뒤 /signup 제출 시 파일+확정값을
    # 같이 보내면 그때 한 번만 저장한다 (재OCR 안 함).
    content = await file.read()

    result: dict = {
        "ocr_success": False,
        "extracted": None,
        "error": None,
        "error_type": None,
        "error_label": None,
    }

    validation_error = _validate_biz_cert_file(file.filename or "", content)
    if validation_error:
        result["error_type"] = "file_error"
        result["error_label"] = validation_error
        result["error"] = validation_error
        return result

    ext = os.path.splitext(file.filename or "")[1].lower()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        model, processor = get_cached_vision_model()
        entity_type, biz_cert = extract_biz_cert(tmp_path, model, processor)
    except Exception as e:
        error_type, error_label = classify_ocr_error(e)
        result["error_type"] = error_type
        result["error_label"] = error_label
        result["error"] = f"OCR 실패: {e}"
        return result
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    result["ocr_success"] = True
    result["extracted"] = _extracted_to_fields(entity_type, biz_cert)
    return result


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
    # [회원가입용] /biz-cert-ocr로 미리 확인/수정을 거친 확정 값 (JSON 문자열, _extracted_to_fields 형태).
    # 있으면 재OCR 안 하고 이 값 그대로 저장. 없으면(레거시 경로) 백그라운드에서 직접 OCR.
    biz_cert_data: str | None = Form(None),
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

    # 사업자등록증은 선택 사항 — 있으면 저장만 하고, 확정값 유무에 따라 재OCR 여부만 다름.
    # 실패해도 회원가입 자체엔 영향 없음(로그만 남김, 아래 두 함수 내부에서 처리).
    if biz_cert_file is not None and biz_cert_file.filename:
        content = biz_cert_file.file.read()
        validation_error = _validate_biz_cert_file(biz_cert_file.filename, content)
        if validation_error:
            # 이 시점엔 이미 /biz-cert-ocr에서 한 번 검증된 파일이 다시 오는 게 정상 경로라,
            # 여기 걸리는 건 예외적인 경우 — 가입 자체는 이미 끝났으니 막지 않고 첨부만 건너뜀.
            print(f"[biz_cert 검증 실패] user_id={user['user_id']}: {validation_error}")
        else:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            save_path = os.path.join(UPLOAD_DIR, f"{user['user_id']}_{biz_cert_file.filename}")
            with open(save_path, "wb") as f:
                f.write(content)

            fields = None
            if biz_cert_data:
                try:
                    fields = json.loads(biz_cert_data)
                except (json.JSONDecodeError, TypeError):
                    fields = None

            if fields:
                background_tasks.add_task(
                    save_biz_cert_data, user["user_id"], save_path, biz_cert_file.filename, fields
                )
            else:
                background_tasks.add_task(
                    process_biz_cert_ocr, user["user_id"], save_path, biz_cert_file.filename
                )

    response.status_code = 201
    return AuthResponse(success=True, data=AuthUserData(**user))
