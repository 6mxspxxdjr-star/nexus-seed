@echo off
title Nexus Dashboard
chcp 65001 >nul 2>&1
set "NEXUS_HOME=%USERPROFILE%\nexus"
set "PYTHONIOENCODING=utf-8"

echo.
echo   Starting Nexus Dashboard...
echo   http://127.0.0.1:3800
echo.

python "%~dp0nexus_dashboard.py" --port 3800 %*
pause
