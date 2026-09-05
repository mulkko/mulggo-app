# 관리자 대시보드용 엔드포인트
# 기업마당(bizinfo) 총 공고 건수만 가볍게 확인 — 전체 목록은 안 받아오고 1페이지만 요청.

from fastapi import APIRouter

from backend.crawler.bizinfo_api import fetch_page

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bizinfo-count")
def get_bizinfo_count() -> dict:
    data = fetch_page(page_index=1, page_unit=1)
    items = data.get("jsonArray", [])
    if isinstance(items, dict):
        items = [items]

    count = int(items[0].get("totCnt", 0)) if items else 0
    return {"count": count}
