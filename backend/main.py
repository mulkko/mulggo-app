"""
백엔드 API 서버 실행 진입점.
담당: 백엔드 인프라 TA
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router

app = FastAPI(title="mulkko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)


def main():
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
