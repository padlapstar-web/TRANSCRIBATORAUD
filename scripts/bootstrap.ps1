#!/usr/bin/env pwsh
param(
    [string]$PythonBin = "python",
    [string]$VenvDir = ".venv"
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

$version = & $PythonBin -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or $version -ne "3.12") {
    Write-Error "Python 3.12 interpreter ('$PythonBin') is required."
    exit 1
}

$venvPath = Join-Path $ProjectRoot $VenvDir
if (-not (Test-Path $venvPath)) {
    & $PythonBin -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$activate = Join-Path $venvPath "Scripts/Activate.ps1"
. $activate

python -m pip install --upgrade pip
if (Test-Path (Join-Path $ProjectRoot "requirements.txt")) {
    python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
}
python -m pip install --upgrade pyinstaller

python (Join-Path $ProjectRoot "scripts/fetch_assets.py")

pwsh (Join-Path $ProjectRoot "scripts/build_exe.ps1")
