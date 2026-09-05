"""
백엔드 API 서버 실행 진입점.
담당: 백엔드 인프라 TA
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.test_ocr import router as test_ocr_router

app = FastAPI(title="mulkko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    # 개발용 CORS 허용 목록. frontend/.env의 VITE_API_BASE_URL이 가리키는 포트(8000)와
    # 이 서버가 실제로 뜨는 포트가 일치해야 한다.
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(test_ocr_router)


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
