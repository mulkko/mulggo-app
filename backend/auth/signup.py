# 회원가입 로직
# DB 테이블이 아직 없어 실제 저장은 TODO로 남겨둔다.

import re

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{};:'\",.<>/?"
PASSWORD_PATTERN = re.compile(
    r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[" + re.escape(SPECIAL_CHARS) + r"]).{8,}$"
)


def validate_email(email: str) -> tuple[bool, str]:
    if not email:
        return False, "이메일을 입력해주세요."
    if not EMAIL_PATTERN.match(email):
        return False, "이메일 형식이 올바르지 않습니다."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if not password:
        return False, "비밀번호를 입력해주세요."
    if not PASSWORD_PATTERN.match(password):
        return False, "비밀번호는 영문, 숫자, 특수문자를 포함해 8자 이상이어야 합니다."
    return True, ""


def validate_password_confirm(password: str, password_confirm: str) -> tuple[bool, str]:
    if password != password_confirm:
        return False, "비밀번호가 일치하지 않습니다."
    return True, ""


def resolve_agreements(
    agree_all: bool, agree_terms: bool, agree_privacy: bool
) -> tuple[bool, bool, bool]:
    # 전체동의 체크 시 하위 필수 항목을 전부 체크 상태로 만든다.
    if agree_all:
        agree_terms = True
        agree_privacy = True
    return agree_all, agree_terms, agree_privacy


def validate_required_terms(agree_terms: bool, agree_privacy: bool) -> tuple[bool, list[str]]:
    errors = []
    if not agree_terms:
        errors.append("서비스 이용약관에 동의해주세요.")
    if not agree_privacy:
        errors.append("개인정보 수집 및 이용에 동의해주세요.")
    return len(errors) == 0, errors


def save_user(name: str, email: str, password: str, nickname: str) -> None:
    # TODO: 테이블 정의 후 구현 (비밀번호 해싱 포함)
    pass


def signup(
    name: str,
    email: str,
    password: str,
    password_confirm: str,
    nickname: str,
    agree_terms: bool,
    agree_privacy: bool,
) -> tuple[bool, list[str]]:
    errors = []

    if not name:
        errors.append("이름을 입력해주세요.")

    is_valid_email, email_error = validate_email(email)
    if not is_valid_email:
        errors.append(email_error)

    is_valid_password, password_error = validate_password(password)
    if not is_valid_password:
        errors.append(password_error)

    is_valid_confirm, confirm_error = validate_password_confirm(password, password_confirm)
    if not is_valid_confirm:
        errors.append(confirm_error)

    if not nickname:
        errors.append("닉네임을 입력해주세요.")

    _, terms_errors = validate_required_terms(agree_terms, agree_privacy)
    errors.extend(terms_errors)

    if errors:
        return False, errors

    save_user(name, email, password, nickname)
    return True, []
