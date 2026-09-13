# ============================================================
# ksic_core/hierarchy.py
#
# 목적
# ------------------------------------------------------------
# KSIC 코드(5자리 숫자, 예: "15211")를 받아서
# 세세분류/세분류/소분류/중분류/대분류를 계산한다.
#
# 기존 03/04번 스크립트에 중복으로 들어있던 로직을
# 여기 한 곳으로 모은다.
# ============================================================

import re


# ============================================================
# 1. 중분류 코드(2자리 숫자) → 대분류 알파벳 변환표
#
# 이건 KSIC 표준 자체의 고정된 규칙이라 데이터가 바뀌어도
# 변하지 않는다 (하드코딩이지만 문제였던 종류의 하드코딩과 다름 —
# Gold 예시에서 뽑은 게 아니라 KSIC 표준 문서 자체의 규칙).
# ============================================================

SECTION_RANGES = [
    (1, 3, "A"),
    (5, 8, "B"),
    (10, 34, "C"),
    (35, 35, "D"),
    (36, 39, "E"),
    (41, 42, "F"),
    (45, 47, "G"),
    (49, 52, "H"),
    (55, 56, "I"),
    (58, 63, "J"),
    (64, 66, "K"),
    (68, 68, "L"),
    (70, 73, "M"),
    (74, 76, "N"),
    (84, 84, "O"),
    (85, 85, "P"),
    (86, 87, "Q"),
    (90, 91, "R"),
    (94, 96, "S"),
    (97, 98, "T"),
    (99, 99, "U"),
]


def get_section_letter(two_digit_code):
    """
    중분류 2자리 코드를 받아 대분류 알파벳을 반환.
    예: "15" -> "C"
    """

    try:
        n = int(two_digit_code)
    except (ValueError, TypeError):
        return ""

    for start, end, letter in SECTION_RANGES:
        if start <= n <= end:
            return letter

    return ""


# ============================================================
# 2. 계층 생성
#
# "15211" 하나를 받아서
# 세세/세/소/중/대분류 코드를 전부 잘라낸 딕셔너리로 반환.
# ============================================================

def build_hierarchy(code):
    """
    KSIC 코드 문자열을 받아 계층별 코드를 반환한다.

    예:
        build_hierarchy("15211")
        ->
        {
            "세세분류": "15211",
            "세분류": "1521",
            "소분류": "152",
            "중분류": "15",
            "대분류": "C"
        }

    자릿수가 부족하면 해당 계층은 빈 문자열("")로 남는다.
    (예: "C" 한 글자만 들어오면 세세~중분류는 전부 "")
    """

    digits = re.sub(r"\D", "", str(code))

    result = {
        "세세분류": "",
        "세분류": "",
        "소분류": "",
        "중분류": "",
        "대분류": "",
    }

    if len(digits) >= 5:
        result["세세분류"] = digits[:5]

    if len(digits) >= 4:
        result["세분류"] = digits[:4]

    if len(digits) >= 3:
        result["소분류"] = digits[:3]

    if len(digits) >= 2:
        result["중분류"] = digits[:2]
        result["대분류"] = get_section_letter(digits[:2])

    # 코드가 아예 알파벳 한 글자(대분류)로만 들어온 경우
    # 예: build_hierarchy("C")
    if not digits and len(str(code).strip()) == 1 and str(code).strip().isalpha():
        result["대분류"] = str(code).strip().upper()

    return result


# ============================================================
# 3. 계층 일치 판단
#
# 서로 다른 정밀도의 두 코드가 "같은 산업"을 가리키는지 비교.
#
# 예:
#   code_a = "C"       (대분류만)
#   code_b = "15211"   (세세분류까지)
#   → code_b는 code_a(C) 안에 포함되므로 "일치"
#
# 04번 스크립트의 candidate_matches_gold 로직을 일반화한 것.
# 나중에 매칭엔진 STEP2(기업KSIC ↔ 공고KSIC 비교)에도 그대로 쓴다.
# ============================================================

def is_same_industry(code_a, code_b):
    """
    두 KSIC 코드(정밀도가 달라도 됨)가 같은 산업 계열인지 판단.

    한쪽이 다른 쪽의 상위 계층이면 True.
    (계층이 겹치는 가장 깊은 레벨에서 비교)
    """

    h_a = build_hierarchy(code_a)
    h_b = build_hierarchy(code_b)

    # 대분류부터 세세분류까지, 둘 다 값이 있는 가장 깊은 레벨에서 비교
    levels = ["대분류", "중분류", "소분류", "세분류", "세세분류"]

    matched_any_level = False

    for level in levels:

        val_a = h_a[level]
        val_b = h_b[level]

        if not val_a or not val_b:
            # 둘 중 하나가 이 레벨 정보가 없으면
            # 더 얕은 레벨까지의 일치만으로 판단하고 멈춤
            break

        if val_a != val_b:
            return False

        matched_any_level = True

    return matched_any_level