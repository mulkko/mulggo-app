"""최종 업종판단 진입점.

이 버전은 '모든 1단계 결과를 UNION'하지 않는다.
우선순위는 다음과 같다.

1) 원문에 직접 명시된 positive KSIC 코드  -> 그대로 보존(권위 소스)
2) 원문에 직접 명시된 국세청 코드        -> KSIC 크로스워크
3) 지원대상 문맥의 KSIC 공식명/안전 동의어
4) 명시적 업종무관 문구
5) LLM fallback

직접 KSIC가 존재하는데 이름매칭으로 C/201/261 같은 부모코드를 덧붙이는
과잉확장을 구조적으로 차단한다.
"""

from __future__ import annotations

from copy import deepcopy
import re

from ksic_core.explicit_match import (
    match_ksic_by_code,
    match_ksic_by_name,
    match_ksic_by_nts_code,
)
from ksic_core.rule_detectors import (
    detect_explicit_scope,
    detect_explicit_industry_agnostic_override,
    detect_manufacturing_requirement,
)
from ksic_core import scope_policy

try:
    from ksic_core.llm_match import match_ksic_by_llm
except Exception:  # 테스트/배포환경에서 LLM 모듈이 없는 경우
    match_ksic_by_llm = None


def _has_positive(result: dict | None) -> bool:
    return bool(result and result.get("확정코드"))


def _excluded_mask(result: dict | None) -> set[str]:
    """전체제외/부분제외 코드는 후속 이름매칭이 다시 positive로 살리지 못하게 한다."""
    mask = set()
    if not result:
        return mask
    for item in result.get("제외업종", []) or []:
        if isinstance(item, dict):
            if item.get("유형") in {"전체제외", "부분제외"}:
                if item.get("코드"):
                    mask.add(str(item["코드"]))
    return mask


def _filter_result_codes(result: dict | None, blocked: set[str]) -> dict | None:
    if not result or not blocked:
        return result
    out = deepcopy(result)
    codes = out.get("확정코드", []) or []
    names = out.get("확정업종명", []) or []
    kept = [(c, n) for c, n in zip(codes, names) if str(c) not in blocked]
    out["확정코드"] = [c for c, _ in kept]
    out["확정업종명"] = [n for _, n in kept]
    if not kept:
        return None
    if len(kept) > 1:
        out["확정단계"] = "복수산업"
    return out


def _merge_stage1_results(name_result, code_result, nts_result):
    """이전 함수명 호환용. 이제 UNION이 아니라 권위 우선순위로 선택한다."""
    # 직접 KSIC가 positive로 존재하면 그것만 사용한다.
    if _has_positive(code_result):
        return code_result

    # 직접 KSIC의 제외표는 후속 결과가 다시 살리지 못하게 mask로 사용.
    blocked = _excluded_mask(code_result)

    if _has_positive(nts_result):
        nts_result = _filter_result_codes(nts_result, blocked)
        if nts_result:
            return nts_result

    if _has_positive(name_result):
        return _filter_result_codes(name_result, blocked)

    return None


def _scope_result(scope: dict) -> dict:
    return {
        "확정단계": scope["status"],
        "확정코드": [],
        "확정업종명": [],
        "제외업종": [],
        "근거": {"매칭방식": "업종범위 판정", "비고": scope.get("reason", "")},
        "ksic_confidence": scope.get("confidence", "LOW"),
        "ksic_status": scope["status"],
    }


def _normalize_llm_result(result: dict | None) -> dict | None:
    """LLM 결과를 자동 HIGH로 두지 않는다.

    HIGH는 직접코드/강한 positive-name 같은 검증 가능한 근거에만 사용한다.
    LLM fallback은 재현성과 근거 검증 문제가 있으므로 최대 MED로 제한한다.
    """
    if not result:
        return None
    out = deepcopy(result)
    current = str(out.get("ksic_confidence", "LOW")).upper()
    out["ksic_confidence"] = "MED" if current == "HIGH" else current
    out.setdefault("근거", {})
    if isinstance(out["근거"], dict):
        out["근거"]["confidence_note"] = "LLM fallback 결과이므로 자동 HIGH 금지"
    return out



def _maybe_merge_explicit_manufacturing_branch(text: str, code_result: dict) -> dict:
    """직접 KSIC 표가 특정 보조산업만 열거하고, 본문 지원대상이 별도로
    '제조업'을 명시한 경우 C를 보존한다.

    직접코드가 있으면 이름매칭을 무조건 UNION하지 않는 원칙은 유지한다.
    다만 광명시처럼 본문 '융자대상: 제조업, 지식산업, 정보통신산업'이고
    붙임 표는 지식산업·정보통신산업만 세부코드로 정의하는 구조에서는
    제조업(C)이라는 독립 지원 branch가 direct 표 밖에 있으므로 누락되면 안 된다.

    조건을 매우 좁게 둔다:
    - 본문 지원/융자/모집/신청대상 근처에 '제조업'이 직접 명시
    - positive appendix/table 헤더가 존재
    - 그 appendix 헤더에는 '제조업'이 없음
    - name matcher도 C를 positive로 확인
    """
    if not code_result or not code_result.get("확정코드"):
        return code_result

    target_m = re.search(
        r"(?:융자|지원|모집|신청|사업)\s*대상.{0,420}",
        text,
        flags=re.I | re.S,
    )
    if not target_m or "제조업" not in target_m.group(0):
        return code_result

    appendix_headers = [
        m.group(0)
        for m in re.finditer(
            r"(?:붙임|븥임|별표)\s*\d+.{0,260}?(?:해당\s*업종|지원\s*업종|분류코드|업종코드|KSIC)",
            text,
            flags=re.I | re.S,
        )
    ]
    if not appendix_headers:
        return code_result
    if any("제조업" in h for h in appendix_headers):
        return code_result

    name_result = match_ksic_by_name(text)
    if not name_result or "C" not in (name_result.get("확정코드") or []):
        return code_result

    out = deepcopy(code_result)
    codes = list(out.get("확정코드") or [])
    names = list(out.get("확정업종명") or [])
    if "C" not in codes:
        codes.insert(0, "C")
        names.insert(0, "제조업")
    out["확정코드"] = codes
    out["확정업종명"] = names
    out["확정단계"] = "복수산업" if len(codes) > 1 else out.get("확정단계", "대분류")
    out.setdefault("근거", {})
    if isinstance(out["근거"], dict):
        out["근거"]["본문_독립지원branch"] = "제조업(C)"
    return out


def decide_industry(
    text: str,
    use_llm_fallback: bool = True,
    *,
    return_scope_result: bool = False,
):
    """업종 판단.

    Args:
        text: 공고 원문.
        use_llm_fallback: 결정적 규칙이 실패했을 때 LLM 사용 여부.
        return_scope_result: True면 명시적 '업종무관/특정불가'도 dict로 반환.
            False(기본)는 기존 파이프라인 호환을 위해 업종무관은 None으로 반환.

    Returns:
        매칭 dict 또는 None.
    """
    result = _decide_industry_core(
        text, use_llm_fallback, return_scope_result=return_scope_result
    )

    # 최우선 override: 직접코드/이름매칭 등 다른 경로가 이미 뭔가 확정했어도,
    # 지원대상 문맥에 명시적 '업종무관' 선언이 있으면 그걸로 덮어쓴다.
    # (다른 규칙을 다 평가한 뒤 마지막에 적용 — PBLN_124861류 버그 수정)
    if text and str(text).strip():
        override = detect_explicit_industry_agnostic_override(text)
        if override:
            if return_scope_result:
                scoped = _scope_result(override)
                scoped.update(scope_policy.build_scope_fields(scoped))
                return scoped
            return None

    if isinstance(result, dict):
        result.update(scope_policy.build_scope_fields(result))
    return result


def _decide_industry_core(
    text: str,
    use_llm_fallback: bool = True,
    *,
    return_scope_result: bool = False,
):
    """override 적용 전, 기존 우선순위 로직 그대로 (decide_industry 내부용)."""
    if not text or not str(text).strip():
        return None

    # 1. 직접 KSIC: authoritative. 이름매칭 결과와 절대 UNION하지 않는다.
    code_result = match_ksic_by_code(text)
    if _has_positive(code_result):
        return _maybe_merge_explicit_manufacturing_branch(text, code_result)

    # 2. 국세청 코드. 1:N이면 explicit_match에서 LOW로 표시된다.
    nts_result = match_ksic_by_nts_code(text)
    blocked = _excluded_mask(code_result)
    if _has_positive(nts_result):
        nts_result = _filter_result_codes(nts_result, blocked)
        if nts_result:
            return nts_result

    # 3. 지원대상 문맥의 업종명.
    name_result = match_ksic_by_name(text)
    if _has_positive(name_result):
        name_result = _filter_result_codes(name_result, blocked)
        if name_result:
            # 결정적 name/synonym 후보가 있으면 LOW/MED라도 그대로 반환해
            # review queue로 보낸다. LLM이 더 불안정한 후보로 덮어쓰지 않게 한다.
            return name_result

    # 3.5 (G3) 신청자격에 '공장등록'이 필수요건이면 제조업(C) 대상으로 본다.
    #     이름매칭이 '제조업'을 직접 못 잡아도 규모기준·공장등록으로 제조업이
    #     확정되는 케이스(중기법 시행령 별표3 맥락).
    mfg_result = detect_manufacturing_requirement(text)
    if mfg_result:
        mfg_result = _filter_result_codes(mfg_result, blocked)
        if mfg_result:
            return mfg_result

    # 4. 공고가 '전 산업 분야/업종 제한 없음'을 직접 선언하면 LLM이 문서의
    # 부수적 업종명을 억지로 확정하지 못하도록 여기서 종료한다.
    scope = detect_explicit_scope(text)
    if scope and scope.get("status") == "업종무관" and scope.get("confidence") == "HIGH":
        return _scope_result(scope) if return_scope_result else None

    # 5. LLM fallback. 이름 규칙이 MED 후보를 갖고 있으면 LLM보다 그 후보가
    # 더 재현가능하므로, LLM이 실패했을 때 반환할 수 있게 보관한다.
    if use_llm_fallback and match_ksic_by_llm is not None:
        llm_result = _normalize_llm_result(match_ksic_by_llm(text))
        if llm_result:
            # 직접 제외코드가 있다면 LLM도 같은 코드를 positive로 되살리지 못하게 한다.
            llm_result = _filter_result_codes(llm_result, blocked)
            if llm_result:
                return llm_result

    # 넓은 기술분야만 있고 KSIC 근거가 없는 경우는 상세모드에서 특정불가로 남긴다.
    if scope and return_scope_result:
        return _scope_result(scope)

    return None


def decide_industry_detailed(text: str, use_llm_fallback: bool = True):
    """업종무관/특정불가를 None과 구분하고 싶은 UI/검증용 진입점."""
    return decide_industry(text, use_llm_fallback=use_llm_fallback, return_scope_result=True)


def needs_human_review(result: dict | None) -> bool:
    """자동확정 가능 여부.

    None은 '검토 불필요'가 아니라 false-negative 가능성이 있으므로 True다.

    2026-09-12부터: 자동확정 기준은 더 이상 ``ksic_confidence == HIGH``가
    아니라 ``auto_accept_eligible``이다(scope_policy 참고). confidence==HIGH
    자동확정 정책은 독립홀드아웃에서 특정업종 확정 정확도 53.1%로 역전되어
    있었다(반면 MED 96.0%/LOW 100.0%). scope_policy 필드가 없는(구버전) 결과는
    기존 로직으로 폴백한다.
    """
    if result is None:
        return True
    if "auto_accept_eligible" in result:
        return not bool(result["auto_accept_eligible"])
    # 하위호환 폴백 (scope_policy가 적용되지 않은 결과)
    if result.get("ksic_status") == "업종무관" and result.get("ksic_confidence") == "HIGH":
        return False
    if str(result.get("확정단계", "")).startswith("확인필요"):
        return True
    return result.get("ksic_confidence") != "HIGH"
