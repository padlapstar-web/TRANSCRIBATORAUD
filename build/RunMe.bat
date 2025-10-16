@echo off
setlocal
set PS=%~dp0RunMe.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%"
if errorlevel 1 (
  echo Build failed. See build\build.log (if present).
  exit /b 1
)
echo OK
