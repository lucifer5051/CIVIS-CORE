@echo off
setlocal enabledelayedexpansion
title CIVIS-CORE  ^|  Cold-Start Launcher

:: ============================================================================
::  CIVIS-CORE  -  Cold-Start Launcher
::  Works on any Windows laptop, first boot, even with no preset PATH.
::  Checks and installs Python packages + Node build only when needed.
:: ============================================================================

echo.
echo ================================================================================
echo   CIVIS-CORE  ^|  LIVE SURVEILLANCE  -  Cold-Start Launcher
echo ================================================================================
echo.

:: -- Self-locate (correct path regardless of where the script is run from) ----
set "PROJECT_DIR=%~dp0"
if "%PROJECT_DIR:~-1%"=="\" set "PROJECT_DIR=%PROJECT_DIR:~0,-1%"

set "FRONTEND_DIR=%PROJECT_DIR%\frontend\civis-dashboard"
set "DIST_DIR=%FRONTEND_DIR%\dist"
set "REQ_FILE=%PROJECT_DIR%\requirements.txt"
set "CAMERA=0"
set "PORT=8000"
set "HOST=0.0.0.0"

echo   Project root : %PROJECT_DIR%
echo.

:: ============================================================================
::  STEP 0 - Kill stale processes on port 8000
:: ============================================================================
echo [STEP 0/6] Clearing stale processes on port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":%PORT% "') do (
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /IM python.exe /T >nul 2>&1
ping -n 2 127.0.0.1 >nul
echo   [OK] Port %PORT% cleared.
echo.

:: ============================================================================
::  STEP 1 - Find Python  (PATH first, then 20+ common install locations)
:: ============================================================================
echo [STEP 1/6] Locating Python...

set "PYTHON_CMD="

:: 1a. Already in PATH?
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :python_found
)

:: 1b. Try py launcher (Windows official installer)
py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :python_found
)

:: 1c. Common install directories
for %%D in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
    "C:\Python39\python.exe"
    "%PROGRAMFILES%\Python313\python.exe"
    "%PROGRAMFILES%\Python312\python.exe"
    "%PROGRAMFILES%\Python311\python.exe"
    "%PROGRAMFILES%\Python310\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python313\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python312\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
    "%USERPROFILE%\AppData\Local\Programs\Python\Python310\python.exe"
) do (
    if exist %%D (
        set "PYTHON_CMD=%%~D"
        goto :python_found
    )
)

:: 1d. Conda / Miniconda
for %%D in (
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "C:\ProgramData\miniconda3\python.exe"
    "C:\ProgramData\Anaconda3\python.exe"
    "%LOCALAPPDATA%\miniconda3\python.exe"
    "%LOCALAPPDATA%\anaconda3\python.exe"
) do (
    if exist %%D (
        set "PYTHON_CMD=%%~D"
        goto :python_found
    )
)

echo.
echo  [ERROR] Python 3.10+ was NOT found on this machine.
echo.
echo  Install from: https://www.python.org/downloads/
echo  Tick "Add Python to PATH" during installation, then re-run this script.
echo.
pause
exit /b 1

:python_found
echo   [OK] Python found  :  %PYTHON_CMD%
for /f "tokens=*" %%v in ('"%PYTHON_CMD%" --version 2^>^&1') do echo   [OK] Version       :  %%v
echo.

:: ============================================================================
::  STEP 2 - Locate pip  (bootstrap via ensurepip if missing)
:: ============================================================================
echo [STEP 2/6] Locating pip...
set "PIP_CMD=%PYTHON_CMD% -m pip"

%PIP_CMD% --version >nul 2>&1
if errorlevel 1 (
    echo   [!] pip missing - attempting bootstrap...
    "%PYTHON_CMD%" -m ensurepip --upgrade >nul 2>&1
    %PIP_CMD% --version >nul 2>&1
    if errorlevel 1 (
        echo  [ERROR] pip could not be bootstrapped.
        echo  Run manually:  %PYTHON_CMD% -m ensurepip
        pause
        exit /b 1
    )
)
echo   [OK] pip is available.
echo.

:: ============================================================================
::  STEP 3 - Install / verify Python dependencies
::  Reads requirements.txt; pip skips already-installed packages.
::  Safe to run OFFLINE if all packages are already installed.
:: ============================================================================
echo [STEP 3/6] Verifying Python dependencies...
echo   (Skips packages already installed - safe offline if previously set up)
echo.

if exist "%REQ_FILE%" (
    %PIP_CMD% install -r "%REQ_FILE%" --quiet --no-warn-script-location
    if errorlevel 1 (
        echo.
        echo   [WARN] Some packages failed. Retrying verbosely...
        %PIP_CMD% install -r "%REQ_FILE%" --no-warn-script-location
        if errorlevel 1 (
            echo.
            echo  [ERROR] Dependency installation failed.
            echo  Check internet connection or install manually:
            echo    %PIP_CMD% install -r "%REQ_FILE%"
            pause
            exit /b 1
        )
    )
) else (
    echo   [WARN] requirements.txt not found - installing core packages...
    %PIP_CMD% install "uvicorn[standard]" websockets fastapi opencv-python pydantic numpy ultralytics torch sahi supervision httpx --quiet --no-warn-script-location
)

echo   [OK] Python dependencies satisfied.
echo.

:: ============================================================================
::  STEP 4 - React frontend  (build only when dist is missing)
::  Does NOT re-run npm install if node_modules already exist.
:: ============================================================================
echo [STEP 4/6] Checking React dashboard build...

if not exist "%DIST_DIR%\index.html" (
    echo   [!] Dashboard not built - building now...

    set "NPM_CMD=npm"
    node --version >nul 2>&1
    if errorlevel 1 (
        :: Try common Node install paths
        set "NODE_FOUND=0"
        for %%D in (
            "C:\Program Files\nodejs\npm.cmd"
            "C:\Program Files (x86)\nodejs\npm.cmd"
            "%PROGRAMFILES%\nodejs\npm.cmd"
            "%LOCALAPPDATA%\Programs\nodejs\npm.cmd"
        ) do (
            if exist %%D (
                set "NPM_CMD=%%~D"
                set "NODE_FOUND=1"
                goto :node_found
            )
        )
        if "!NODE_FOUND!"=="0" (
            echo   [ERROR] Node.js not found. Install from: https://nodejs.org/
            pause
            exit /b 1
        )
    )

    :node_found
    pushd "%FRONTEND_DIR%"

    :: Only npm install when node_modules is missing
    if not exist "node_modules" (
        echo   Running npm install (first-time, needs internet)...
        call "!NPM_CMD!" install --silent
        if errorlevel 1 (
            echo  [ERROR] npm install failed.
            popd
            pause
            exit /b 1
        )
    )

    call "!NPM_CMD!" run build
    if errorlevel 1 (
        echo  [ERROR] Frontend build failed.
        popd
        pause
        exit /b 1
    )
    popd
    echo   [OK] Dashboard built successfully.
) else (
    echo   [OK] Dashboard build found - skipping rebuild.
)
echo.

:: ============================================================================
::  STEP 5 - GPU / CUDA status
:: ============================================================================
echo [STEP 5/6] GPU status...
echo ================================================================================
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>nul
if errorlevel 1 echo   GPU : Not detected / No NVIDIA driver
"%PYTHON_CMD%" -c "import torch; cuda=torch.cuda.is_available(); dev=torch.cuda.get_device_name(0) if cuda else 'N/A'; print(f'  PyTorch CUDA : {\"AVAILABLE\" if cuda else \"CPU-ONLY\"}  |  Device: {dev}')" 2>nul
echo ================================================================================
echo.

:: ============================================================================
::  STEP 6 - Launch CIVIS-CORE
:: ============================================================================
echo [STEP 6/6] Starting CIVIS-CORE backend + webcam pipeline...
echo.
echo   Console URL  :  http://localhost:%PORT%
echo   Live Stream  :  http://localhost:%PORT%/cameras/CAM_01/stream
echo   WebSocket    :  ws://localhost:%PORT%/ws/events
echo   API Docs     :  http://localhost:%PORT%/docs
echo.
echo   Press CTRL+C to stop all services.
echo.

:: Open browser 5 seconds after launch (non-blocking)
start /b cmd /c "ping -n 6 127.0.0.1 >nul && start http://localhost:%PORT%"

:: Change to project directory and run (blocking - keeps console open)
cd /d "%PROJECT_DIR%"
"%PYTHON_CMD%" run_civis.py --camera %CAMERA% --port %PORT% --host %HOST%

echo.
echo [CIVIS-CORE] Server stopped.
pause
