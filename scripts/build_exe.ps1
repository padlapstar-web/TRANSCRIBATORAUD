#requires -version 5.1
[CmdletBinding()]
param(
    [string]$SpecFile = 'build/TRANSCRIBATORAUD.spec',
    [string]$OutputDir = 'dist',
    [string]$VenvDir = '.venv'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$specPath = Join-Path $ProjectRoot $SpecFile

if (-not (Test-Path $specPath)) {
    Write-Warning "Spec file $SpecFile not found; skipping PyInstaller build."
    return
}

$venvPath = Join-Path $ProjectRoot $VenvDir
if (Test-Path $venvPath) {
    $activate = Join-Path $venvPath 'Scripts/Activate.ps1'
    . $activate
}

$env:PYI_PROJECT_ROOT = $ProjectRoot
$env:PYI_SPEC_DIR = (Resolve-Path (Join-Path $ProjectRoot 'build')).Path

& python -m PyInstaller --clean $specPath
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

New-Item -ItemType Directory -Force -Path (Join-Path $ProjectRoot $OutputDir) | Out-Null

$distTarget = Join-Path (Join-Path $ProjectRoot $OutputDir) 'TRANSCRIBATORAUD'
$postCopy = Join-Path $PSScriptRoot 'post_build_copy_ffmpeg.ps1'
if (Test-Path $distTarget -PathType Container -ErrorAction SilentlyContinue) {
    & $postCopy -DistDir $distTarget
} else {
    Write-Warning "Каталог $distTarget не найден после сборки"
}

$gitStatus = git -C $ProjectRoot status --short
if ($gitStatus) {
    Write-Warning 'Build produced working tree changes. Verify that artefacts stay ignored.'
}
