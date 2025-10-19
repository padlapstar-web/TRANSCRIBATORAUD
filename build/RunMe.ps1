# encoding: utf-8
#requires -version 5.1
<#
TRANSCRIBATORAUD — one-click builder
Правит venv, зависимости, ffmpeg и собирает EXE через PyInstaller.
#>
[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$NoSyntaxCheck,
    [switch]$KillApp
)

function Clear-ReadOnlyAttributes {
    param([string] $Path)
    if (Test-Path $Path) {
        Get-ChildItem -Path $Path -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                if ($_.Attributes -band [IO.FileAttributes]::ReadOnly) {
                    $_.Attributes = $_.Attributes -bxor [IO.FileAttributes]::ReadOnly
                }
            } catch {}
        }
    }
}

function Remove-Path-Retry {
    param(
        [Parameter(Mandatory=$true)][string] $Path,
        [int] $MaxRetries = 15,
        [int] $DelaySec = 1
    )
    if (-not (Test-Path $Path)) { return }
    Clear-ReadOnlyAttributes -Path $Path

    for ($i=1; $i -le $MaxRetries; $i++) {
        try {
            Remove-Item -Recurse -Force -LiteralPath $Path -ErrorAction Stop
            return
        } catch {
            Write-Host "[$i/$MaxRetries] '$Path' still locked. Waiting $DelaySec s..." -ForegroundColor Yellow
            Start-Sleep -Seconds $DelaySec
        }
    }
    throw "Could not delete '$Path' - files are locked."
}

function Stop-RunningApp {
    param(
        [Parameter(Mandatory=$true)][string]$DistDir,
        [int]$Rounds = 3,
        [int]$WaitMs = 800
    )

    $distGlob = ($DistDir.TrimEnd('\') + '\*')
    for ($i = 1; $i -le $Rounds; $i++) {
        $procs = Get-CimInstance Win32_Process |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like $distGlob }

        if (-not $procs) { return $true }

        Write-Host "Found running instances under $DistDir (round $i/$Rounds). Trying to stop..."

        foreach ($p in $procs) {
            try {
                $ps = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
                if ($ps) {
                    [void]$ps.CloseMainWindow()
                }
            } catch {}
        }
        Start-Sleep -Milliseconds $WaitMs

        foreach ($p in $procs) {
            try { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue } catch {}
        }
        Start-Sleep -Milliseconds $WaitMs

        foreach ($p in $procs) {
            try {
                & taskkill.exe /PID $p.ProcessId /F /T | Out-Null
            } catch {}
        }

        $deadline = (Get-Date).AddSeconds(3)
        while ((Get-Date) -lt $deadline) {
            $still = Get-CimInstance Win32_Process |
                Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like $distGlob }
            if (-not $still) { break }
            Start-Sleep -Milliseconds 250
        }

        $left = Get-CimInstance Win32_Process |
            Where-Object { $_.ExecutablePath -and $_.ExecutablePath -like $distGlob }
        if (-not $left) {
            Write-Host "All running instances were terminated."
            return $true
        }
    }

    Write-Warning "Running app instances are still alive after $Rounds rounds."
    return $false
}

function Resolve-PowerShell {
    try {
        (Get-Command pwsh -ErrorAction Stop).Source
    } catch {
        (Get-Command powershell -ErrorAction Stop).Source
    }
}

$PSExe = Resolve-PowerShell

function Invoke-PS {
    param(
        [string]$Command
    )

    & $PSExe -NoProfile -ExecutionPolicy Bypass -Command $Command
}

if (-not $NoSyntaxCheck) {
    try {
        Invoke-PS "Write-Output 'syntax check ok'"
    } catch {
        Write-Host "Skip syntax check (PowerShell 7 not found)."
    }
}

if ($KillApp) {
    cmd /c "taskkill /F /IM TRANSCRIBATORAUD.exe /T" | Out-Null
    cmd /c "taskkill /F /IM TRANSCRIBATORAUD_console.exe /T" | Out-Null
}

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$env:PYI_PROJECT_ROOT = $ProjectRoot
$env:PYI_SPEC_DIR = $PSScriptRoot

function Get-Python312Path {
    $candidates = @(
        @{ Cmd = "py"; Args = @('-3.12') },
        @{ Cmd = "python"; Args = @() },
        @{ Cmd = "python3"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $args = @()
            $args += $candidate.Args
            $args += @('-c', 'import sys; assert sys.version_info[:2] == (3, 12); print(sys.executable)')
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
    $distDir  = Join-Path $ProjectRoot 'dist'
    $buildDir = Join-Path $ProjectRoot 'build/TRANSCRIBATORAUD'
    $exeDir   = Join-Path $distDir 'TRANSCRIBATORAUD'

    Write-Host "Cleaning previous artefacts..." -ForegroundColor Cyan

    if (Test-Path $exeDir) {
        $exePath = Join-Path $exeDir 'TRANSCRIBATORAUD.exe'
        if (Test-Path $exePath) {
            Start-Process $exePath -ArgumentList '--shutdown' -WindowStyle Hidden -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }

        if (-not (Stop-RunningApp -DistDir $exeDir -Rounds 4 -WaitMs 600)) {
            throw "Running app instances are still alive. Close them manually and rerun the build."
        }

        Get-ChildItem $exeDir -Recurse -Force -ErrorAction SilentlyContinue | ForEach-Object {
            try { $_.IsReadOnly = $false } catch {}
        }
        try { Remove-Item -Recurse -Force $exeDir } catch { Start-Sleep -Milliseconds 400 }
        if (Test-Path $exeDir) { Remove-Item -Recurse -Force $exeDir }
    }

    if (Test-Path $distDir)  { Remove-Path-Retry -Path $distDir  -MaxRetries 15 -DelaySec 1 }
    if (Test-Path $buildDir) { Remove-Path-Retry -Path $buildDir -MaxRetries 15 -DelaySec 1 }

    $pyiCache = Join-Path $env:LOCALAPPDATA 'pyinstaller'
    if (Test-Path $pyiCache) { Remove-Path-Retry -Path $pyiCache -MaxRetries 5 -DelaySec 1 }

    $other = @('.venv', 'build/output', 'build/cache')
    foreach ($rel in $other) {
        $target = Join-Path $ProjectRoot $rel
        if (Test-Path $target) {
            Remove-Path-Retry -Path $target -MaxRetries 5 -DelaySec 1
        }
    }
}

$pythonPath = Get-Python312Path

Write-Host "Using Python interpreter: $pythonPath"

$bootstrap = Join-Path $ProjectRoot 'scripts/bootstrap.ps1'

& $bootstrap -PythonBin $pythonPath

Write-Host "Build complete. EXE artefacts remain under dist/ and must not be committed to git."
