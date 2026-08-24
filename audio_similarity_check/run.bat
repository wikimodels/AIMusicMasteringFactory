@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ==========================================
echo Audio Similarity Dashboard - Starting
echo ==========================================
echo.

echo [1/4] Killing existing processes on port 5050...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5050 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
    echo       Killed PID %%a
)

echo.
echo [2/4] Starting server...
echo.

set VENV_PYTHON=C:\Users\Vitali\AppData\Local\pypoetry\Cache\virtualenvs\sound-mastering-ddXEiBPa-py3.11\Scripts\python.exe

if not exist %VENV_PYTHON% (
    echo ERROR: Python not found
    pause
    exit /b 1
)

echo ==========================================
echo Server will be available at:
echo   http://127.0.0.1:5050
echo   http://10.8.21.4:5050
echo ==========================================
echo.
echo Press Ctrl+C to stop
echo.

%VENV_PYTHON% server.py