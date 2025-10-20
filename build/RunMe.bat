@echo off
setlocal enabledelayedexpansion
set SCRIPT_DIR=%~dp0
set POWERSHELL=powershell.exe

%POWERSHELL% -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%RunMe.ps1" %*
if errorlevel 1 exit /b %errorlevel%

endlocal
