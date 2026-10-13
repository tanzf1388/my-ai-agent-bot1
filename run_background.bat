@echo off
rem ==========================================================================
rem  Background runner for discord_ai.py (no window, no pause).
rem  - Runs from this script's own folder (no hard-coded path)
rem  - Writes all output to logs\bot.log
rem  - Restarts the bot automatically if it crashes
rem  Normally launched hidden by start_run.vbs; do not double-click unless
rem  you want to watch it in a console.
rem ==========================================================================
cd /d "%~dp0"
if not exist "logs" mkdir "logs"

rem Force UTF-8 so emoji / Chinese output does not crash when redirected to a file
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

:loop
echo [%date% %time%] Starting discord_ai.py >> "logs\bot.log"
python discord_ai.py >> "logs\bot.log" 2>&1
echo [%date% %time%] discord_ai.py exited with code %errorlevel%, restarting in 15 seconds >> "logs\bot.log"
timeout /t 15 /nobreak > nul
goto loop
