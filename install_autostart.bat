@echo off
rem ==========================================================================
rem  Enable auto-start: puts a shortcut to start_run.vbs into the current
rem  user's Startup folder, so the bot runs hidden in the background after
rem  every login. No administrator rights required.
rem ==========================================================================
cd /d "%~dp0"
set "SHORTCUT=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DiscordAIBot.lnk"

if "%DISCORD_TOKEN%"=="" (
    echo DISCORD_TOKEN is not set as a permanent user environment variable.
    echo The bot needs it to start after reboot.
    set /p "TOKEN_INPUT=Paste your Discord bot token (leave empty to skip): "
)
if "%DISCORD_TOKEN%"=="" if not "%TOKEN_INPUT%"=="" (
    setx DISCORD_TOKEN "%TOKEN_INPUT%" > nul
    set "DISCORD_TOKEN=%TOKEN_INPUT%"
    echo DISCORD_TOKEN saved to user environment variables.
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:SHORTCUT);" ^
  "$s.TargetPath = 'wscript.exe';" ^
  "$s.Arguments = '\"%~dp0start_run.vbs\"';" ^
  "$s.WorkingDirectory = '%~dp0';" ^
  "$s.Description = 'Discord AI Bot (background)';" ^
  "$s.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo [OK] Auto-start enabled: %SHORTCUT%
    echo The bot will start in the background 2 minutes after every login.
    echo Logs: %~dp0logs\bot.log
    echo.
    choice /c YN /m "Start the bot in the background now"
    if not errorlevel 2 wscript.exe "%~dp0start_run.vbs" nodelay
) else (
    echo [FAILED] Could not create the Startup shortcut.
)
pause
