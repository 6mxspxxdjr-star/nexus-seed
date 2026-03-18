@echo off
title Nexus
chcp 65001 >nul 2>&1
set "NEXUS_HOME=%USERPROFILE%\nexus"
set "PYTHONIOENCODING=utf-8"

:: Check for --dashboard flag: launch dashboard alongside terminal UI
set "LAUNCH_DASH=0"
for %%a in (%*) do (
    if "%%a"=="--dashboard" set "LAUNCH_DASH=1"
)

if "%LAUNCH_DASH%"=="1" (
    start "" /B python "%~dp0nexus_dashboard.py" --port 3800 >nul 2>&1
)

:: Prefer Windows Terminal for truecolor, fall back to current console
where wt.exe >nul 2>&1
if %ERRORLEVEL%==0 (
    wt.exe -p "Command Prompt" --title Nexus cmd /k "chcp 65001 >nul & python \"%~dp0nexus_ui.py\" \"%USERPROFILE%\Downloads\Gemini_Generated_Image_bcbirqbcbirqbcbi.png\""
    exit
)

python "%~dp0nexus_ui.py" "%USERPROFILE%\Downloads\Gemini_Generated_Image_bcbirqbcbirqbcbi.png"
pause
