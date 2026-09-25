@echo off
setlocal
cd /d "%~dp0"
:restart
py -3.12 main.py
set EXITCODE=%ERRORLEVEL%
echo [%date% %time%] 420VaultBot exited with code %EXITCODE%. Restarting in 10 seconds...
timeout /t 10 /nobreak >nul
goto restart
