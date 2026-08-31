@echo off
setlocal enabledelayedexpansion
title CIVIS-CORE — Stop All Services

echo.
echo ================================================================================
echo   CIVIS-CORE  ^|  STOPPING ALL SERVICES
echo ================================================================================
echo.

:: ── Step 1: Find and kill ONLY the process holding port 8000 ─────────────────
echo [1/3] Finding CIVIS process on port 8000...
set "FOUND_PID="

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr " :8000 "') do (
    set "PID=%%a"
    :: Skip PID 0 (system)
    if not "!PID!"=="0" (
        :: Confirm it's a Python process before killing
        for /f "tokens=1" %%p in ('tasklist /FI "PID eq !PID!" /NH 2^>nul ^| findstr /i "python"') do (
            echo   [*] Found CIVIS Python process  PID=!PID!
            taskkill /F /PID !PID! /T >nul 2>&1
            set "FOUND_PID=!PID!"
        )
        :: Also kill if it's uvicorn directly
        for /f "tokens=1" %%p in ('tasklist /FI "PID eq !PID!" /NH 2^>nul ^| findstr /i "uvicorn"') do (
            echo   [*] Found CIVIS uvicorn process  PID=!PID!
            taskkill /F /PID !PID! /T >nul 2>&1
            set "FOUND_PID=!PID!"
        )
    )
)

if "!FOUND_PID!"=="" (
    echo   [*] No CIVIS process found on port 8000 ^(already stopped^).
)

:: ── Step 2: Wait for port to release ─────────────────────────────────────────
echo [2/3] Waiting for port 8000 to release...
ping -n 3 127.0.0.1 >nul

:: ── Step 3: Verify ───────────────────────────────────────────────────────────
echo [3/3] Verifying...
netstat -aon 2>nul | findstr " :8000 " >nul
if errorlevel 1 (
    echo.
    echo   [OK] CIVIS-CORE stopped cleanly. Port 8000 is free.
    echo   [OK] Other Python processes on your system were NOT affected.
) else (
    echo.
    echo   [WARN] Port 8000 still in use. The process may need a moment.
    echo   [HINT] Wait 5 seconds and run this again, or reboot if stuck.
)

echo.
echo ================================================================================
echo   Done. Run START_CIVIS.bat to restart.
echo ================================================================================
echo.
timeout /t 3 >nul
