@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title 420VaultBot Installer - Python 3.12

echo ============================================================
echo  420VaultBot - First-Time Windows Installer
echo  This installer requires Python 3.12 and will install it if needed.
echo ============================================================
echo.

call :find312
if defined PY312 goto :havepython

echo Python 3.12 was not found. Installing it with Windows Package Manager...
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo ERROR: winget is not available on this Windows installation.
  echo Install/update "App Installer" from Microsoft Store, then run install.bat again.
  pause
  exit /b 1
)
winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements --silent
if errorlevel 1 (
  echo.
  echo ERROR: Python 3.12 installation failed.
  pause
  exit /b 1
)
call :find312
if not defined PY312 (
  echo ERROR: Python 3.12 installed but could not be located. Close this window and run install.bat again.
  pause
  exit /b 1
)

:havepython
echo Using: %PY312%
if exist .venv\Scripts\python.exe (
  for /f "tokens=2" %%V in ('".venv\Scripts\python.exe" -c "import sys; print(str(sys.version_info.major)+'.'+str(sys.version_info.minor))" 2^>nul') do set VENVVER=%%V
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>nul
  if errorlevel 1 (
    echo Existing virtual environment is not Python 3.12. Rebuilding it...
    rmdir /s /q .venv
  )
)
if not exist .venv\Scripts\python.exe (
  echo Creating Python 3.12 virtual environment...
  %PY312% -m venv .venv
  if errorlevel 1 goto :fail
)

echo Bootstrapping pip...
.venv\Scripts\python.exe -m ensurepip --upgrade >nul 2>nul
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :fail

echo Installing 420VaultBot dependencies...
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo Starting 420VaultBot with Python 3.12...
.venv\Scripts\python.exe setup_and_start.py
set EXITCODE=%ERRORLEVEL%
echo.
echo 420VaultBot exited with code %EXITCODE%.
pause
exit /b %EXITCODE%

:find312
set PY312=
where py >nul 2>nul && py -3.12 -c "import sys; assert sys.version_info[:2]==(3,12)" >nul 2>nul && set "PY312=py -3.12"
if defined PY312 exit /b 0
for %%P in ("%LocalAppData%\Programs\Python\Python312\python.exe" "%ProgramFiles%\Python312\python.exe") do (
  if exist %%P set PY312=%%P
)
exit /b 0

:fail
echo.
echo ERROR: Installation failed. Scroll up for the first error message.
pause
exit /b 1
