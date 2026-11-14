@echo off
cd /d "%~dp0"
".venv\Scripts\python.exe" packaging\build_portable.py
if errorlevel 1 exit /b 1
pause
