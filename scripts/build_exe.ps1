#!/usr/bin/env pwsh
param(
    [string]$SpecFile = "build/TRANSCRIBATORAUD.spec",
    [string]$OutputDir = "dist",
    [string]$VenvDir = ".venv"
)

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$specPath = Join-Path $ProjectRoot $SpecFile

if (-not (Test-Path $specPath)) {
    Write-Warning "Spec file $SpecFile not found; skipping PyInstaller build."
    exit 0
}

$venvPath = Join-Path $ProjectRoot $VenvDir
if (Test-Path $venvPath) {
    $activate = Join-Path $venvPath "Scripts/Activate.ps1"
    . $activate
}

pyinstaller --clean $specPath
New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $OutputDir) | Out-Null

$gitStatus = git -C $ProjectRoot status --short
if ($gitStatus) {
    Write-Warning "Build produced working tree changes. Verify that artefacts stay ignored."
}
