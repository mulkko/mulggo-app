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

        # 사업자등록증 없이 가입 = 예비창업자. OCR/확인 끝나면 save_biz_cert_data()가 "기존사업자"로 갱신.
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
    사업자등록증을 첨부해서 OCR/확인이 끝나면 save_biz_cert_data()가 "기존사업자"+entity_type_code로 갱신한다.
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


# [2026-09-12] 사업장 지역(business_profiles.regions, TEXT[]) - 사업자등록증 OCR의
# business_address에서 뽑아낸 시/도를 자동으로 추가한다(사용자 확인 - 예전엔
# 마포구/서대문구/은평구 3개짜리 수동 셀렉트에 문자열 하나만 담았는데, 공고 매칭이
# 쓰는 지역 단위(announcements.regions)가 구 단위를 아예 안 담고 시/도까지만 있어서
# (matching.py 참고) 단위를 시/도로 맞추고, 예비창업자가 직접 추가하는 "희망 지역"
# 칩과 개념을 통일하려고 배열로 바꿈 - ProfileEdit.tsx 참고).
# 등록 주소는 법정 표기상 항상 정식 시/도명으로 시작하므로 접두어 매칭이면 충분 -
# preprocessing/extract_region.py(공고 원문의 약칭·제외표현까지 다루는 텍스트마이닝)는
# 이 정형화된 등록주소엔 과함.
SIDO_NAMES = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
    "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
    "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도",
]


def derive_sido_from_address(address: str | None) -> str | None:
    """사업장 소재지 주소 맨 앞의 시/도명을 뽑는다. 못 찾으면 None(호출부가 기존 값을
    그대로 두게)."""
    if not address:
        return None
    text = address.strip()
    for sido in SIDO_NAMES:
        if text.startswith(sido):
            return sido
    return None


# ══════════════════════════════════════════════════════
# 사업자등록증 정보 → DB 저장
# ══════════════════════════════════════════════════════
def save_biz_cert_data(user_id: int, file_path: str | None, original_filename: str, fields: dict) -> None:
    """확정된 사업자등록증 정보(fields)를 DB에 저장.
    fields: {company_name, ceo_name, biz_no, corp_no, open_date, birth_date, business_address,
    entity_type, business_category, business_item} (뒤 2개는 업태/종목 — 없어도 됨).
    (직접 OCR을 돌린 결과든, 사용자가 확인/수정 팝업에서 확정한 값이든 같은 형태).
    실패해도 회원가입 자체엔 영향 없음(로그만 남김) — 백그라운드에서 호출됨.

    [2026-09-11] file_path는 이제 항상 None - OCR로 값만 뽑고 원본 이미지는 디스크에
    안 남기기로 함(사용자 확인, 개인정보 최소화). storage_path 컬럼도 그래서 nullable로
    바꿈. 호출부(process_biz_cert_ocr)가 OCR 끝나면 파일을 직접 지운다."""
    entity_type_code = "corporate" if fields.get("entity_type") == "법인" else "individual"

    connection = get_connection()
    try:
        cursor = connection.cursor()

        # entity_types: 개인/법인 코드 (없으면 최초 1회 생성, TA/DA3 확인 전까지 임시 코드)
        cursor.execute(
            "INSERT INTO entity_types (code, name) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            ("individual", "개인"),
        )
        cursor.execute(
            "INSERT INTO entity_types (code, name) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
            ("corporate", "법인"),
        )

        business_name = fields.get("company_name") or None
        derived_region = derive_sido_from_address(fields.get("business_address"))

        # [2026-09-12] region TEXT -> regions TEXT[] (사용자 확인) - 예비창업자가 직접
        # 추가해둔 "희망 지역" 칩이 있을 수 있어서, 자동으로 뽑은 시/도는 통째로
        # 덮어쓰지 않고 없을 때만 배열에 추가한다(기존 칩 보존).
        cursor.execute("SELECT profile_id, regions FROM business_profiles WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if row:
            profile_id, existing_regions = row
            existing_regions = existing_regions or []
            if derived_region and derived_region not in existing_regions:
                new_regions = existing_regions + [derived_region]
            else:
                new_regions = existing_regions or None
            cursor.execute(
                """
                UPDATE business_profiles
                SET profile_type = %s, entity_type_code = %s, business_name = %s,
                    regions = %s, updated_at = NOW()
                WHERE profile_id = %s
                """,
                ("기존사업자", entity_type_code, business_name, new_regions, profile_id),
            )
        else:
            cursor.execute(
                """
                INSERT INTO business_profiles (user_id, profile_type, entity_type_code, business_name, regions, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING profile_id
                """,
                (user_id, "기존사업자", entity_type_code, business_name, [derived_region] if derived_region else None),
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
                fields.get("biz_no") or None,
                fields.get("corp_no") or None,
                business_name,
                fields.get("ceo_name") or None,
                fields.get("open_date") or None,
                fields.get("birth_date") or None,
                fields.get("business_address") or None,
            ),
        )
        # [테스트] 업태/종목 (profile_business_types) — 2026-09-07 연결, 09-08 확인 팝업으로 이동.
        # 이제 이 함수는 재추출 안 하고, 호출부(팝업 확인 or process_biz_cert_ocr)가 이미
        # 넣어준 fields.business_category/business_item을 그대로 저장만 한다.
        business_category = fields.get("business_category") or None
        business_item = fields.get("business_item") or None
        # [2026-09-11] ksic_code: OCR 텍스트가 decide_industry()로 확신 있게 자동매칭됐거나,
        # 그게 안 돼서 사용자가 셀렉트박스로 직접 고른 값 - 둘 다 fields.ksic_code로 같은
        # 모양으로 들어온다(/api/auth/biz-cert-ocr 응답 또는 BizCertUpload 확인 팝업 수정값).
        ksic_code = fields.get("ksic_code") or None
        if business_category or business_item or ksic_code:
            # [2026-09-12] 재업로드(재등록) 시 기존 행을 그대로 두고 is_primary=true인
            # 새 행만 추가하면, 같은 profile_id에 is_primary=true가 여러 개 남아서
            # "현재 업종이 뭔지" 조회(matching.py::_lookup_profile_ksic_code(), 최초
            # ORDER BY is_primary DESC LIMIT 1)가 어느 걸 고를지 보장이 안 됐다(실측
            # 확인한 버그) - 새로 확정하기 전에 기존 행을 전부 false로 내려서 새 행만
            # 유일한 is_primary=true가 되게 한다.
            cursor.execute(
                "UPDATE profile_business_types SET is_primary = false WHERE profile_id = %s",
                (profile_id,),
            )
            cursor.execute(
                """
                INSERT INTO profile_business_types
                    (profile_id, business_category, business_item, ksic_code, is_primary)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (profile_id, business_category, business_item, ksic_code, True),
            )

        connection.commit()
        print(f"[biz_cert 저장 성공] user_id={user_id}, profile_id={profile_id}")
    except Exception as e:
        print(f"[biz_cert DB 저장 실패] user_id={user_id}: {e}")
    finally:
        connection.close()


def process_biz_cert_ocr(user_id: int, file_path: str, original_filename: str) -> None:
    """레거시 경로: 확인/수정 팝업 없이 파일만 온 경우, 백그라운드에서 직접 OCR 돌리고 저장.
    (정상 경로는 /api/auth/biz-cert-ocr로 먼저 확인받은 뒤 save_biz_cert_data를 씀)

    [2026-09-11] OCR에만 file_path(임시로 디스크에 저장된 원본)를 쓰고, 끝나면(성공/실패
    무관) 바로 지운다 - 이미지 자체는 저장할 이유가 없음(사용자 확인)."""
    from backend.assistant.biz_cert_ocr import extract_biz_cert, get_cached_vision_model

    try:
        try:
            model, processor = get_cached_vision_model()
            entity_type, biz_cert = extract_biz_cert(file_path, model, processor)
        except Exception as e:
            print(f"[biz_cert OCR 실패] user_id={user_id}: {e}")
            return

        fields = {
            "company_name": biz_cert.get("corp_name") or biz_cert.get("trade_name") or "",
            "ceo_name": biz_cert.get("ceo_name", ""),
            "biz_no": biz_cert.get("biz_no", ""),
            "corp_no": biz_cert.get("corp_no", ""),
            "open_date": biz_cert.get("open_date", ""),
            "birth_date": biz_cert.get("birth_date", ""),
            "business_address": biz_cert.get("address_basic", ""),
            "entity_type": entity_type,
        }

        # 확인 팝업을 안 거치는 경로라 여기서 직접 업태/종목까지 뽑아서 넘긴다.
        try:
            from backend.assistant.category_ocr import extract_categories

            groups = extract_categories(file_path, qwen=(model, processor))
            if groups:
                fields["business_category"] = groups[0].get("업태", "") or ""
                fields["business_item"] = ", ".join(i for i in groups[0].get("종목", []) if i.strip())
        except Exception as e:
            print(f"[업태/종목 추출 실패] user_id={user_id}: {e}")

        save_biz_cert_data(user_id, None, original_filename, fields)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
