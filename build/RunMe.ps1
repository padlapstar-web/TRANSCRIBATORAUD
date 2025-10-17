#Requires -Version 5.1
param(
    [switch]$Clean,
    [string]$PyPreferred = "3.12"
)

Set-StrictMode -Version Latest
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($IsAdmin) {
    Write-Warning "Running as Administrator is not required and may mask build issues. Use a regular PowerShell session."
}
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function Resolve-PythonInterpreter {
    param([string]$Version)

    function Resolve-CandidatePath {
        param([string]$Candidate)
        if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
        if ($Candidate -match '(?i)(anaconda|miniconda)') { return $null }
        if (Test-Path $Candidate) { return (Resolve-Path $Candidate).Path }
        return $null
    }

    $candidates = @()

    $directPaths = @(
        "$Env:LocalAppData\Programs\Python\Python$Version\python.exe",
        "C:\\Program Files\\Python$Version\\python.exe",
        "C:\\Program Files (x86)\\Python$Version\\python.exe"
    )
    foreach ($path in $directPaths) {
        $resolved = Resolve-CandidatePath -Candidate $path
        if ($resolved) { $candidates += $resolved }
    }

    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        $pyArgs = @("-$Version", "-c", "import sys; print(sys.executable)")
        $result = (& $pyLauncher.Path @pyArgs 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $text = if ($result -is [Array]) { $result[-1] } else { $result }
            $resolved = Resolve-CandidatePath -Candidate ($text.Trim())
            if ($resolved) { $candidates += $resolved }
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd -and ($Version -eq "3.12")) {
        try {
            $reported = (& $pythonCmd.Path -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
            if ($reported -eq "3.12") {
                $resolved = Resolve-CandidatePath -Candidate $pythonCmd.Path
                if ($resolved) { $candidates += $resolved }
            }
        } catch {}
    }

    $unique = @()
    foreach ($candidate in $candidates) {
        if ($candidate -and ($unique -notcontains $candidate)) {
            $unique += $candidate
        }
    }

    if ($unique.Count -gt 0) { return $unique[0] }
    throw "Python $Version (python.org) not found. Install it from python.org and re-run."
}

$root = (Resolve-Path (Join-Path $PSScriptRoot ".." )).Path
Set-Location $root

if ($Clean.IsPresent) {
    Remove-Item -Recurse -Force .venv, "build\pyinstaller", dist, build\*.log, build\cache -ErrorAction SilentlyContinue
}

$pythonExe = Resolve-PythonInterpreter -Version $PyPreferred
Write-Host ("Using interpreter: " + $pythonExe)

if (Test-Path .\.venv) {
    Remove-Item -Recurse -Force .\.venv -ErrorAction SilentlyContinue
}

& $pythonExe -m venv .\.venv
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (!(Test-Path $venvPython)) { throw "Missing .\\.venv\\Scripts\\python.exe" }

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r (Join-Path $root "requirements.txt")
& $venvPython -m pip install pyinstaller

$ffOutDir = Join-Path $root "resources\ffmpeg"
& (Join-Path $PSScriptRoot "Ensure-FFmpeg.ps1") -OutDir $ffOutDir
if (!(Test-Path (Join-Path $ffOutDir "ffmpeg.exe")) -or !(Test-Path (Join-Path $ffOutDir "ffprobe.exe"))) {
    throw "FFmpeg not prepared in resources\\ffmpeg"
}
$env:PATH = "$ffOutDir;$env:PATH"

$spec = Join-Path $root "build\TRANSCRIBATORAUD.spec"
$logDir = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$pyiLog = Join-Path $logDir "pyinstaller-admin.log"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $venvPython
$psi.ArgumentList.Add("-m")
$psi.ArgumentList.Add("PyInstaller")
$psi.ArgumentList.Add("--noconfirm")
$psi.ArgumentList.Add("--clean")
$psi.ArgumentList.Add($spec)
$psi.WorkingDirectory = $root
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.Environment["PYTHONUTF8"] = "1"

$proc = [System.Diagnostics.Process]::Start($psi)
$stdOut = $proc.StandardOutput.ReadToEnd()
$stdErr = $proc.StandardError.ReadToEnd()
$proc.WaitForExit()
Set-Content -Path $pyiLog -Value ($stdOut + "`r`n" + $stdErr) -Encoding UTF8
if ($proc.ExitCode -ne 0) {
    Write-Host "---- PyInstaller LOG (tail) ----"
    if (Test-Path $pyiLog) {
        Get-Content $pyiLog -Tail 120
    }
    Write-Error "PyInstaller failed (code $($proc.ExitCode)). See $pyiLog"
    exit $proc.ExitCode
}

$exe = Join-Path $root "dist\TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
if (!(Test-Path $exe)) {
    throw "EXE not found after build: $exe"
}

Write-Host "READY: $exe"
Write-Host "Run:   `"$exe`" --help"
