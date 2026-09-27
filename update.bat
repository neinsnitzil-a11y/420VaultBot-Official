@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title 420VaultBot Universal Manual Updater
echo ============================================================
echo          420VaultBot UNIVERSAL MANUAL UPDATER
echo ============================================================
echo CURRENT BOT:
echo   %CD%
echo.
echo Select the NEW version, not this current installation.
echo Supports:
echo   - Full build ZIP
echo   - Extracted full build folder
echo   - Legacy manifest/payload release
echo.
set /p "SRC=NEW update ZIP/folder path: "
set "SRC=%SRC:"=%"
if not exist "%SRC%" (
  echo.
  echo ERROR: Path does not exist:
  echo %SRC%
  pause
  exit /b 2
)
echo.
py -3.12 --version >nul 2>nul
if not errorlevel 1 (
  py -3.12 update.py "%SRC%" --install-dir "%CD%"
) else (
  python update.py "%SRC%" --install-dir "%CD%"
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Finished. You can start 420VaultBot normally.
) else (
  echo Update failed. Read the error above.
)
pause
exit /b %RC%
