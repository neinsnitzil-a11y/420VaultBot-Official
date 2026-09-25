@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo 420VaultBot is not installed yet. Running the first-time installer...
  call install.bat
  exit /b %ERRORLEVEL%
)
.venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>nul
if errorlevel 1 (
  echo The existing environment is not Python 3.12. Running installer to rebuild it...
  call install.bat
  exit /b %ERRORLEVEL%
)
.venv\Scripts\python.exe setup_and_start.py
pause
