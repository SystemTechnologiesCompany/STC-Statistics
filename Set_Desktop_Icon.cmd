@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Set_Desktop_Icon.ps1"
if errorlevel 1 (
    echo Desktop icon update failed. Please keep these files in the STC Statistics project folder.
    pause
    exit /b 1
)
pause
