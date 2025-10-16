#Requires -Version 5.1
[CmdletBinding()]
Param([switch]$Clean)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function New-PyInvoker {
    param(
        [string]$Command,
        [string[]]$Arguments
    )

    return {
        param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
        & $Command @Arguments @Args
    }.GetNewClosure()
}

function Get-Py {
    $candidates = @(
        New-PyInvoker -Command "py" -Arguments @("-3.12"),
        New-PyInvoker -Command "py" -Arguments @("-3.11"),
        New-PyInvoker -Command "py" -Arguments @("-3.10"),
        New-PyInvoker -Command "python" -Arguments @()
    )

    foreach ($candidate in $candidates) {
        try {
            & $candidate "-c" "import sys" 2>$null
            if ($LASTEXITCODE -eq 0) { return $candidate }
        } catch {}
    }

    throw "Python 3.10-3.12 not found"
}

$root = (Resolve-Path "$PSScriptRoot\..\").Path
Set-Location $root

if ($Clean.IsPresent) {
    Remove-Item -Recurse -Force .venv, "build\pyinstaller", dist, build\*.log, build\cache -ErrorAction SilentlyContinue
}

$PY = Get-Py
$pythonPath = (& $PY "-c" "import pathlib, sys; print(pathlib.Path(sys.executable).resolve())" 2>$null).Trim()
Write-Host ("Using interpreter: " + $pythonPath)

& $PY "-m" "venv" ".venv"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path $venvPython)) { throw "Missing .\\.venv\\Scripts\\python.exe" }

& $venvPython "-m" "pip" "install" "--upgrade" "pip"
& $venvPython "-m" "pip" "install" "-r" "requirements.txt"
& $venvPython "-m" "pip" "install" "pyinstaller"

. "$PSScriptRoot\Ensure-FFmpeg.ps1"
Ensure-FFmpeg -OutDir (Join-Path $root "resources\ffmpeg")

$ffDir = Join-Path $root "resources\ffmpeg"
if (!(Test-Path (Join-Path $ffDir "ffmpeg.exe")) -or !(Test-Path (Join-Path $ffDir "ffprobe.exe"))) {
    throw "FFmpeg not prepared in resources\\ffmpeg"
}
$env:PATH = "$ffDir;$env:PATH"

$pyinstallerExe = Join-Path $root ".venv\Scripts\pyinstaller.exe"
if (!(Test-Path $pyinstallerExe)) { throw "PyInstaller executable not found" }

& $pyinstallerExe "--noconfirm" "--clean" "--workpath" ".\build\pyinstaller" "--distpath" ".\dist" ".\build\TRANSCRIBATORAUD.spec" |
    Tee-Object -FilePath .\build\build.log
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed. See build\\build.log"
}

$exe = Join-Path $root "dist\TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
if (!(Test-Path $exe)) {
    throw "EXE not found after build"
}

Write-Host "READY: $exe"
Write-Host "Run:   `"$exe`" --help"
