# 로그인 로직 (아이디 = 이메일)

import re
from datetime import datetime, timezone
from math import ceil

import bcrypt

from backend.db.connection import get_connection

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# [2026-09-12] 로그인 실패 5회 제한(사용자 확인) - users.failed_login_count/locked_until 사용.
FAILED_LOGIN_LIMIT = 5
LOCKOUT_MINUTES = 30


def validate_email(email: str) -> tuple[bool, str]:
    if not email:
        return False, "이메일을 입력해주세요."
    if not EMAIL_PATTERN.match(email):
        return False, "이메일 형식이 올바르지 않습니다."
    return True, ""


def validate_login_input(email: str, password: str) -> tuple[bool, list[str]]:
    errors = []

    is_valid_email, email_error = validate_email(email)
    if not is_valid_email:
        errors.append(email_error)

    if not password:
        errors.append("비밀번호를 입력해주세요.")

    return len(errors) == 0, errors


def find_user_by_email(email: str) -> dict | None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT user_id, email, name, password_hash, is_admin, locked_until FROM users WHERE email = %s",
            (email,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return {
            "user_id": row[0],
            "email": row[1],
            "name": row[2],
            "password_hash": row[3],
            "is_admin": row[4],
            "locked_until": row[5],
        }
    finally:
        connection.close()


def register_failed_login(user_id: int) -> None:
    """실패 횟수 +1. FAILED_LOGIN_LIMIT에 도달하면 그 순간 locked_until을 지금+LOCKOUT_MINUTES로
    설정해서 로그인 자체를 막는다(이미 잠긴 상태면 다시 안 늘림 - locked_until 있으면 로그인
    시도가 login()에서 먼저 걸러져서 여기까지 안 옴)."""
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            UPDATE users
            SET failed_login_count = failed_login_count + 1,
                locked_until = CASE WHEN failed_login_count + 1 >= %s
                                     THEN now() + make_interval(mins => %s)
                                     ELSE locked_until END
            WHERE user_id = %s
            """,
            (FAILED_LOGIN_LIMIT, LOCKOUT_MINUTES, user_id),
        )
        connection.commit()
    finally:
        connection.close()


def reset_failed_login(user_id: int) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE user_id = %s",
            (user_id,),
        )
        connection.commit()
    finally:
        connection.close()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def update_last_login(user_id: int) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE users SET last_login_at = NOW() WHERE user_id = %s", (user_id,))
        connection.commit()
    finally:
        connection.close()


def login(email: str, password: str) -> dict:
    """
    반환:
      성공  {"success": True, "user": {"user_id", "email", "name"}}
      실패  {"success": False, "code": "VALIDATION_ERROR" | "UNAUTHORIZED" | "ACCOUNT_LOCKED", "errors": [...]}
    """
    is_valid, errors = validate_login_input(email, password)
    if not is_valid:
        return {"success": False, "code": "VALIDATION_ERROR", "errors": errors}

    user = find_user_by_email(email)

    # 이메일이 없는 경우와 비밀번호가 틀린 경우를 같은 메시지로 처리
    # (둘을 구분해서 알려주면 "이 이메일은 가입돼있다"는 정보가 새어나감).
    invalid_credentials = {
        "success": False,
        "code": "UNAUTHORIZED",
        "errors": ["이메일 또는 비밀번호가 일치하지 않습니다."],
    }

    if user is None:
        return invalid_credentials

    # [2026-09-12] 로그인 실패 5회 제한 - 비밀번호 확인보다 먼저 체크해서, 잠긴 동안은
    # 맞는 비밀번호를 넣어도 로그인이 안 되게 막는다(무차별 대입 방지 취지에 맞게).
    if user["locked_until"] is not None and user["locked_until"] > datetime.now(timezone.utc):
        remaining_minutes = max(1, ceil((user["locked_until"] - datetime.now(timezone.utc)).total_seconds() / 60))
        return {
            "success": False,
            "code": "ACCOUNT_LOCKED",
            "errors": [f"로그인 시도가 너무 많아 계정이 잠겼습니다. {remaining_minutes}분 후 다시 시도해주세요."],
        }

    if not verify_password(password, user["password_hash"]):
        register_failed_login(user["user_id"])
        return invalid_credentials

    reset_failed_login(user["user_id"])
    update_last_login(user["user_id"])

    return {
        "success": True,
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
            "name": user["name"],
            "is_admin": user["is_admin"],
        },
    }
