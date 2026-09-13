# PSST 사업설명 -> 국세청 업종코드(+연계 KSIC코드) 매칭 API.
#
# 실제 매칭 로직은 backend/ml/industry_code_matching/service.py(predict())가 다 한다 -
# 이 파일은 그걸 FastAPI 라우터로 노출만 한다. DB 저장은 안 함(diagnosis.py 쪽 몫).
#
# [주의] LLM 호출 때문에 응답에 8~25초 걸린다(service.py docstring 참고). 프론트에서
# 로딩 표시 필수. 로그인 필요(비로그인 남용 방지) - 결과를 어디 저장하지도 않는 순수
# 조회 엔드포인트라 profile_id는 안 본다.

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.auth.session import get_current_user_id
from backend.ml.industry_code_matching.service import predict

router = APIRouter(prefix="/api/industry-code", tags=["industry-code"])


class IndustryCodeRequest(BaseModel):
    seed_interest: str
    problem_to_solve: str
    solution_approach: str
    has_store: bool | None = None
    region: str = ""


@router.post("")
def match_industry_code(payload: IndustryCodeRequest, user_id: int = Depends(get_current_user_id)) -> JSONResponse:
    result = predict(
        payload.seed_interest,
        payload.problem_to_solve,
        payload.solution_approach,
        is_offline_store=payload.has_store,
        region=payload.region,
    )
    status_code = 200 if result["success"] else 400
    return JSONResponse(status_code=status_code, content=result)
