# 고객센터 챗봇 API.
#
# backend/customer_chatbot/ 의 완성된 로직(call_llm_for_customer_support)을
# 웹 엔드포인트로 감싸기만 한다. 챗봇 로직 자체(프롬프트/지식문서/파싱/폴백)는
# 그 폴더가 담당하고 여기선 손대지 않는다 - docs/customer_chatbot_연동_가이드.md 참고.
#
# 상태를 들고 있지 않다(stateless): 질문 한 건 받아서 답변 한 건 돌려준다.
# 대화 맥락(이전 질문들)은 지금 안 쓴다 - 지식문서 그라운딩 방식이라 매 질문이 독립적.
#
# [OPENAI_API_KEY] backend/customer_chatbot/real_llm_client.py 는 이 키가 없으면
# getpass로 콘솔 입력을 기다린다(서버에선 멈춰버림). 그래서 호출 전에 키 존재를
# 먼저 확인하고, 없으면 바로 500으로 응답한다.

import os

from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from backend.customer_chatbot.customer_service_bot import call_llm_for_customer_support
from backend.customer_chatbot.real_llm_client import call_llm

load_dotenv()

router = APIRouter(prefix="/api/support", tags=["support"])


def _error(status_code: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": {"message": message, "code": code}})


class ChatRequest(BaseModel):
    question: str = ""


@router.post("/chat")
def support_chat(payload: ChatRequest) -> JSONResponse:
    question = (payload.question or "").strip()
    if not question:
        return _error(400, "질문 내용을 입력해주세요.", "EMPTY_QUESTION")

    if not os.environ.get("OPENAI_API_KEY"):
        return _error(500, "챗봇이 아직 설정되지 않았습니다. 관리자에게 문의해주세요.", "LLM_NOT_CONFIGURED")

    try:
        result = call_llm_for_customer_support(question, llm_client=call_llm)
    except Exception as e:  # noqa: BLE001 - 원인(네트워크/인증/지식문서 누락 등) 안 가리고 500으로 내려줌
        return _error(500, f"챗봇 응답 생성에 실패했습니다: {e}", "LLM_ERROR")

    return JSONResponse(content={
        "success": True,
        "data": {
            "answer": result["answer"],
            # True면 프론트에서 "문의 접수하기"(기존 고객센터 문의 폼)로 유도한다.
            "needs_human_support": result["needs_human_support"],
        },
    })
