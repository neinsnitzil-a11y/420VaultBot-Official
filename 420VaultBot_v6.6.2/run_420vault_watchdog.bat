@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "BOTVER=unknown"
if exist "VERSION" set /p BOTVER=<VERSION
title 420VaultBot v%BOTVER% Watchdog

if not exist "logs" mkdir "logs" >nul 2>nul
set "WATCHLOG=%~dp0logs\watchdog.log"

echo [%date% %time%] Watchdog started.>>"%WATCHLOG%"
echo 420VaultBot v%BOTVER% Watchdog
echo Launch folder: %CD%
echo Log: %WATCHLOG%
echo.

:restart
call :log Starting 420VaultBot process...

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_and_start.py
) else (
  python setup_and_start.py
)
set "EXITCODE=%ERRORLEVEL%"

call :log Bot process exited with code %EXITCODE%.
call :log Restarting automatically in 3 seconds. No keyboard input required.
rem Non-interactive delay: no PAUSE and no "Press any key to continue" prompt.
ping 127.0.0.1 -n 4 >nul
goto restart

:log
echo [%date% %time%] %*
echo [%date% %time%] %*>>"%WATCHLOG%"
exit /b 0
