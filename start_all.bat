@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

REM cd를 따옴표 문자열 안에 넣지 않고 start의 /D로 시작 디렉터리를 지정한다.
REM %~dp0는 항상 끝에 \가 붙는데, "cd /d "%ROOT%" && ..." 처럼 그 뒤에 바로
REM 닫는 따옴표가 오면 \" 가 이스케이프된 따옴표로 잘못 해석되어 명령어가
REM 깨진다(백엔드 창이 안 뜨거나 조용히 죽는 원인). /D 방식은 이 문제가 없다.
start "backend (8000)" /D "%ROOT%" cmd /k "python -m backend.main"
start "frontend (5173) - 사용자+관리자 화면" /D "%ROOT%\frontend" cmd /k "npm run dev"

timeout /t 3 >nul
start "" "http://localhost:5173/dev/dev_links.html"
