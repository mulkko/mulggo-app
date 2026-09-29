@echo off
setlocal

REM  K-Startup(창업진흥원) 원본 공고 크롤 - 매일 1회 실행.
REM  원래 GitHub Actions(.github/workflows/crawl-daily.yml)에서 매일 04:07(KST)에 돌았으나,
REM  스케줄 트리거 자체가 몇 시간씩 밀리는 문제가 반복돼(2026-09-11, 09-12 이틀 연속)
REM  로컬 PC 작업 스케줄러로 옮겼다. GitHub Actions 워크플로는 나중에 다시 쓸 수 있게
REM  파일은 남겨두되 스케줄 트리거만 비활성화했다 (workflow_dispatch는 유지).
REM  Setup: see scripts\README.md

REM  cd to repo root (this bat lives in scripts\). kst_api.py loads .env from repo root regardless of CWD.
cd /d "%~dp0.."

if not exist "logs" mkdir "logs"

REM  make Python write UTF-8 to the redirected log (avoids mojibake)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM  crawl_batch_logs.source 에 "-local" 접미사를 남겨서 GitHub Actions(수동 dispatch 포함)와 구분한다
set "CRAWL_SOURCE_SUFFIX=-local"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.>> "logs\crawl_kstartup.log"
echo [%date% %time%] kstartup crawl start (%PY%)>> "logs\crawl_kstartup.log"
"%PY%" -m backend.crawler.kst_api >> "logs\crawl_kstartup.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] kstartup crawl end (exit %RC%)>> "logs\crawl_kstartup.log"

REM  [2026-09-29] 수집 성공 시 이어서 raw -> announcements 통합 반영(미반영분만, 마감 공고는 제외).
REM  관리자 "배치하기"와 같은 동작. 로그는 관리자 "통합 반영(임시)" 화면용 sync_kstartup.log와
REM  섞이지 않게(그 화면이 마지막 "=== 성공" 줄로 다음 시작 위치를 계산함) 별도 파일에 남긴다.
REM  결과 요약은 crawl_batch_logs의 source='kstartup-auto-sync' 행으로 관리자 메인에 표시된다.
if not "%RC%"=="0" goto :done
set "PYTHONUNBUFFERED=1"
echo.>> "logs\sync_kstartup_auto.log"
echo [%date% %time%] kstartup auto-sync start (%PY%)>> "logs\sync_kstartup_auto.log"
"%PY%" -m backend.preprocessing.sync_kstartup_announcements --log-source kstartup-auto-sync >> "logs\sync_kstartup_auto.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] kstartup auto-sync end (exit %RC%)>> "logs\sync_kstartup_auto.log"

:done
endlocal & exit /b %RC%
