@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" packaging\build_installer.py
if errorlevel 1 (
    echo Setup build failed. Read the message above.
    pause
    exit /b 1
)
pause
