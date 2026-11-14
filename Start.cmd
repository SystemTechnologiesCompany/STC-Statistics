@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Run Setup.cmd first. / Lancez Setup.cmd d'abord.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import PySide6, pandas, numpy, matplotlib, openpyxl, xlrd, ipykernel, jupyter_client, nbformat" >nul 2>&1
if errorlevel 1 (
    echo Run Setup.cmd to finish installation. / Lancez Setup.cmd pour terminer l'installation.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
