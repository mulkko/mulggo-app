# 로그인/회원가입 엔드포인트
# backend/auth/login.py, signup.py의 검증 로직을 그대로 호출만 한다.

from fastapi import APIRouter
from pydantic import BaseModel

from backend.auth.login import login
from backend.auth.signup import signup

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class SignupRequest(BaseModel):
    name: str
    email: str
    password: str
    password_confirm: str
    nickname: str
    agree_terms: bool
    agree_privacy: bool


class AuthResponse(BaseModel):
    success: bool
    errors: list[str]


@router.post("/login", response_model=AuthResponse)
def login_endpoint(payload: LoginRequest) -> AuthResponse:
    success, errors = login(payload.email, payload.password)
    return AuthResponse(success=success, errors=errors)


@router.post("/signup", response_model=AuthResponse)
def signup_endpoint(payload: SignupRequest) -> AuthResponse:
    success, errors = signup(
        payload.name,
        payload.email,
        payload.password,
        payload.password_confirm,
        payload.nickname,
        payload.agree_terms,
        payload.agree_privacy,
    )
    return AuthResponse(success=success, errors=errors)
