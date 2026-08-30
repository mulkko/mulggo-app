# 로그인 로직 (아이디 = 이메일)
# DB 테이블이 아직 없어 실제 조회/비밀번호 검증은 TODO로 남겨둔다.

import re

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


def find_user_by_email(email: str):
    # TODO: 테이블 정의 후 구현 (이메일로 사용자 조회)
    pass


def verify_password(password: str, password_hash) -> bool:
    # TODO: 테이블 정의 후 구현 (비밀번호 해시 비교)
    pass


def login(email: str, password: str) -> tuple[bool, list[str]]:
    is_valid, errors = validate_login_input(email, password)
    if not is_valid:
        return False, errors

    user = find_user_by_email(email)
    # TODO: 테이블 정의 후 구현 (user 존재 여부 확인 + verify_password로 비밀번호 검증)

    return False, ["로그인 기능은 DB 연동 후 사용할 수 있습니다."]
