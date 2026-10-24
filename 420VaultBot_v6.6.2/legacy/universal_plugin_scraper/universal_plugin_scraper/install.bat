@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt || goto :err
python -m playwright install chromium || goto :err
echo.
echo Installation complete.
pause
exit /b 0
:err
echo.
echo Installation failed. Make sure Python 3.10+ is installed and on PATH.
pause
exit /b 1
