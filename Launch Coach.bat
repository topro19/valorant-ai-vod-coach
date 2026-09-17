@echo off
title VALORANT AI VOD COACH
color 0C
cd /d "%~dp0"

:: Add local bin folder to PATH if it exists (for portable FFmpeg)
if exist "bin" (
    set "PATH=%~dp0bin;%PATH%"
)

:: Select Python interpreter
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
) else (
    python -c "import webview, fastapi" >nul 2>&1
    if %errorlevel% equ 0 (
        set "PY_EXE=python"
    ) else (
        echo [!] Required dependencies not found.
        echo Starting 1-Click Setup...
        call "Setup.bat"
        exit /b 0
    )
)

"%PY_EXE%" app.py
if %errorlevel% neq 0 (
    echo.
    echo =========================================================
    echo Application exited. If you encountered an error,
    echo try running "Setup.bat" to verify all dependencies.
    echo =========================================================
    pause
)
