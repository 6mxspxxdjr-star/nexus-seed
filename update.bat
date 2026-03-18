@echo off
title Nexus Updater
set "NEXUS_HOME=%USERPROFILE%\nexus"
"%NEXUS_HOME%\.venv\Scripts\python.exe" "%NEXUS_HOME%\scripts\update.py" %*
pause
