@echo off
title Libra - First-Time Setup
color 0A

echo.
echo  _      _____ ____  _____
echo ^| ^|    ^|_   _^|  _ \^|  __ \     /\
echo ^| ^|      ^| ^| ^| ^|_) ^| ^|__) ^|   /  \
echo ^| ^|      ^| ^| ^|  _ ^^/^|  _  /   / /\ \
echo ^| ^|____ _^| ^|_^| ^|_) ^| ^| \ \  / ____ \
echo ^|______^|_____^|____/^|_^|  \_\/_/    \_\
echo.
echo  ============================================
echo.
echo  Press any key to begin setup...
pause >nul
echo.

:: ── 1. Check Docker is installed ────────────────────────────────────
echo [1/3] Checking Docker...
where docker >nul 2>&1
if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo  Docker is not installed on this computer.
    echo  Libra requires Docker Desktop to run.
    echo.
    echo  Opening the Docker Desktop download page...
    timeout /t 2 >nul
    start https://www.docker.com/products/docker-desktop/
    echo.
    echo  After installing Docker Desktop:
    echo    1. Restart your computer
    echo    2. Open Docker Desktop and wait for it to start
    echo    3. Run this script again
    echo.
    pause
    exit /b 1
)

:: ── Check Docker is running ─────────────────────────────────────────
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    color 0E
    echo.
    echo  Docker is installed but not running.
    echo  Attempting to start Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe" 2>nul
    echo.
    echo  Waiting for Docker to start (this can take 30-60 seconds^)...
)
:wait_docker
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo  Still waiting...
    timeout /t 5 >nul
    goto wait_docker
)
echo       Docker is running. OK.
echo.

:: ── 2. Create .env and get API key ──────────────────────────────────
echo [2/3] Checking environment file...
if exist ".env" goto env_done

echo.
echo  =============================================
echo   Libra needs a Together AI API key to work.
echo   Get one free at: https://www.together.ai/
echo  =============================================
echo.
set /p "HAS_KEY=  Do you have a Together AI API key ready? (Y/N): "
if /i "%HAS_KEY%"=="N" (
    echo.
    echo  Opening Together AI signup page...
    start https://api.together.ai/settings/api-keys
    echo.
    echo  After getting your key, run this script again.
    pause
    exit /b 0
)
echo.
set /p "API_KEY=  Paste your Together AI API key here: "
if "%API_KEY%"=="" (
    color 0C
    echo  No key entered. Please run setup again.
    pause
    exit /b 1
)
echo TOGETHER_API_KEY=%API_KEY%> .env
echo.
echo       API key saved to .env. OK.
goto env_continue

:env_done
echo       .env file found. OK.

:env_continue
echo.

:: ── 3. Build and start ──────────────────────────────────────────────
echo [3/3] Building and starting Libra (this may take 10-15 minutes the first time)...
echo.
docker compose up --build -d

if %ERRORLEVEL% neq 0 (
    color 0C
    echo.
    echo  ERROR: Docker build failed. Check the output above.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo       Libra is starting up!
echo  ============================================
echo.
echo  The backend needs a few minutes to initialize
echo  the knowledge base on first run.
echo.
echo  Once ready, open your browser to:
echo.
echo       http://localhost
echo.
echo  To stop Libra later, run:
echo       docker compose down
echo.
echo  ============================================
pause
