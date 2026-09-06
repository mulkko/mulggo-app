# 회원가입 로직 + 사업자등록증 OCR 연동
# 비밀번호는 bcrypt 해싱 후 저장. 평문 비밀번호는 어디에도 남기지 않는다.

import os
import re

import bcrypt

from backend.db.connection import get_connection

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


def check_email_exists(email: str) -> bool:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        return cursor.fetchone() is not None
    finally:
        connection.close()


def save_user(name: str, email: str, password: str, agree_terms: bool, agree_privacy: bool) -> dict:
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO users (email, password_hash, name, created_at, agree_terms, agree_privacy)
            VALUES (%s, %s, %s, NOW(), %s, %s)
            RETURNING user_id, email, name
            """,
            (email, password_hash, name, agree_terms, agree_privacy),
        )
        row = cursor.fetchone()
        user_id = row[0]

        # 사업자등록증 없이 가입 = 예비창업자. OCR 성공하면 process_biz_cert_ocr()가 "기존사업자"로 갱신.
        cursor.execute(
            """
            INSERT INTO business_profiles (user_id, profile_type, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            """,
            (user_id, "예비창업자"),
        )

        connection.commit()
        return {"user_id": row[0], "email": row[1], "name": row[2]}
    finally:
        connection.close()


def signup(
    name: str,
    email: str,
    password: str,
    password_confirm: str,
    agree_terms: bool,
    agree_privacy: bool,
) -> dict:
    """
    반환:
      성공  {"success": True, "user": {"user_id", "email", "name"}}
      실패  {"success": False, "code": "VALIDATION_ERROR" | "DUPLICATE_EMAIL", "errors": [...]}

    가입 시점엔 사업자등록증 유무와 무관하게 business_profiles에 profile_type="예비창업자"로 행이 생긴다.
    사업자등록증을 첨부해서 OCR이 성공하면 process_biz_cert_ocr()가 "기존사업자"/individual/corporate로 갱신한다.
    """
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

    _, terms_errors = validate_required_terms(agree_terms, agree_privacy)
    errors.extend(terms_errors)

    if errors:
        return {"success": False, "code": "VALIDATION_ERROR", "errors": errors}

    if is_valid_email and check_email_exists(email):
        return {"success": False, "code": "DUPLICATE_EMAIL", "errors": ["이미 가입된 이메일입니다."]}

    user = save_user(name, email, password, agree_terms, agree_privacy)
    return {"success": True, "user": user}


# ══════════════════════════════════════════════════════
# 사업자등록증 OCR → DB 저장 (회원가입 완료를 지연시키지 않도록 백그라운드에서 호출됨)
# ══════════════════════════════════════════════════════
def process_biz_cert_ocr(user_id: int, file_path: str, original_filename: str) -> None:
    from backend.assistant.biz_cert_ocr import extract_biz_cert, get_cached_vision_model

    try:
        model, processor = get_cached_vision_model()
        entity_type, biz_cert = extract_biz_cert(file_path, model, processor)
    except Exception as e:
        print(f"[biz_cert OCR 실패] user_id={user_id}: {e}")
        return

    # entity_types: 개인/법인 코드 (없으면 최초 1회 생성, TA/DA3 확인 전까지 임시 코드)
    entity_type_code = "corporate" if entity_type == "법인" else "individual"

    connection = get_connection()
    try:
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO entity_types (code, name) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            ("individual", "개인"),
        )
        cursor.execute(
            "INSERT INTO entity_types (code, name) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            ("corporate", "법인"),
        )

        business_name = biz_cert.get("corp_name") or biz_cert.get("trade_name")

        cursor.execute("SELECT profile_id FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if row:
            profile_id = row[0]
            cursor.execute(
                """
                UPDATE business_profiles
                SET profile_type = %s, entity_type_code = %s, business_name = %s, updated_at = NOW()
                WHERE profile_id = %s
                """,
                ("기존사업자", entity_type_code, business_name, profile_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO business_profiles (user_id, profile_type, entity_type_code, business_name, created_at, updated_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                RETURNING profile_id
                """,
                (user_id, "기존사업자", entity_type_code, business_name),
            )
            profile_id = cursor.fetchone()[0]

        cursor.execute(
            """
            INSERT INTO biz_registration_docs (
                profile_id, entity_type_code, file_name, file_type, storage_path,
                biz_no, corp_no, company_name, ceo_name, open_date, birth_date,
                business_address, uploaded_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
            (
                profile_id,
                entity_type_code,
                original_filename,
                os.path.splitext(original_filename)[1].lstrip("."),
                file_path,
                biz_cert.get("biz_no"),
                biz_cert.get("corp_no"),
                business_name,
                biz_cert.get("ceo_name"),
                biz_cert.get("open_date") or None,
                biz_cert.get("birth_date") or None,
                biz_cert.get("address_basic"),
            ),
        )
        connection.commit()
        print(f"[biz_cert OCR 성공] user_id={user_id}, profile_id={profile_id}")
    except Exception as e:
        print(f"[biz_cert DB 저장 실패] user_id={user_id}: {e}")
    finally:
        connection.close()
