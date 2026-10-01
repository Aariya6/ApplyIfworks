@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Run install_windows.bat first.
  exit /b 1
)
".venv\Scripts\python.exe" -m app.cli discover >> "data\daily_scrape.log" 2>&1
".venv\Scripts\python.exe" -m app.cli score >> "data\daily_scrape.log" 2>&1
".venv\Scripts\python.exe" -m app.cli company-fit >> "data\daily_scrape.log" 2>&1
".venv\Scripts\python.exe" -m app.cli skill-gaps >> "data\daily_scrape.log" 2>&1
echo [%date% %time%] daily scrape + score + company-fit + skill-gaps complete >> "data\daily_scrape.log"
