@echo off
setlocal

REM  bizinfo (Gigyeopmadang) raw announcement crawl - run once daily.
REM  www.bizinfo.go.kr blocks non-Korea IPs, so GitHub Actions (US runners)
REM  time out. This crawl runs from a Korea-based PC via Task Scheduler at 04:00.
REM  (K-Startup crawl also moved to local Task Scheduler on 2026-09-12 - see crawl_kstartup.bat.)
REM  Setup: see scripts\README.md

REM  cd to repo root (this bat lives in scripts\). bizinfo_api.py loads .env from CWD.
cd /d "%~dp0.."

if not exist "logs" mkdir "logs"

REM  make Python write UTF-8 to the redirected log (avoids mojibake)
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM  crawl_batch_logs.source 에 "-local" 접미사를 남겨서 GitHub Actions(수동 dispatch 포함)와 구분한다
set "CRAWL_SOURCE_SUFFIX=-local"

set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

echo.>> "logs\crawl_bizinfo.log"
echo [%date% %time%] bizinfo crawl start (%PY%)>> "logs\crawl_bizinfo.log"
"%PY%" -m backend.crawler.bizinfo_api >> "logs\crawl_bizinfo.log" 2>&1
set "RC=%ERRORLEVEL%"
echo [%date% %time%] bizinfo crawl end (exit %RC%)>> "logs\crawl_bizinfo.log"

endlocal & exit /b %RC%
