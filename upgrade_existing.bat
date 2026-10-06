@echo off
setlocal
set /p BOT_ROOT=Enter EXISTING bot installation directory: 
if "%BOT_ROOT%"=="" (echo No directory supplied. & pause & exit /b 1)
echo.
echo === Upgrade preflight (dry run) ===
py -3.12 "%~dp0upgrade_existing.py" "%BOT_ROOT%" --dry-run > "%TEMP%\420vault_upgrade_preflight.log" 2>&1
if errorlevel 1 (
  type "%TEMP%\420vault_upgrade_preflight.log"
  echo Upgrade blocked; installation unchanged.
  pause & exit /b 1
)
for /f "tokens=*" %%A in ('findstr /C:"420VaultBot upgrade:" "%TEMP%\420vault_upgrade_preflight.log"') do echo %%A
for /f "tokens=*" %%A in ('findstr /C:"USER DATA EXCLUDED:" "%TEMP%\420vault_upgrade_preflight.log"') do echo %%A
set /p CONFIRM=STOP YOUR BOT FIRST. Type UPDATE to continue: 
if /i not "%CONFIRM%"=="UPDATE" (echo Cancelled. & pause & exit /b 0)
py -3.12 "%~dp0upgrade_existing.py" "%BOT_ROOT%"
if errorlevel 1 (
  echo Python 3.12 launcher failed or upgrade blocked; check errors above.
  pause & exit /b 1
)
pause
