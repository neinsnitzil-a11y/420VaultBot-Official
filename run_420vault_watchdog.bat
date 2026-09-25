@echo off
setlocal
cd /d "%~dp0"
title 420VaultBot v5.8.2 Watchdog
:restart
python -m app.bot
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] 420VaultBot exited with code %EXITCODE%. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto restart
