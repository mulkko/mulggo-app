# ============================================================
# ml/classifier/decide_industry.py
#
# 최종 진입점. 파이프라인/서비스 코드는 이제 이 함수 하나만 호출하면 됨
# (match_ksic_by_name을 직접 호출하던 기존 코드는 이걸로 교체).
#
#   decide_industry(원문)
#     ├─ 1단계: match_ksic_by_name()   무료, API 키 불필요, 81% 해결
#     └─ 1단계 실패한 것만 ↓
#          2단계: match_ksic_by_llm()  무료 티어/기존 키 재사용, 나머지 보완
#
# 2단계는 선택사항이다 — use_llm_fallback=False면 1단계까지만 쓰고 멈춘다.
# (API 키 세팅 전이거나, 비용/속도를 더 아끼고 싶을 때)
# ============================================================

from backend.ml.classifier.explicit_match import match_ksic_by_name
from backend.ml.classifier.llm_match import match_ksic_by_llm


def needs_human_review(result: dict | None) -> bool:
    """
    [2026-08-31 추가] 이 매칭 결과를 화면에서 자동 확정으로 보여줄지,
    "AI 추정 - 확인필요"로 표시할지 판단하는 규칙.

    - 1단계(문자열 대조)는 결정적이고 100건 검증에서 헛다리 0건이 확인됐으므로
      ksic_confidence='HIGH' -> 자동 확정, 사람 재확인 불필요.
    - 2단계(LLM)는 여러 차례 반복 실행 결과 재현성이 완벽하지 않고
      (같은 19건을 반복 실행해도 13~15건으로 회수율이 흔들림), 헛다리도
      완전히 0으로 수렴하지 않음(실측 최선 결과 14건) -> ksic_confidence가
      HIGH가 아니면(MED/LOW) 무조건 확인필요로 표시.
    - result가 None(특정불가/해당없음)이면 애초에 확정된 게 없으므로
      review 대상이 아님(하드필터의 △ 처리와 동일하게 별도 취급).
    """
    if result is None:
        return False
    return result.get("ksic_confidence") != "HIGH"


def decide_industry(text: str, use_llm_fallback: bool = True):
    """
    반환값 형식은 두 단계 모두 동일:
      {"확정단계", "확정코드", "확정업종명", "제외업종", "근거", "ksic_confidence"}
    매칭 실패(1·2단계 모두 실패, 또는 2단계 자체를 안 씀)면 None.
    """
    result = match_ksic_by_name(text)
    if result is not None:
        result.setdefault("ksic_confidence", "HIGH")  # 1단계는 결정적 매칭이라 신뢰도 최상
        return result

    if not use_llm_fallback:
        return None

    return match_ksic_by_llm(text)
