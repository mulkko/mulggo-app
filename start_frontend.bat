@echo off
setlocal
set "ROOT=%~dp0"

cd /d "%ROOT%frontend"
npm run dev
