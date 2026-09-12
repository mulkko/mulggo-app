# 업종코드(KSIC) 매칭 API — 진단 12번 화면(업종코드 매칭)용.
#
# 실제 판정 로직은 backend/ml/industry_code_matching/(다른 세션이 완성한 별도 모듈)의
# service.predict()가 전부 갖고 있다 - 여기선 HTTP 계약(FastAPI 라우터)으로 감싸기만
# 한다. 그 모듈은 "프로젝트 어디에 놓여도 되도록" 자기 자신을 sys.path에 넣고
# `from industry_matcher import ...` 식으로 bare import하게 설계돼 있어서
# (service.py 상단 주석 참고), service.py를 import하기 전에 그 폴더를 sys.path에
# 추가해야 한다 - 그 폴더 안 코드는 손대지 않는다.
#
# [응답 지연] LLM 호출 포함 8~25초 걸릴 수 있다 - 프론트에서 로딩 상태 필수.
# [예열] backend/main.py가 서버 기동 시 warm_industry_matcher()를 1회 호출한다
# (모델 GPU 로드 등 ~10초). 이 저장소엔 chroma_db가 커서 git에 안 올라가 있어
# (.gitignore) 예열이 실패할 수 있는데, 그래도 서버 자체는 떠야 하므로 main.py 쪽에서
# 예열 실패를 삼킨다 - 실제 호출 시점에 다시 에러를 내려준다(아래 except 참고).

import sys
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

_INDUSTRY_MATCH_DIR = Path(__file__).resolve().parent.parent / "ml" / "industry_code_matching"
if str(_INDUSTRY_MATCH_DIR) not in sys.path:
    sys.path.insert(0, str(_INDUSTRY_MATCH_DIR))

from service import predict as match_industry_code  # noqa: E402
from service import warm as warm_industry_matcher  # noqa: E402  (main.py 예열용으로 재노출)

router = APIRouter(prefix="/api/industry-code", tags=["industry-code"])

__all__ = ["router", "warm_industry_matcher"]


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


class IndustryCodeRequest(BaseModel):
    seed_interest: str
    problem_to_solve: str
    solution_approach: str
    has_store: bool | None = None
    region: str = ""


@router.post("")
def industry_code(payload: IndustryCodeRequest) -> JSONResponse:
    try:
        result = match_industry_code(
            payload.seed_interest,
            payload.problem_to_solve,
            payload.solution_approach,
            is_offline_store=payload.has_store,
            region=payload.region,
        )
    except Exception as e:  # noqa: BLE001 - 원인이 다양해(모델 미예열/DB 누락/LLM 오류 등) 폭넓게 잡고 500으로 알림
        return _error(500, f"업종코드 매칭에 실패했습니다: {e}", "INDUSTRY_MATCH_ERROR")

    if not result["success"]:
        return _error(400, result["error"]["message"], result["error"]["code"])

    data = dict(result["data"])
    data.pop("raw", None)  # 로깅/디버깅용 원본 응답 - 용량만 키우니 프론트엔 안 내려줌
    return JSONResponse(content={"success": True, "data": data})
