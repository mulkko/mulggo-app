# KSIC(한국표준산업분류) 목록 조회 — 사업자등록증 OCR이 업태/종목을 못 읽거나
# decide_industry()가 매칭 못 했을 때, 사용자가 직접 선택하는 셀렉트박스용.
#
# 1,202건 전부 한 번에 내려주고 대분류→중분류→세세분류 캐스케이드는 프론트에서
# 처리한다 - 데이터가 작아(수십 KB) 단계별 조회 API를 따로 만들 필요가 없음.

from fastapi import APIRouter

from backend.db.connection import get_connection

router = APIRouter(prefix="/api/ksic", tags=["ksic"])


@router.get("/options")
def list_ksic_options() -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT code, name, large_code, large_name, medium_code, medium_name
            FROM ksic_codes
            ORDER BY large_code, medium_code, code
            """
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    data = [
        {
            "code": code,
            "name": name,
            "largeCode": large_code,
            "largeName": large_name,
            "mediumCode": medium_code,
            "mediumName": medium_name,
        }
        for code, name, large_code, large_name, medium_code, medium_name in rows
    ]
    return {"success": True, "data": data}
