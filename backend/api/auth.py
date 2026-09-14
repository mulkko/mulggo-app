# 로그인/회원가입 엔드포인트
# backend/auth/login.py, signup.py의 검증 로직을 그대로 호출만 한다.
# CLAUDE.md 8번(API 응답 포맷) 기준 — {"success", "data"} / {"success", "error":{"message","code"}}.

import json
import os
import tempfile

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, Response, UploadFile
from pydantic import BaseModel

from backend.assistant.biz_cert_ocr import (
    classify_ocr_error,
    extract_biz_cert,
    get_cached_vision_model,
)
from backend.auth.login import login
from backend.auth.session import create_session, delete_session, get_current_user_id
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
    business_category = ""
    business_item = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        model, processor = get_cached_vision_model()
        entity_type, biz_cert = extract_biz_cert(tmp_path, model, processor)

        # [테스트] 업태/종목 (2026-09-07): 기본정보 OCR과 별도 파이프라인(EasyOCR)이라
        # 실패 확률이 더 높음 — 실패해도 기본정보는 그대로 팝업에 뜨게 별도로 감쌈.
        # 여러 행이 인식돼도 팝업은 단순 텍스트 2칸이라, 대표(첫) 업태 하나만 보여주고
        # 종목은 콤마로 합쳐서 하나의 문자열로 보여준다.
        try:
            from backend.assistant.category_ocr import extract_categories

            groups = extract_categories(tmp_path, qwen=(model, processor))
            if groups:
                business_category = groups[0].get("업태", "") or ""
                business_item = ", ".join(i for i in groups[0].get("종목", []) if i.strip())
        except Exception as e:
            print(f"[업태/종목 추출 실패] {e}")

        # [2026-09-11] 업태/종목 OCR이 아예 실패하거나, 글자는 읽었어도 우리 KSIC
        # 참고표에 없는 표현이면 업종코드를 알 방법이 없다 - 그 경우 프론트가 사용자에게
        # 직접 선택(GET /api/ksic/options 기반 셀렉트박스)하게 하도록, 여기선 "자동으로
        # 확신 있게 매칭됐는지"만 판단해서 결과에 같이 실어 보낸다. 실시간 응답 경로라
        # LLM 폴백(2단계, 느림·비용)은 빼고 결정적 매칭(1단계)만 시도 - 실패하면 그냥
        # 매칭 없음으로 두고 선택은 사용자 몫으로 넘긴다.
        # [2026-09-13] ksic_core(공고 매칭용, backend/preprocessing/pipeline.py 등)로
        # 통일해봤으나(사용자 확인 시도), 실측 결과 여기서는 안 맞음 - ksic_core 규칙엔진은
        # "지원대상 문맥"이 있는 공고 원문 전제로 설계돼서, 업태/종목 같은 맥락 없는 짧은
        # 구문은("소프트웨어 개발업 응용 소프트웨어 개발 및 공급업"처럼 명확한 경우도)
        # 자동확정을 안 해준다(needs_review=True로 빠짐) - 구버전(decide_industry, 단순
        # 문자열 대조라 짧은 구문에도 강함)은 같은 입력을 HIGH 확신으로 즉시 매칭했다.
        # 자동매칭 성공률 저하(크래시는 아니고 수동 선택으로 자연스럽게 넘어감)를 감수할
        # 가치가 없다고 판단해 이 화면만 구버전 유지로 되돌림(사용자 확인, 2026-09-13).
        ksic_code, ksic_name = "", ""
        combined = f"{business_category} {business_item}".strip()
        if combined:
            try:
                from backend.ml.classifier.decide_industry import decide_industry, needs_human_review

                match = decide_industry(combined, use_llm_fallback=False)
                codes = (match or {}).get("확정코드") or []
                if match and not needs_human_review(match) and len(codes) == 1:
                    ksic_code = codes[0]
                    ksic_name = match["확정업종명"][0]
            except Exception as e:
                print(f"[업종코드 자동매칭 실패] {e}")
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
    result["extracted"]["business_category"] = business_category
    result["extracted"]["business_item"] = business_item
    result["extracted"]["ksic_code"] = ksic_code
    result["extracted"]["ksic_name"] = ksic_name
    return result


class AuthUserData(BaseModel):
    user_id: int
    email: str
    name: str
    token: str | None = None  # 로그인 성공 시에만 채움(회원가입 응답엔 없음 - 가입 직후 자동로그인 안 함)


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
    "ACCOUNT_LOCKED": 401,
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
    token = create_session(user["user_id"])
    response.status_code = 200
    return AuthResponse(
        success=True,
        data=AuthUserData(user_id=user["user_id"], email=user["email"], name=user["name"], token=token),
    )


@router.get("/me")
def get_me_endpoint(user_id: int = Depends(get_current_user_id)) -> dict:
    """[2026-09-15, 사용자 확인] 토큰이 localStorage에 남아있어도 서버 auth_sessions에서
    지워졌으면(전체 로그아웃 등) 무효 - Home.tsx처럼 getAuthToken() 존재 여부만으로
    "로그인됨"을 판단하던 화면이 죽은 토큰을 로그인 상태로 착각하는 문제가 있었다.
    get_current_user_id가 유효성 검증까지 하므로(무효 토큰이면 401) 여기 도달하면 유효한 것."""
    return {"success": True, "data": {"user_id": user_id}}


@router.post("/logout", response_model=AuthResponse)
def logout_endpoint(authorization: str | None = Header(default=None)) -> AuthResponse:
    """[2026-09-12] 로그아웃 - 서버측 auth_sessions에서도 토큰을 지워서 즉시 무효화한다
    (사용자 확인). 토큰 없거나 이미 지워졌어도 에러 안 내고 그냥 성공 처리(로그아웃은
    몇 번을 눌러도 "로그아웃된 상태"로 끝나면 되는 멱등 동작)."""
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else None
    if token:
        delete_session(token)
    return AuthResponse(success=True, data=None)


def _dev_auto_login(response: Response, email_env: str, password_env: str, require_admin: bool = False) -> AuthResponse:
    """[개발 전용] 공통 로직 - .env의 두 값으로 서버가 대신 로그인해서 토큰을 내려준다.
    비밀번호는 프론트/브라우저에 절대 노출되지 않는다(.env는 서버에만 있고 커밋 안 됨).
    두 값이 .env에 없으면(= 대부분의 환경) 그냥 비활성 상태로 404."""
    email = os.environ.get(email_env)
    password = os.environ.get(password_env)
    if not email or not password:
        response.status_code = 404
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message="자동 로그인이 설정되어 있지 않습니다.", code="NOT_CONFIGURED"),
        )

    result = login(email, password)
    if not result["success"]:
        response.status_code = 500
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message="자동 로그인 계정 인증에 실패했습니다 (.env 값을 확인하세요).", code="AUTO_LOGIN_FAILED"),
        )

    user = result["user"]
    if require_admin and not user["is_admin"]:
        response.status_code = 403
        return AuthResponse(
            success=False,
            error=AuthErrorDetail(message="자동 로그인 계정에 관리자 권한이 없습니다.", code="FORBIDDEN"),
        )

    token = create_session(user["user_id"])
    response.status_code = 200
    return AuthResponse(
        success=True,
        data=AuthUserData(user_id=user["user_id"], email=user["email"], name=user["name"], token=token),
    )


@router.post("/dev-auto-login", response_model=AuthResponse)
def dev_auto_login_endpoint(response: Response) -> AuthResponse:
    """[개발 전용] 일반 사용자 로그인 화면 - DEV_AUTO_LOGIN_EMAIL/PASSWORD 계정으로 대신 로그인."""
    return _dev_auto_login(response, "DEV_AUTO_LOGIN_EMAIL", "DEV_AUTO_LOGIN_PASSWORD")


@router.post("/dev-auto-login-admin", response_model=AuthResponse)
def dev_auto_login_admin_endpoint(response: Response) -> AuthResponse:
    """[개발 전용] 관리자 로그인 화면 - DEV_ADMIN_AUTO_LOGIN_EMAIL/PASSWORD 계정으로 대신 로그인.
    admin-login과 동일하게 is_admin 서버 검증 포함."""
    return _dev_auto_login(response, "DEV_ADMIN_AUTO_LOGIN_EMAIL", "DEV_ADMIN_AUTO_LOGIN_PASSWORD", require_admin=True)


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

    token = create_session(user["user_id"])
    response.status_code = 200
    return AuthResponse(
        success=True,
        data=AuthUserData(user_id=user["user_id"], email=user["email"], name=user["name"], token=token),
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
            fields = None
            if biz_cert_data:
                try:
                    fields = json.loads(biz_cert_data)
                except (json.JSONDecodeError, TypeError):
                    fields = None

            if fields:
                # [2026-09-11] 이미 /biz-cert-ocr에서 OCR 끝난 확정값이라 이미지를 다시
                # 디스크에 저장할 이유가 없음(사용자 확인, 개인정보 최소화) - 값만 저장.
                background_tasks.add_task(
                    save_biz_cert_data, user["user_id"], None, biz_cert_file.filename, fields
                )
            else:
                # 레거시 경로: 백그라운드에서 직접 OCR 돌려야 하니 파일이 일단 필요함 -
                # process_biz_cert_ocr가 OCR 끝나면 알아서 지운다.
                os.makedirs(UPLOAD_DIR, exist_ok=True)
                save_path = os.path.join(UPLOAD_DIR, f"{user['user_id']}_{biz_cert_file.filename}")
                with open(save_path, "wb") as f:
                    f.write(content)
                background_tasks.add_task(
                    process_biz_cert_ocr, user["user_id"], save_path, biz_cert_file.filename
                )

    response.status_code = 201
    return AuthResponse(success=True, data=AuthUserData(**user))
