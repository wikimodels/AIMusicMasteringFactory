@echo off
title Baroque Master Album Dashboard
echo ==============================================================================
echo   BAROQUE MASTER ALBUM - DASHBOARD LAUNCHER
echo   Angular Material Web Interface for Early Baroque Music Factory
echo ==============================================================================
cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (
    echo [+] Starting Baroque Dashboard with .venv python on http://127.0.0.1:8088/ ...
    start http://127.0.0.1:8088/
    .venv\Scripts\python.exe baroque_dashboard\server.py 8088
) else (
    echo [+] Starting Baroque Dashboard with system python on http://127.0.0.1:8088/ ...
    start http://127.0.0.1:8088/
    python baroque_dashboard\server.py 8088
)

pause
