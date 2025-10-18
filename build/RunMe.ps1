# encoding: utf-8
<#
TRANSCRIBATORAUD — one-click builder
Правит venv, зависимости, ffmpeg и собирает EXE через PyInstaller.
#>
[CmdletBinding()]
param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

function Get-Python312Path {
    $candidates = @(
        @{ Cmd = "py"; Args = @("-3.12") },
        @{ Cmd = "python"; Args = @() },
        @{ Cmd = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $args = @()
            $args += $candidate.Args
            $args += @("-c", "import sys; assert sys.version_info[:2] == (3, 12); print(sys.executable)")
            $exe = & $candidate.Cmd @args
            if ($LASTEXITCODE -eq 0 -and $exe) {
                return $exe.Trim()
            }
        } catch {
            continue
        }
    }

    throw "Python 3.12 from python.org is required. Install it and ensure 'py -3.12' or 'python' points to that interpreter. Conda distributions are not supported."
}

if ($Clean) {
    Write-Host "Cleaning previous artefacts..."
    @(".venv", "dist", "build/output", "build/cache") | ForEach-Object {
        $target = Join-Path $ProjectRoot $_
        if (Test-Path $target) {
            Remove-Item -Recurse -Force $target
        }
    }
}

$pythonPath = Get-Python312Path

Write-Host "Using Python interpreter: $pythonPath"

$bootstrap = Join-Path $ProjectRoot "scripts/bootstrap.ps1"

& $bootstrap -PythonBin $pythonPath

Write-Host "Build complete. EXE artefacts remain under dist/ and must not be committed to git."
