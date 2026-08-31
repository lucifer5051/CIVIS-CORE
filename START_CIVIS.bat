@echo off
setlocal enabledelayedexpansion
title CIVIS-CORE Operator Console Launcher

echo.
echo ================================================================================
echo   CIVIS-CORE  ^|  LIVE SURVEILLANCE OPERATOR CONSOLE
echo ================================================================================
echo.

:: ── Configuration ────────────────────────────────────────────────────────────
set "PROJECT_DIR=%~dp0"
set "FRONTEND_DIR=%PROJECT_DIR%frontend\civis-dashboard"
set "CAMERA=0"
set "PORT=8000"
set "HOST=0.0.0.0"

:: ── Step 1: Kill any stale Python / uvicorn processes on port 8000 ──────────
echo [1/5] Stopping any existing CIVIS processes...
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /F /PID %%a >nul 2>&1
)
taskkill /F /IM python.exe /T >nul 2>&1
ping -n 2 127.0.0.1 >nul

:: ── Step 2: Verify Python ────────────────────────────────────────────────────
echo [2/5] Checking Python environment...
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found in PATH. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

:: ── Step 3: Install required pip packages (fast, skips if already present) ──
echo [3/5] Verifying Python dependencies...
pip install "uvicorn[standard]" websockets fastapi --quiet --no-warn-script-location 2>nul

:: ── Step 4: Build frontend if needed ─────────────────────────────────────────
echo [4/5] Checking React dashboard build...
if not exist "%FRONTEND_DIR%\dist\index.html" (
    echo  [!] Dashboard not built. Building now (requires Node.js)...
    pushd "%FRONTEND_DIR%"
    call npm install --silent
    call npm run build
    if errorlevel 1 (
        echo  [ERROR] Frontend build failed. Check Node.js installation.
        popd
        pause
        exit /b 1
    )
    popd
    echo  [OK] Dashboard built successfully.
) else (
    echo  [OK] Dashboard build found.
)

:: ── Step 5: Check NVIDIA GPU ─────────────────────────────────────────────────
echo.
echo ================================================================================
echo   GPU STATUS
echo ================================================================================
nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>nul
if errorlevel 1 (
    echo   GPU : Not detected / No NVIDIA driver
) 
python -c "import torch; cuda=torch.cuda.is_available(); dev=torch.cuda.get_device_name(0) if cuda else 'N/A'; print(f'  PyTorch CUDA : {\"AVAILABLE\" if cuda else \"CPU-ONLY (install CUDA torch to enable)\"}'); print(f'  Device       : {dev}')" 2>nul
echo ================================================================================
echo.

:: ── Launch CIVIS-CORE ────────────────────────────────────────────────────────
echo [5/5] Starting CIVIS-CORE backend + webcam pipeline...
echo.
echo   Console URL  :  http://localhost:%PORT%
echo   Live Stream  :  http://localhost:%PORT%/cameras/CAM_01/stream
echo   WebSocket    :  ws://localhost:%PORT%/ws/events
echo   API Docs     :  http://localhost:%PORT%/docs
echo.
echo   Press CTRL+C to stop all services.
echo.

:: Open browser after 4s in background
start /b cmd /c "ping -n 5 127.0.0.1 >nul && start http://localhost:%PORT%"

:: Run CIVIS (blocking — keeps console open)
cd /d "%PROJECT_DIR%"
python run_civis.py --camera %CAMERA% --port %PORT% --host %HOST%

echo.
echo [CIVIS-CORE] Server stopped.
pause
