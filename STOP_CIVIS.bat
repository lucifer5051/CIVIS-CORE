@echo off
setlocal enabledelayedexpansion
title CIVIS-CORE  ^|  Stop All Services

:: ============================================================================
::  CIVIS-CORE  -  Cold-Start-Aware Stop Script
::  Works on any Windows laptop, no PATH required.
::  Safely kills only CIVIS-related processes, not other Python apps.
:: ============================================================================

echo.
echo ================================================================================
echo   CIVIS-CORE  ^|  STOPPING ALL SERVICES
echo ================================================================================
echo.

:: ── Self-locate ──────────────────────────────────────────────────────────────
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"
set "PORT=8000"

echo   Project root : %PROJECT_DIR%
echo.

:: ============================================================================
::  STEP 1 - Find and kill the process holding port 8000
::  Only kills Python/uvicorn — does NOT kill other Python apps
:: ============================================================================
echo [STEP 1/3] Finding CIVIS process on port %PORT%...
set "FOUND_PID="
set "KILL_COUNT=0"

for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":%PORT% "') do (
    set "PID=%%a"
    if not "!PID!"=="0" (
        :: Check if it is a Python process
        for /f "tokens=1" %%p in ('tasklist /FI "PID eq !PID!" /NH 2^>nul ^| findstr /i "python"') do (
            echo   [*] Killing Python process  PID=!PID!
            taskkill /F /PID !PID! /T >nul 2>&1
            set "FOUND_PID=!PID!"
            set /a KILL_COUNT+=1
        )
        :: Check if it is uvicorn
        for /f "tokens=1" %%p in ('tasklist /FI "PID eq !PID!" /NH 2^>nul ^| findstr /i "uvicorn"') do (
            echo   [*] Killing uvicorn process  PID=!PID!
            taskkill /F /PID !PID! /T >nul 2>&1
            set "FOUND_PID=!PID!"
            set /a KILL_COUNT+=1
        )
    )
)

:: Also sweep for any orphaned python.exe tied to this project
for /f "tokens=2" %%a in ('tasklist /FI "IMAGENAME eq python.exe" /NH 2^>nul ^| findstr /i "python"') do (
    set "PID=%%a"
    if not "!PID!"=="0" (
        :: Check command line for run_civis
        wmic process where "ProcessId=!PID!" get CommandLine 2>nul | findstr /i "run_civis" >nul
        if not errorlevel 1 (
            echo   [*] Killing orphaned run_civis.py  PID=!PID!
            taskkill /F /PID !PID! /T >nul 2>&1
            set /a KILL_COUNT+=1
        )
    )
)

if "!FOUND_PID!"=="" if !KILL_COUNT!==0 (
    echo   [*] No CIVIS process found on port %PORT% ^(already stopped^).
) else (
    echo   [OK] Killed !KILL_COUNT! process(es).
)
echo.

:: ============================================================================
::  STEP 2 - Wait for port to release
:: ============================================================================
echo [STEP 2/3] Waiting for port %PORT% to release...
ping -n 3 127.0.0.1 >nul

:: ============================================================================
::  STEP 3 - Verify port is free
:: ============================================================================
echo [STEP 3/3] Verifying port %PORT% is free...
netstat -aon 2>nul | findstr ":%PORT% " >nul
if errorlevel 1 (
    echo.
    echo   [OK] CIVIS-CORE stopped cleanly.
    echo   [OK] Port %PORT% is free.
    echo   [OK] Other Python processes on your system were NOT affected.
) else (
    echo.
    echo   [WARN] Port %PORT% still in use. Process may need a moment to release.
    echo   [HINT] Wait 5-10 seconds and run STOP_CIVIS.bat again.
    echo   [HINT] If stuck, reboot or run:  netstat -aon ^| findstr ":%PORT%"
)

echo.
echo ================================================================================
echo   Done. Double-click START_CIVIS.bat to restart CIVIS-CORE.
echo ================================================================================
echo.
timeout /t 3 >nul
