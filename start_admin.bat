@echo off
setlocal
set "ROOT=%~dp0"

cd /d "%ROOT%"
streamlit run frontend-admin\app.py
