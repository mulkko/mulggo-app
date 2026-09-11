"""
물꼬(Mulkko) 업종코드 매칭 - 백엔드 통합 진입점.

사용:
    from industry_matcher import match_business_code

    result = match_business_code(
        seed="직접 볶은 원두로 매장에서 커피 음료를 만들어 손님에게 판매하는 카페를 운영한다",
        problem_to_solve="동네에 제대로 된 스페셜티 커피를 마실 곳이 없다",
        solution_approach="좌석을 갖춘 매장에서 바리스타가 에스프레소 음료를 제조해 현장 판매한다",
        region="",  # 선택. 업종 판정에는 쓰지 않음(그대로 통과만).
    )
    rep = result["representative_business"]
    print(rep["ai_predicted_code"], rep["business_name"], rep["confidence"])

반환 스키마는 README.md 4·5절 참고.

주의(성능):
    match_business_code()는 호출마다 reference CSV 로드 + Chroma 오픈 + OpenAI 클라이언트
    생성을 새로 한다. 요청량이 많으면 아래 warm_up()으로 1회 예열하거나,
    business_matching/23_match_business_code_v3.py 의 load_reference / reference_lookup /
    open_chroma 결과를 서버 기동 시 캐시하도록 리팩터링을 권장한다.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_PKG_ROOT = Path(__file__).resolve().parent
_MODULE_PATH = _PKG_ROOT / "business_matching" / "23_match_business_code_v3.py"

_spec = importlib.util.spec_from_file_location("mulkko_bcm", _MODULE_PATH)
_bcm = importlib.util.module_from_spec(_spec)
sys.modules["mulkko_bcm"] = _bcm
_spec.loader.exec_module(_bcm)

# 공개 함수
match_business_code = _bcm.match_business_code

# 참고용(신뢰도 규칙 등 재사용 시)
compute_confidence = _bcm.compute_confidence
RERANK_TOP_N = _bcm.RERANK_TOP_N
BUSINESS_ROLES = _bcm.BUSINESS_ROLES


def warm_up() -> None:
    """서버 기동 시 1회 호출하면 모델·DB 연결을 미리 확인한다(가벼운 예열)."""
    llm_model, embedding_model = _bcm.load_env()
    _bcm.load_reference()
    _bcm.open_chroma(embedding_model)
    _bcm.load_exclusion_notes()   # 해설서 <제외> 노트 캐시 (재판정에서 사용)
    if not _bcm.embedders.is_openai(embedding_model):
        _bcm.embedders.embed(["예열"], embedding_model)   # 로컬 임베딩 모델 GPU 로드


def health() -> dict[str, Any]:
    """DB·환경 상태 점검용. (2026-09-09판 정상값: chroma_doc_count 14627, reference_rows 1612)"""
    llm_model, embedding_model = _bcm.load_env()
    col = _bcm.open_chroma(embedding_model)
    try:
        _, coll_name = _bcm.embedders.chroma_target(embedding_model)
    except KeyError:
        coll_name = _bcm.COLLECTION
    return {
        "llm_model": llm_model,
        "embedding_model": embedding_model,
        "chroma_collection": coll_name,
        "chroma_doc_count": col.count(),
        "reference_rows": len(_bcm.load_reference()),
        "exclusion_note_codes": len(_bcm.load_exclusion_notes()),
        "rerank_top_n": _bcm.RERANK_TOP_N,
    }


__all__ = [
    "match_business_code",
    "compute_confidence",
    "warm_up",
    "health",
    "RERANK_TOP_N",
    "BUSINESS_ROLES",
]
