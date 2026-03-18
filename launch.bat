@echo off
title Nexus
chcp 65001 >nul 2>&1
set "NEXUS_HOME=%USERPROFILE%\nexus"
set "PYTHONIOENCODING=utf-8"

:: Prefer Windows Terminal for truecolor, fall back to current console
where wt.exe >nul 2>&1
if %ERRORLEVEL%==0 (
    wt.exe -p "Command Prompt" --title Nexus cmd /k "chcp 65001 >nul & python \"%~dp0nexus_ui.py\" \"%USERPROFILE%\Downloads\Gemini_Generated_Image_bcbirqbcbirqbcbi.png\""
    exit
)

python "%~dp0nexus_ui.py" "%USERPROFILE%\Downloads\Gemini_Generated_Image_bcbirqbcbirqbcbi.png"
pause
