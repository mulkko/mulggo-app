# 관리자 대시보드용 엔드포인트
# 공고 수집 현황: raw 테이블에 우리가 실제로 수집·저장한 건수를 센다.
#   - 외부 API의 totCnt/totalCount가 아니다. 그 값은 종료된 공고까지 포함한
#     출처 전체 총계라 "누적 수집 건수" 지표로는 부적절했음(특히 K-Startup은
#     역대 전체 3만여 건이 잡힘). 크롤러는 insert-only+ID 중복제거라
#     raw 테이블 자체가 "우리가 지금까지 모은 공고" = 종료분 포함 누적본이다.

import csv
import io
import threading
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import JSONResponse, Response

from backend.crawler import bizinfo_api, kst_api
from backend.db.connection import get_connection

router = APIRouter(prefix="/admin", tags=["admin"])

# 소스 코드 -> raw 테이블명. 수집 건수/CSV export 공용.
RAW_TABLES = {
    "bizinfo": "announcements_raw_bizinfo",
    "kstartup": "announcements_raw_kstartup",
}


def _count_rows(table: str) -> int:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(f"SELECT count(*) FROM {table}")
        return cursor.fetchone()[0]
    finally:
        connection.close()


@router.get("/bizinfo-count")
def get_bizinfo_count() -> dict:
    return {"count": _count_rows(RAW_TABLES["bizinfo"])}


@router.get("/kstartup-count")
def get_kstartup_count() -> dict:
    return {"count": _count_rows(RAW_TABLES["kstartup"])}


@router.get("/export")
def export_raw(source: str) -> Response:
    """raw 테이블 전체를 CSV로 내려준다. source_raw(원본 JSON)는 제외."""
    table = RAW_TABLES.get(source)
    if table is None:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "message": f"알 수 없는 소스: {source} (가능: {', '.join(RAW_TABLES)})",
                    "code": "UNKNOWN_SOURCE",
                },
            },
        )

    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s AND column_name <> 'source_raw'
            ORDER BY ordinal_position
            """,
            (table,),
        )
        columns = [row[0] for row in cursor.fetchall()]
        cursor.execute(f"SELECT {', '.join(columns)} FROM {table} ORDER BY collected_at")
        rows = cursor.fetchall()
    finally:
        connection.close()

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM - 엑셀에서 한글 안 깨지게
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])

    filename = f"{source}_raw_{date.today().isoformat()}.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


# ── 수동 공고 수집 ──────────────────────────────────────────────
# 소스마다 크롤 시간이 크게 다르다(기업마당 ~1분 / K-Startup 수 분~십수 분:
# 오픈API 전체가 3만여 건, 100건씩 ~300페이지라 한 번에 다 훑음). 그래서
# 요청-응답 안에서 동기로 돌리지 않고 BackgroundTasks로 넘긴 뒤 즉시 202를
# 반환한다. 진행 상황은 /admin/batch-logs 로 확인. auth.py가 이미 쓰는 패턴.

# 진행 중인 소스 (중복 실행 방지). BackgroundTasks가 같은 프로세스에서 돌기
# 때문에 모듈 레벨 set + Lock으로 충분하다(운영 워커 1개 기준).
_running_crawls: set[str] = set()
_running_lock = threading.Lock()


def _crawl_bizinfo() -> None:
    try:
        items = bizinfo_api.fetch_all()
        inserted = bizinfo_api.save_to_db(items)
    except Exception as e:  # noqa: BLE001 - 백그라운드 작업이라 삼키고 로그로 남긴다
        _log_crawl("bizinfo", 0, 0, "error")
        print(f"[crawl] bizinfo 실패: {e}")
    else:
        _log_crawl("bizinfo", len(items), inserted, "success")
    finally:
        with _running_lock:
            _running_crawls.discard("bizinfo")


def _crawl_kstartup() -> None:
    try:
        items = kst_api.fetch_announcements_all()
        summary = kst_api.save_to_db(items)
    except Exception as e:  # noqa: BLE001
        _log_crawl("kstartup", 0, 0, "error")
        print(f"[crawl] kstartup 실패: {e}")
    else:
        _log_crawl("kstartup", len(items), summary["inserted"], "success")
    finally:
        with _running_lock:
            _running_crawls.discard("kstartup")


CRAWLERS = {
    "bizinfo": _crawl_bizinfo,
    "kstartup": _crawl_kstartup,
}


@router.post("/crawl")
def run_crawl(source: str, background_tasks: BackgroundTasks) -> JSONResponse:
    """source(bizinfo/kstartup) 크롤을 백그라운드로 시작하고 즉시 반환한다."""
    if source not in CRAWLERS:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "message": f"알 수 없는 소스: {source} (가능: {', '.join(CRAWLERS)})",
                    "code": "UNKNOWN_SOURCE",
                },
            },
        )

    with _running_lock:
        if source in _running_crawls:
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": {
                        "message": f"{source} 수집이 이미 진행 중입니다.",
                        "code": "ALREADY_RUNNING",
                    },
                },
            )
        _running_crawls.add(source)

    background_tasks.add_task(CRAWLERS[source])
    return JSONResponse(
        status_code=202,
        content={"success": True, "data": {"source": source, "status": "started"}},
    )


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
