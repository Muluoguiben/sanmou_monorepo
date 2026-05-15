@echo off
setlocal

set "SCRIPT=\\wsl.localhost\Ubuntu\home\lan\projects\sanmou_monorepo\.agent\skills\sanmou-client-control\scripts\sanmou_client_control.ps1"
set "STATUS=%TEMP%\sanmou_install_controller_task_status.json"

del "%STATUS%" >nul 2>nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" install-controller-task -StatusPath "%STATUS%"

echo.
echo === SanmouController install status ===
if exist "%STATUS%" (
  type "%STATUS%"
) else (
  echo No status file was written. Make sure this file was run as administrator.
)
echo.
pause
