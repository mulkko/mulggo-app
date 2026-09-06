# 로그인 로직 (아이디 = 이메일)

import re

import bcrypt

from backend.db.connection import get_connection

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
            "SELECT user_id, email, name, password_hash, is_admin FROM users WHERE email = %s",
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
        }
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
      실패  {"success": False, "code": "VALIDATION_ERROR" | "UNAUTHORIZED", "errors": [...]}
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

    if not verify_password(password, user["password_hash"]):
        return invalid_credentials

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
