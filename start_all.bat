@echo off
setlocal
set "ROOT=%~dp0"

start "backend (8000)" cmd /k "cd /d "%ROOT%" && python -m backend.main"
start "frontend (5173)" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
start "admin (8501)" cmd /k "cd /d "%ROOT%" && streamlit run frontend-admin\app.py"

timeout /t 3 >nul
start "" "http://localhost:5173/dev/dev_links.html"
