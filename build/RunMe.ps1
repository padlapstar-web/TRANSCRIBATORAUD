#Requires -Version 5.1
param(
    [switch]$Clean,
    [string]$PyPreferred = "3.12"
)

Set-StrictMode -Version Latest
$IsAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($IsAdmin) {
    Write-Warning "Running as Administrator is not required and may hide build issues. Use a regular PowerShell session."
}
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

if ($PyPreferred -ne "3.12") {
    Write-Warning "Only python.org 3.12 is supported for packaging. Overriding to 3.12."
    $PyPreferred = "3.12"
}

function Resolve-CandidatePath {
    param([string]$Candidate)
    if ([string]::IsNullOrWhiteSpace($Candidate)) { return $null }
    if ($Candidate -match '(?i)(anaconda|miniconda)') { return $null }
    if (Test-Path $Candidate) {
        return (Resolve-Path $Candidate).Path
    }
    return $null
}

function Resolve-Python {
    param([string]$Version)

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
        $result = (& $pyLauncher.Path "-$Version" "-c" "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -eq 0) {
            $text = if ($result -is [Array]) { $result[-1] } else { $result }
            $resolved = Resolve-CandidatePath -Candidate ($text.Trim())
            if ($resolved) { $candidates += $resolved }
        }
    }

    if ($Version -eq "3.12") {
        $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
        if ($pythonCmd) {
            try {
                $reported = (& $pythonCmd.Path -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
                if ($reported -eq "3.12") {
                    $resolved = Resolve-CandidatePath -Candidate $pythonCmd.Path
                    if ($resolved) { $candidates += $resolved }
                }
            } catch {}
        }
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

$pythonExe = Resolve-Python -Version $PyPreferred
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

# --- PyInstaller: resilient under admin PowerShell ---
$spec   = Join-Path $root "build\TRANSCRIBATORAUD.spec"
$logDir = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$pyiOut = Join-Path $logDir "pyinstaller-admin.out.log"
$pyiErr = Join-Path $logDir "pyinstaller-admin.err.log"
$pyiLog = Join-Path $logDir "pyinstaller-admin.log"
Remove-Item $pyiOut, $pyiErr, $pyiLog -ErrorAction SilentlyContinue

$args = @("-m", "PyInstaller", "--noconfirm", "--clean", "--log-level", "INFO", $spec)
$proc = Start-Process -FilePath $venvPython `
    -ArgumentList $args `
    -WorkingDirectory $root `
    -NoNewWindow -PassThru -Wait `
    -RedirectStandardOutput $pyiOut `
    -RedirectStandardError $pyiErr

Get-Content $pyiOut, $pyiErr -ErrorAction SilentlyContinue | Set-Content -Encoding UTF8 $pyiLog

if ($proc.ExitCode -ne 0) {
    Write-Host "---- PyInstaller LOG (tail) ----"
    if (Test-Path $pyiLog) {
        Get-Content $pyiLog -Tail 160
    }
    Write-Error "PyInstaller failed (code $($proc.ExitCode)). See $pyiLog"
    exit $proc.ExitCode
}

$exe = $null
$candidateA = Join-Path $root "dist\TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
$candidateB = Join-Path $root "dist\TRANSCRIBATORAUD.exe"
if (Test-Path $candidateA) {
    $exe = $candidateA
} elseif (Test-Path $candidateB) {
    $exe = $candidateB
} else {
    $hit = Get-ChildItem -Recurse -Path (Join-Path $root "dist") -Filter "TRANSCRIBATORAUD.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hit) {
        $exe = $hit.FullName
    } else {
        Write-Error "EXE not found after build"
        exit 1
    }
}

Write-Host "`nREADY: $exe"
Write-Host "Run:   `"$exe`" --help"
