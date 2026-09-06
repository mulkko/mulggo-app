# 관리자 대시보드용 엔드포인트
# 기업마당(bizinfo) 총 공고 건수만 가볍게 확인 — 전체 목록은 안 받아오고 1페이지만 요청.

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from backend.crawler.bizinfo_api import fetch_all, fetch_page, save_to_db
from backend.db.connection import get_connection

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bizinfo-count")
def get_bizinfo_count() -> dict:
    data = fetch_page(page_index=1, page_unit=1)
    items = data.get("jsonArray", [])
    if isinstance(items, dict):
        items = [items]

    count = int(items[0].get("totCnt", 0)) if items else 0
    return {"count": count}


def _log_crawl(source: str, fetched_count: int, inserted_count: int, status: str) -> None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO crawl_batch_logs (source, fetched_count, inserted_count, status)
            VALUES (%s, %s, %s, %s)
            """,
            (source, fetched_count, inserted_count, status),
        )
        connection.commit()
    finally:
        connection.close()


@router.post("/bizinfo-crawl")
def run_bizinfo_crawl() -> dict:
    try:
        items = fetch_all()
        inserted = save_to_db(items)
    except Exception as e:
        _log_crawl("bizinfo", 0, 0, "error")
        return {"success": False, "error": {"message": str(e), "code": "CRAWL_FAILED"}}

    _log_crawl("bizinfo", len(items), inserted, "success")
    return {"success": True, "data": {"fetched": len(items), "inserted": inserted}}


@router.get("/batch-logs")
def get_batch_logs() -> dict:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT source, fetched_count, inserted_count, status, ran_at
            FROM crawl_batch_logs
            ORDER BY ran_at DESC
            LIMIT 5
            """
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    logs = [
        {
            "source": source,
            "fetched_count": fetched_count,
            "inserted_count": inserted_count,
            "status": status,
            "ran_at": ran_at.isoformat(),
        }
        for source, fetched_count, inserted_count, status, ran_at in rows
    ]
    return {"success": True, "data": {"logs": logs}}


KST = timezone(timedelta(hours=9))


@router.get("/members")
def get_members() -> dict:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT u.user_id, u.name, u.email, u.created_at, bp.entity_type_code, u.last_login_at
            FROM users u
            LEFT JOIN business_profiles bp ON bp.user_id = u.user_id
            ORDER BY u.created_at DESC
            """
        )
        rows = cursor.fetchall()
    finally:
        connection.close()

    now = datetime.now(timezone.utc)
    today_kst = now.astimezone(KST).date()
    active_cutoff = now - timedelta(days=30)

    members = []
    total_count = 0
    new_today_count = 0
    active_count = 0

    for user_id, name, email, created_at, applicant_type, last_login_at in rows:
        total_count += 1

        if created_at.astimezone(KST).date() == today_kst:
            new_today_count += 1

        last_activity = last_login_at or created_at
        is_active = last_activity >= active_cutoff
        if is_active:
            active_count += 1

        members.append(
            {
                "user_id": user_id,
                "name": name,
                "email": email,
                "created_at": created_at.isoformat(),
                "applicant_type": applicant_type,
                "last_login_at": last_login_at.isoformat() if last_login_at else None,
                "status": "active" if is_active else "dormant",
            }
        )

    return {
        "success": True,
        "data": {
            "members": members,
            "stats": {
                "total": total_count,
                "new_today": new_today_count,
                "active_30d": active_count,
            },
        },
    }
