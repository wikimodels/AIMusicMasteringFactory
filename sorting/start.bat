@echo off
title Music Sorting Studio
cd /d "%~dp0\.."

echo.
echo  ===================================
echo    Music Sorting Studio
echo  ===================================
echo.

echo  [~] Stopping old server (if running)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo  [*] Starting server at http://localhost:5000
echo  Press Ctrl+C to stop
echo.
start "" "http://localhost:5000"
poetry run python sorting/server.py
pause
