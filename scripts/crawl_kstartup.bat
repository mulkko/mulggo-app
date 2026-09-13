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

endlocal & exit /b %RC%
