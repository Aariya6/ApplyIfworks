@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3 -m venv .venv
  if errorlevel 1 python -m venv .venv
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -e .
python -m playwright install chromium
if not exist ".env" copy /Y .env.example .env >nul
if not exist "config\company_universe.csv" copy /Y config\company_universe.example.csv config\company_universe.csv >nul
python -m app.cli init
python -m app.cli seed-qna
python -m app.cli seed-companies
python -m app.cli setup
pause
