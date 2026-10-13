@echo off
rem ==========================================================================
rem  Stop the background bot (the restart loop in run_background.bat and
rem  the python process running discord_ai.py).
rem ==========================================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*run_background.bat*' -or ($_.Name -like 'python*.exe' -and $_.CommandLine -like '*discord_ai.py*')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped PID ' + $_.ProcessId) }"
echo Background bot stopped.
if /i not "%~1"=="nopause" pause
