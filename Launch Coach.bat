@echo off
title VALORANT AI VOD COACH
cd /d "%~dp0"
python app.py
if errorlevel 1 (
    echo.
    echo Application exited with an error.
    pause
)
