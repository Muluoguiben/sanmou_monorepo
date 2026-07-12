@echo off
setlocal

set "SCRIPT=%~dp0sanmou_client_control.ps1"
set "CONTROL_DIR=%LOCALAPPDATA%\SanmouClientControl"
set "LOCAL_SCRIPT=%CONTROL_DIR%\sanmou_client_control.ps1"
set "STATUS=%TEMP%\sanmou_install_controller_task_status.json"

net session >nul 2>&1
if %errorLevel% neq 0 (
  echo Requesting Administrator permission to install SanmouController...
  powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

if not exist "%CONTROL_DIR%" mkdir "%CONTROL_DIR%"
copy /Y "%SCRIPT%" "%LOCAL_SCRIPT%" >nul
if %errorLevel% neq 0 (
  echo [ERROR] Failed to copy controller script:
  echo   from: %SCRIPT%
  echo   to:   %LOCAL_SCRIPT%
  pause
  exit /b 2
)

del "%STATUS%" >nul 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%LOCAL_SCRIPT%" install-controller-task -StatusPath "%STATUS%"

echo.
echo === SanmouController install status ===
if exist "%STATUS%" (
  type "%STATUS%"
) else (
  echo No status file was written. Make sure this file was run as administrator.
)
echo.
pause
