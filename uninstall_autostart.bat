@echo off
rem ==========================================================================
rem  Disable auto-start and stop the background bot if it is running.
rem ==========================================================================
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DiscordAIBot.lnk"

if exist "%SHORTCUT%" (
    del "%SHORTCUT%"
    echo [OK] Auto-start disabled.
) else (
    echo Auto-start was not enabled.
)

choice /c YN /m "Also stop the running background bot now"
if errorlevel 2 goto end
call "%~dp0stop_bot.bat" nopause

:end
pause
