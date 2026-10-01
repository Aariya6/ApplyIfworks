@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_windows.bat first.
  pause
  exit /b 1
)
echo Remote Job Pilot: live watch mode.
echo Keep this window open. It rechecks every 20 minutes for as long as it runs and pops a
echo desktop notification when a new QUALIFIED or TRANSFERABLE job shows up. Close this window
echo (or Ctrl+C) to stop watching -- nothing runs once it's closed.
".venv\Scripts\python.exe" -m app.cli watch --minutes 20
pause
