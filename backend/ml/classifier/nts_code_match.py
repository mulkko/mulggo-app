# ============================================================
# ml/classifier/nts_code_match.py
#
# match_ksic_by_nts_code() - 공고문이 KSIC 업종명이 아니라 국세청 업종코드를
# 숫자로 직접 명시하는 경우를 잡는다. 실측 사례(크리에이터미디어콤플렉스
# 입주공고): "국세청 업종코드 940306(1인 미디어 콘텐츠 창작자) 또는 921505".
# match_ksic_by_name()은 문자열(업종명) 매칭이라 이런 숫자 코드는 못 잡는다.
#
# 흐름: "국세청 업종코드" 문구 뒤에 나오는 숫자를 후보로 추출 -> DB의
# nts_ksic_mapping에 실제 있는 코드만 채택(전화번호 등 다른 숫자가 섞여도
# 매핑 테이블에 없으면 자연히 걸러짐, 별도 화이트리스트 불필요) -> KSIC로 변환.
#
# 국세청 코드 1개가 KSIC 여러 개와 연결되는 1:N 매핑이 실제로 있다
# (docs/DA2_작업현황.md 참고) - 이 경우 어느 KSIC가 맞는지 확정할 수 없으므로
# ksic_confidence를 LOW로 낮춰 사람이 확인하게 한다(match_ksic_by_name의
# "확인필요(다수매칭)"과 같은 처리 방식).
# ============================================================

import re

from backend.db.connection import get_connection

_CONTEXT_RE = re.compile(r"국세청\s*업종\s*코드")
_CODE_RE = re.compile(r"\d{5,6}")
_WINDOW = 150  # "국세청 업종코드" 뒤 이 길이만큼만 후보 숫자를 찾는다 (문단이 바뀌면 무관한 숫자를 주울 위험)


def _extract_candidate_codes(text):
    codes = []
    for m in _CONTEXT_RE.finditer(text):
        window = text[m.end():m.end() + _WINDOW]
        cut = window.find("\n\n")  # 다음 문단으로 넘어가면 멈춘다
        if cut != -1:
            window = window[:cut]
        codes.extend(_CODE_RE.findall(window))

    seen = set()
    ordered = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _fetch_mappings(nts_codes):
    """nts_code -> [(ksic_code, ksic_name), ...]. DB에 실제 있는 코드만
    돌아오므로, 후보 숫자 중 진짜 국세청 코드가 아닌 건 자연히 걸러진다."""
    if not nts_codes:
        return {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT m.nts_code, m.ksic_code, k.name
            FROM nts_ksic_mapping m
            JOIN ksic_codes k ON k.code = m.ksic_code
            WHERE m.nts_code = ANY(%s)
            """,
            (nts_codes,),
        )
        result = {}
        for nts_code, ksic_code, ksic_name in cur.fetchall():
            result.setdefault(nts_code, []).append((ksic_code, ksic_name))
        return result
    finally:
        conn.close()


def match_ksic_by_nts_code(text):
    """반환값 형식은 match_ksic_by_name()과 동일. 매칭 실패(문구 자체가 없거나,
    후보 숫자가 실제 국세청 코드가 아님)면 None."""
    candidates = _extract_candidate_codes(text)
    if not candidates:
        return None

    mapping = _fetch_mappings(candidates)
    if not mapping:
        return None

    codes, names, matched_nts_codes = [], [], []
    is_ambiguous = False
    for nts_code in candidates:
        pairs = mapping.get(nts_code)
        if not pairs:
            continue
        matched_nts_codes.append(nts_code)
        if len(pairs) > 1:
            is_ambiguous = True  # 국세청 코드 1개가 KSIC 여러 개와 연결(1:N)
        for ksic_code, ksic_name in pairs:
            if ksic_code not in codes:
                codes.append(ksic_code)
                names.append(ksic_name)

    if not codes:
        return None

    return {
        "확정단계": "확인필요(국세청코드1:N)" if is_ambiguous else "국세청코드매칭",
        "확정코드": codes,
        "확정업종명": names,
        "제외업종": [],
        "근거": {"매칭방식": "국세청 업종코드 직접명시", "국세청코드": matched_nts_codes},
        "ksic_confidence": "LOW" if is_ambiguous else "HIGH",
    }
