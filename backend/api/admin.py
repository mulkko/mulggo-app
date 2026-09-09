# 관리자 대시보드용 엔드포인트
# 공고 수집 현황: raw 테이블에 우리가 실제로 수집·저장한 건수를 센다.
#   - 외부 API의 totCnt/totalCount가 아니다. 그 값은 종료된 공고까지 포함한
#     출처 전체 총계라 "누적 수집 건수" 지표로는 부적절했음(특히 K-Startup은
#     역대 전체 3만여 건이 잡힘). 크롤러는 insert-only+ID 중복제거라
#     raw 테이블 자체가 "우리가 지금까지 모은 공고" = 종료분 포함 누적본이다.

import csv
import io
import os
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

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

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNC_LOG_DIR = PROJECT_ROOT / "logs"


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


# ── 통합 테이블 반영 (raw -> announcements) ──────────────────────
# [임시] 관리자 화면 "통합 반영(임시)" 메뉴에서 호출. sync_*_announcements.py
# 파이프라인(raw 읽어서 지역/업종 매핑 후 announcements 로 UPSERT)을 별도
# 파이썬 프로세스(subprocess)로 돌리고, 그 stdout/stderr를 logs/sync_<source>.log
# 에 남긴다. 화면은 /admin/sync-status 로 그 로그를 폴링해서 텍스트로 보여준다.
#
# 별도 프로세스로 도는 이유:
#   - stdout이 uvicorn 콘솔과 안 섞임(파일로 격리)
#   - bizinfo는 첨부 다운로드+OCR로 수 시간 -> 요청 스레드에서 떼어냄
#   - uvicorn 재시작되면 같이 죽지만, 파이프라인이 only_unprocessed=True 라
#     재실행하면 안 끝난 것만 이어서 처리됨

SYNC_MODULES = {
    "bizinfo": "backend.preprocessing.sync_bizinfo_announcements",
    "kstartup": "backend.preprocessing.sync_kstartup_announcements",
}
_running_syncs: set[str] = set()


def _sync_log_path(source: str) -> Path:
    return SYNC_LOG_DIR / f"sync_{source}.log"


def _run_sync(source: str, limit: int | None = None) -> None:
    SYNC_LOG_DIR.mkdir(exist_ok=True)
    log_path = _sync_log_path(source)
    started = datetime.now().isoformat(timespec="seconds")
    returncode = None
    try:
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(f"=== 시작: {started} · source={source}" + (f" · limit={limit} ===\n" if limit else " ===\n"))
            log_file.flush()
            cmd = [sys.executable, "-m", SYNC_MODULES[source]]
            if limit:
                cmd += ["--limit", str(limit)]
            completed = subprocess.run(  # noqa: S603 - 고정된 내부 모듈만 실행
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=str(PROJECT_ROOT),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            returncode = completed.returncode
            ended = datetime.now().isoformat(timespec="seconds")
            if returncode == 0:
                log_file.write(f"\n=== 성공: {ended} (returncode=0) ===\n")
            else:
                log_file.write(f"\n=== 실패: {ended} (returncode={returncode}) ===\n")
    except Exception as e:  # noqa: BLE001 - 백그라운드라 삼키고 로그로 남긴다
        try:
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write(f"\n=== 실행 자체 실패: {type(e).__name__}: {e} ===\n")
        except OSError:
            pass

    # crawl_batch_logs 에도 결과 한 줄 남긴다 (announcements 현재 건수 기준)
    status = "success" if returncode == 0 else "error"
    try:
        count = _count_rows("announcements")
    except Exception:  # noqa: BLE001
        count = 0
    _log_crawl(f"{source}-sync", count, count, status)

    with _running_lock:
        _running_syncs.discard(source)


@router.post("/sync")
def run_sync(source: str, background_tasks: BackgroundTasks, limit: int | None = None) -> JSONResponse:
    """raw -> announcements 통합 반영을 백그라운드로 시작하고 즉시 반환한다.
    limit: 지정하면 이번 실행에서 그 건수만 처리(테스트/분할 실행용). only_unprocessed=True라
    이미 반영된 건은 자동으로 빠지므로, 같은 limit으로 반복 호출하면 다음 구간이 이어서 처리된다."""
    if source not in SYNC_MODULES:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": {
                    "message": f"알 수 없는 소스: {source} (가능: {', '.join(SYNC_MODULES)})",
                    "code": "UNKNOWN_SOURCE",
                },
            },
        )

    with _running_lock:
        if source in _running_syncs:
            return JSONResponse(
                status_code=409,
                content={
                    "success": False,
                    "error": {
                        "message": f"{source} 통합 반영이 이미 진행 중입니다.",
                        "code": "ALREADY_RUNNING",
                    },
                },
            )
        _running_syncs.add(source)

    background_tasks.add_task(_run_sync, source, limit)
    return JSONResponse(
        status_code=202,
        content={"success": True, "data": {"source": source, "status": "started", "limit": limit}},
    )


@router.get("/sync-status")
def get_sync_status(source: str) -> dict:
    """통합 반영 진행 상태 + 로그 파일 tail(최대 20KB)."""
    if source not in SYNC_MODULES:
        return {"success": False, "error": {"message": f"알 수 없는 소스: {source}", "code": "UNKNOWN_SOURCE"}}

    with _running_lock:
        running = source in _running_syncs

    log_path = _sync_log_path(source)
    log_text = ""
    if log_path.exists():
        raw = log_path.read_text(encoding="utf-8", errors="replace")
        log_text = raw[-20000:]
        if len(raw) > 20000:
            log_text = "…(앞부분 생략)…\n" + log_text

    return {"success": True, "data": {"source": source, "running": running, "log": log_text}}


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
