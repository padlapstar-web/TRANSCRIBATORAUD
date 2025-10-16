@echo off
setlocal
REM One-click entry point: invoke PowerShell helper bypassing execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0RunMe.ps1"
if errorlevel 1 (
  echo Build failed. See build\build.log (if present).
  exit /b 1
)
echo OK
