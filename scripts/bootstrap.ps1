#requires -version 5.1
[CmdletBinding()]
param(
    [string]$PythonBin = 'python',
    [string]$VenvDir = '.venv'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot '..')

$version = & $PythonBin -c "import sys; print('.'.join(map(str, sys.version_info[:2])))"
if ($LASTEXITCODE -ne 0 -or $version -ne '3.12') {
    Write-Error "Python 3.12 interpreter ('$PythonBin') is required."
    exit 1
}

$venvPath = Join-Path $ProjectRoot $VenvDir
if (-not (Test-Path $venvPath)) {
    & $PythonBin -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$activate = Join-Path $venvPath 'Scripts/Activate.ps1'
. $activate

python -m pip install --upgrade pip
if (Test-Path (Join-Path $ProjectRoot 'requirements.txt')) {
    python -m pip install -r (Join-Path $ProjectRoot 'requirements.txt')
}
python -m pip install --upgrade pyinstaller

$buildScript = Join-Path $ProjectRoot 'scripts/build_exe.ps1'
& $buildScript -SpecFile 'build/TRANSCRIBATORAUD.spec' -VenvDir $VenvDir
