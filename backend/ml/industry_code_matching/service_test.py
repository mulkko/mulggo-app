"""
service.py — 백엔드 연동용 진입점.

industry_matcher.match_business_code() 를 감싸서:
  1. 무거운 로딩(참조표·Chroma·bge-m3·OpenAI 클라이언트)을 프로세스 1회만 (lru_cache).
  2. 프론트가 바로 쓰는 납작한 응답으로 정리.

사용 (FastAPI 예):
    from service import predict, warm

    @app.on_event("startup")
    def _startup():
        warm()                     # 서버 기동 시 1회 (모델 GPU 로드, ~10초)

    @app.post("/industry-code")
    def industry_code(body: PsstIn):
        return predict(body.seed, body.problem, body.solution,
                       body.is_offline_store, body.region)   # {"success", "data"|"error"} 그대로 반환

응답 시간: 8~25초 (LLM 호출) → 워커/큐 또는 타임아웃 30초+.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))  # 패키지로 임포트돼도 bare import 되게 (industry_matcher.py와 동일 패턴)
from industry_matcher import match_business_code, warm_up

_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # .../industry_code_matching/ml/backend/<root>
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))  # 스크립트로 단독 실행해도 backend.db.connection 임포트되게

# result_state 내부값 -> 프론트 표시용
_STATE = {
    "추천_가능": "추천",
    "사용자_확인_필요": "확인필요",
    "정보_추가_필요": "정보부족",
}


def warm() -> None:
    """서버 기동 시 1회. 모델·DB 예열 (bge-m3 GPU 로드 포함)."""
    warm_up()


_KSIC_MAP: dict[str, list[str]] | None = None  # 국세청업종코드 -> KSIC코드 목록 (지연 로딩, 프로세스당 1회)


def _load_ksic_map() -> dict[str, list[str]]:
    """nts_ksic_mapping 테이블(DA2, backend/db/load_nts_ksic_mapping.py 적재) 원본 그대로 사용.
    이 모듈 자체 참조 CSV에도 linked_ksic_codes가 있지만 중복 관리 피하려고 DB만 본다."""
    from backend.db.connection import get_connection

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT nts_code, ksic_code FROM nts_ksic_mapping")
        out: dict[str, list[str]] = {}
        for nts_code, ksic_code in cur.fetchall():
            out.setdefault(nts_code, []).append(ksic_code)
        return out
    finally:
        conn.close()


def _ksic_codes(business_code: str) -> list[str]:
    global _KSIC_MAP
    if _KSIC_MAP is None:
        _KSIC_MAP = _load_ksic_map()
    return _KSIC_MAP.get(business_code, [])  # 매핑 누락 코드(DA2 확인 필요분, load_nts_ksic_mapping.py 참고)는 빈 배열


def _slim(b: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": b["business_code"],
        "name": b["business_name"],
        "confidence": b.get("confidence", ""),
        "ksicCodes": _ksic_codes(b["business_code"]),
    }


def predict(
    seed: str,
    problem: str,
    solution: str,
    is_offline_store: bool | None = None,
    region: str = "",
) -> dict[str, Any]:
    """
    PSST 4개(+지역) → 업종코드 결과 (납작한 형태).
    응답 포맷은 CLAUDE.md 8번 규칙(success/data 또는 success/error)을 따른다.

    반환 (성공):
      {
        "success": true,
        "data": {
          "state": "추천" | "확인필요" | "정보부족",   # 화면 분기 키
          "question": "...",                          # state != "추천" 일 때 표시
          "primary":     {"code","name","confidence","ksicCodes"},   # ksicCodes: nts_ksic_mapping DB 조회 (0개 이상)
          "alternatives":[{"code","name"}...],         # 최대 3, "이 업종 아니면?"
          "additional":  [{"code","name","confidence","ksicCodes"}...],  # 부가 업종 0~2
          "raw": {...}                                 # 전체 응답 (로깅/디버깅)
        }
      }
    반환 (검증 실패): {"success": false, "error": {"message": "...", "code": "INVALID_INPUT"}}
    """
    try:
        r = match_business_code(seed, problem, solution,
                                is_offline_store=is_offline_store, region=region)
    except ValueError as e:      # 입력 길이/형식 위반
        return {"success": False, "error": {"message": str(e), "code": "INVALID_INPUT"}}

    rep = r["representative_business"]
    return {
        "success": True,
        "data": {
            "state": _STATE.get(rep["result_state"], "확인필요"),
            "question": rep.get("clarifying_question", ""),
            "primary": _slim(rep),
            "alternatives": [        # 계획서 §8.2: 2·3순위 → 최대 3개만 노출 (raw 엔 더 있음)
                {"code": a["business_code"], "name": a["business_name"]}
                for a in rep.get("alternatives", [])[:3]
            ],
            "additional": [_slim(a) for a in r.get("additional_businesses", [])],
            "raw": r,
        },
    }


if __name__ == "__main__":   # 스모크
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    warm()
    out = predict(
        "직접 볶은 원두로 손님에게 커피를 만들어 파는 카페",
        "동네에 스페셜티 커피를 마실 곳이 없다",
        "매장에서 바리스타가 에스프레소를 제조해 판매하고 원두도 소매한다",
        is_offline_store=True,
    )
    if out["success"]:
        out["data"].pop("raw")
    print(json.dumps(out, ensure_ascii=False, indent=2))
