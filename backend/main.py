"""
백엔드 API 서버 실행 진입점.
담당: 백엔드 인프라 TA
"""

import os
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router
from backend.api.test_ocr import router as test_ocr_router
from backend.api.analysis import router as analysis_router
from backend.api.diagnosis import router as diagnosis_router
from backend.api.idea_card_test import router as idea_card_test_router
from backend.api.industry_code import router as industry_code_router, warm_industry_matcher
from backend.api.ksic import router as ksic_router
from backend.api.matching import router as matching_router
from backend.api.mypage import router as mypage_router
from backend.api.support import router as support_router
from backend.db.connection import get_connection

app = FastAPI(title="mulkko API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        # [2026-09-12] AWS EC2 배포 테스트용 프론트 주소(Vite dev server, --host 0.0.0.0).
        # 고정 IP가 아니라 인스턴스를 중지·재시작하면 바뀔 수 있음(Elastic IP 아님) -
        # 바뀌면 이 목록도 새 IP로 갱신 필요.
        "http://3.107.87.41:5173",
    ],
    # [테스트] OCR 하이브리드 구조: 팀원들이 각자 PC의 프론트(5173)에서 GPU PC(192.168.0.160)의
    # 백엔드로 직접 OCR 요청을 보낸다. 팀원마다 IP가 달라 하나하나 등록하는 대신
    # 같은 공유기 대역(192.168.0.x)을 전부 허용해뒀던 것을, [2026-09-14] localhost/
    # 127.0.0.1까지 넓히고 포트 고정(5173)도 풀었다 - 팀원용 5173(포트 8000)은
    # 그대로 두고, 본인 PC에서 별도 포트로 두 번째 프론트+백엔드 쌍을 띄워 테스트할
    # 때도(예: 5175/8001) 매번 이 목록에 추가할 필요 없게 함(사용자 확인).
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.0\.\d{1,3}):\d{2,5}",
    # 개발용 CORS 허용 목록. frontend/.env의 VITE_API_BASE_URL이 가리키는 포트(8000)와
    # 이 서버가 실제로 뜨는 포트가 일치해야 한다.
    allow_methods=["*"],
    allow_headers=["*"],
    
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(test_ocr_router)
app.include_router(analysis_router)
app.include_router(diagnosis_router)
app.include_router(idea_card_test_router)
app.include_router(industry_code_router)
app.include_router(ksic_router)
app.include_router(matching_router)
app.include_router(mypage_router)
app.include_router(support_router)


@app.on_event("startup")
def _clear_sessions_on_restart() -> None:
    # [2026-09-15, 사용자 확인] 백엔드 재시작 시 기존 로그인 세션을 전부 무효화한다 -
    # auth_sessions가 DB(팀 공용 Supabase)에 저장돼서 재시작해도 안 지워지다 보니,
    # 브라우저에 남은 옛 토큰으로 "로그인된 것처럼" 잘못 보이는 문제가 있었다
    # (Home.tsx가 GET /api/auth/me로 토큰을 검증해서 무효면 자동으로 지워주므로,
    # 여기서 서버측 세션만 지우면 프론트는 이미 있는 로직으로 따라온다).
    # 같은 DB를 팀 전체가 써서 이 백엔드가 재시작될 때마다 팀원 전체가 로그아웃되는데,
    # 사용자 확인 완료.
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM auth_sessions")
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
def _warm_industry_matcher() -> None:
    # 모델 GPU 로드 등 ~10초 - 첫 요청이 그 시간을 기다리지 않도록 서버 기동 시 1회 예열.
    # chroma_db는 커서 git에 안 올라가 있어(.gitignore) 없는 개발 환경에서는 예열이
    # 실패할 수 있는데, 그래도 다른 기능은 그대로 떠야 하므로 실패를 삼킨다 -
    # 실제로 /api/industry-code를 호출할 때 그 시점에 다시 에러가 난다.
    #
    # [2026-09-17] 이 함수를 startup에서 동기(블로킹)로 부르면, 임베딩 모델(bge-m3,
    # 2.27GB)이 로컬에 캐시돼 있지 않은 환경(클라우드 서버 최초 기동 등)에서는
    # Hugging Face 다운로드가 끝날 때까지 uvicorn이 포트를 안 열어서 "서버가 아예
    # 안 뜨는 것처럼" 보인다(사용자 확인 - 실측, 다운로드 중 서버 응답 자체가 없었음).
    # 백그라운드 스레드로 돌려서 서버는 즉시 뜨게 하고, 예열이 끝나기 전에 들어온
    # 첫 /api/industry-code 요청은 기존과 동일하게(예열 없었을 때처럼) 그 자리에서
    # 모델을 로드해 처리한다 - 예열은 순수 최적화라 늦게 끝나도 정확성에 영향 없음.
    def _warm():
        try:
            warm_industry_matcher()
        except Exception as e:  # noqa: BLE001
            print(f"[industry_code] 예열 실패 (요청 시점에 재시도됨): {e}")

    threading.Thread(target=_warm, daemon=True).start()


def main():
    import uvicorn

    # [2026-09-14, 사용자 확인] 기본값은 그대로 8000(안 건드리면 예전과 100% 동일) -
    # 팀원들이 쓰는 인스턴스를 안 건드리고, 본인 PC에서 두 번째 인스턴스를 다른
    # 포트로 띄우고 싶을 때만 BACKEND_PORT=8001 같은 식으로 환경변수를 줘서 쓴다.
    port = int(os.getenv("BACKEND_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
