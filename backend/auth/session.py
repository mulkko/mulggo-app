# 로그인 세션 토큰 발급/검증.
#
# JWT 대신 opaque random token + DB 조회 방식을 쓴다: 새 의존성(PyJWT 등) 없이
# stdlib(secrets)만으로 충분하고, 서버 쪽에서 auth_sessions 행을 지우면 즉시
# 로그아웃/폐기가 되는 게 이 프로젝트 규모(3주 부트캠프)엔 JWT보다 더 단순하다.
#
# [2026-09-10] 자동로그인(.env의 DEV_AUTO_LOGIN_EMAIL/PASSWORD)도 이 모듈로 발급한
# 토큰을 그대로 쓴다 - "인증 우회" 코드가 따로 있는 게 아니라, 실제 login()을
# 서버가 대신 호출해주는 것뿐이라 로직 경로가 하나로 유지된다.

import secrets

from fastapi import Header, HTTPException

from backend.db.connection import get_connection


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO auth_sessions (token, user_id) VALUES (%s, %s)",
            (token, user_id),
        )
        connection.commit()
    finally:
        connection.close()
    return token


def get_user_id_by_token(token: str) -> int | None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE auth_sessions SET last_used_at = now() WHERE token = %s RETURNING user_id",
            (token,),
        )
        row = cursor.fetchone()
        connection.commit()
        return row[0] if row else None
    finally:
        connection.close()


def get_current_user_id(authorization: str | None = Header(default=None)) -> int:
    """FastAPI Depends()로 주입: 로그인 필요한 엔드포인트에 `user_id: int = Depends(get_current_user_id)`."""
    token = authorization.removeprefix("Bearer ").strip() if authorization and authorization.startswith("Bearer ") else None
    user_id = get_user_id_by_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user_id
