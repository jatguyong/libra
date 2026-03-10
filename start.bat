@echo off
title Libra App Startup

echo =========================================
echo       Starting Libra Application
echo =========================================
echo.

:: 1. Setup Frontend
echo [1/4] Checking frontend dependencies...
if not exist "frontend\node_modules\" (
    echo Frontend node_modules not found. Installing...
    cd frontend
    call npm install
    cd ..
) else (
    echo Frontend dependencies already installed.
)
echo.

:: 2. Setup Backend Virtual Environment
echo [2/4] Checking Python virtual environment...
if not exist ".venv\" (
    echo Virtual environment not found. Creating...
    python -m venv .venv
)
echo.

:: 3. Install Backend Dependencies
echo [3/4] Checking backend dependencies...
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt
echo.

:: 4. Start Servers
echo [4/4] Starting servers...

:: Start Backend in a new command prompt window
echo Starting Backend (Python)...
start "Libra Backend" cmd /k "call .venv\Scripts\activate.bat && cd backend && python app.py"

:: Start Frontend in a new command prompt window
echo Starting Frontend (Vite)...
start "Libra Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo =========================================
echo Both services have been started in separate windows!
echo You can close this window now.
echo =========================================
pause
