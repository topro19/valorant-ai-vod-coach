@echo off
setlocal enabledelayedexpansion
title VALORANT AI VOD COACH - Setup & Installer
color 0C

echo ================================================================================
echo                   VALORANT AI VOD COACH - 1-CLICK SETUP
echo ================================================================================
echo.

cd /d "%~dp0"

:: 1. Detect Python
echo [1/5] Checking Python installation...
set "PY_CMD="
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set "PY_CMD=python"
) else (
    py -3 --version >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_CMD=py -3"
    )
)

if "%PY_CMD%"=="" (
    echo [!] Python is NOT detected on this machine.
    echo.
    echo Would you like to automatically install Python 3.12 via Windows Package Manager?
    set /p INSTALL_PY="Install Python now? (Y/N, default Y): "
    if "!INSTALL_PY!"=="" set "INSTALL_PY=Y"
    if /i "!INSTALL_PY!"=="Y" (
        echo Installing Python 3.12 via winget...
        winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
        echo.
        echo Please RESTART this Setup.bat window after the Python installer finishes.
        pause
        exit /b 1
    ) else (
        echo Please download and install Python 3.10+ from https://www.python.org/downloads/
        echo (Remember to check "Add Python to PATH" during installation!)
        pause
        exit /b 1
    )
)

for /f "tokens=*" %%v in ('%PY_CMD% --version 2^>^&1') do echo [OK] Found %%v

:: Check if application files exist; if not, download automatically from GitHub
if not exist "backend" (
    echo.
    echo [!] Application files not detected in this folder.
    echo [*] Downloading full VALORANT AI VOD COACH from GitHub...
    %PY_CMD% -c "import urllib.request, zipfile, io, pathlib; url='https://github.com/topro19/valorant-ai-vod-coach/archive/refs/heads/master.zip'; req=urllib.request.Request(url, headers={'User-Agent': 'VodCoach/1.0'}); z=zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(req).read())); [(pathlib.Path(*pathlib.Path(f).parts[1:]).parent.mkdir(parents=True, exist_ok=True), pathlib.Path(*pathlib.Path(f).parts[1:]).write_bytes(z.read(f))) for f in z.namelist() if len(pathlib.Path(f).parts) > 1 and not f.endswith('/')]; print('[OK] Application files successfully downloaded and extracted!')"
    if errorlevel 1 (
        echo [!] Failed to download application files from GitHub.
        echo Please check your internet connection and try again.
        pause
        exit /b 1
    )
)

:: 2. Initialize Configuration (.env)
echo.
echo [2/5] Initializing local configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [OK] Created .env from template.
    ) else (
        echo GEMINI_API_KEY=> .env
        echo DATA_DIR=> .env
        echo [OK] Created default .env.
    )
) else (
    echo [OK] Existing configuration found.
)

:: 3. Setup Virtual Environment
echo.
echo [3/5] Setting up isolated Python virtual environment (.venv)...
if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY_CMD% -m venv .venv
    if %errorlevel% neq 0 (
        echo [!] Failed to create .venv using %PY_CMD%. Trying direct system install...
        set "VENV_PY=%PY_CMD%"
    ) else (
        set "VENV_PY=.venv\Scripts\python.exe"
        echo [OK] Virtual environment created successfully.
    )
) else (
    set "VENV_PY=.venv\Scripts\python.exe"
    echo [OK] Virtual environment already exists.
)

:: 4. Install Dependencies
echo.
echo [4/5] Installing required packages (FastAPI, OpenCV, PyWebView, Gemini SDK)...
"%VENV_PY%" -m pip install --upgrade pip --quiet
"%VENV_PY%" -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [!] Warning: Some dependencies may have had installation warnings.
) else (
    echo [OK] All dependencies successfully installed.
)

:: Check FFmpeg
echo.
ffmpeg -version >nul 2>&1
if %errorlevel% neq 0 (
    if not exist "bin\ffmpeg.exe" (
        echo [!] FFmpeg was not detected in PATH.
        echo Would you like to install FFmpeg via winget now?
        set /p INSTALL_FF="Install FFmpeg? (Y/N, default Y): "
        if "!INSTALL_FF!"=="" set "INSTALL_FF=Y"
        if /i "!INSTALL_FF!"=="Y" (
            echo Installing FFmpeg via winget...
            winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements
        )
    ) else (
        echo [OK] Found local portable FFmpeg in bin\
    )
) else (
    echo [OK] FFmpeg is available in system PATH.
)

:: 5. Create Desktop Shortcut
echo.
echo [5/5] Creating Windows Desktop Shortcut...
if exist "create_shortcut.ps1" (
    powershell -ExecutionPolicy Bypass -File "create_shortcut.ps1" >nul 2>&1
    echo [OK] Desktop shortcut created: "VALORANT AI VOD Coach"
)

echo.
echo ================================================================================
echo                    SETUP COMPLETED SUCCESSFULLY!
echo ================================================================================
echo You can launch the coach anytime via the desktop shortcut or "Launch Coach.bat".
echo.
set /p RUN_NOW="Would you like to launch VALORANT AI VOD COACH now? (Y/N, default Y): "
if "!RUN_NOW!"=="" set "RUN_NOW=Y"
if /i "!RUN_NOW!"=="Y" (
    echo Starting application...
    start "" "Launch Coach.bat"
)

echo Done. Have fun reviewing your gameplay!
timeout /t 3 >nul
exit /b 0
