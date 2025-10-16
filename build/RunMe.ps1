#Requires -Version 5.1
[CmdletBinding()]
Param(
  [switch]$Clean
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new() } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function Find-Python312 {
  $cands = @(
    "$env:LocalAppData\Programs\Python\Python312\python.exe",
    "C:\\Program Files\\Python312\\python.exe",
    "C:\\Program Files (x86)\\Python312\\python.exe"
  ) | Where-Object { Test-Path $_ }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    $list = & py -0p 2>$null
    $match = ($list | Select-String " -3\.12 ").Line
    if ($match) {
      $parts = $match -split '\s+',3
      if ($parts.Length -ge 3 -and ($parts[2] -notmatch 'anaconda|miniconda')) {
        $cands += $parts[2]
      }
    }
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) {
    $path = $pythonCmd.Source
    if ($path -and ($path -notmatch 'anaconda|miniconda')) {
      try {
        $ver = (& $path -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
        if ($ver -eq "3.12") {
          $cands += $path
        }
      } catch {}
    }
  }

  $cands = $cands | Where-Object { $_ } | Select-Object -Unique | Where-Object { $_ -notmatch 'anaconda|miniconda' }
  if ($cands.Count -gt 0) { return $cands[0] }
  return $null
}

$root = (Resolve-Path "$PSScriptRoot\..\").Path
Set-Location $root
if ($Clean.IsPresent) {
  Remove-Item -Recurse -Force .venv, "build\pyinstaller", dist, build\*.log, build\cache -ErrorAction SilentlyContinue
}

$pyExe = Find-Python312
if (-not $pyExe) {
  Write-Host "Installing python.org 3.12 via winget..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent --scope user
    $pyExe = Find-Python312
  }
  if (-not $pyExe) { throw "Python 3.12 (python.org) not found. Install it and re-run." }
}
Write-Host ("Using interpreter: " + $pyExe)

$venvHome = Join-Path $root ".venv"
if (Test-Path (Join-Path $venvHome "pyvenv.cfg")) {
  try {
    $cfg = Get-Content (Join-Path $venvHome "pyvenv.cfg") -Encoding UTF8
    if ($cfg -match 'anaconda|miniconda') {
      Remove-Item -Recurse -Force $venvHome -ErrorAction SilentlyContinue
    }
  } catch {}
}

if (!(Test-Path .\.venv)) { & "$pyExe" -m venv .venv }
if (!(Test-Path .\.venv\Scripts\Activate.ps1)) { throw "Missing .\\.venv\\Scripts\\Activate.ps1" }
& .\.venv\Scripts\Activate.ps1

$env:PYTHONNOUSERSITE = "1"
python -m pip install -U pip
pip install -r requirements.txt
pip install pyinstaller

powershell -NoProfile -ExecutionPolicy Bypass -File ".\build\Ensure-FFmpeg.ps1"
$ffdir = Join-Path $root "resources\ffmpeg"
$ffExe = Join-Path $ffdir "ffmpeg.exe"
$ffProbe = Join-Path $ffdir "ffprobe.exe"
$ffok  = (Test-Path $ffExe) -and (Test-Path $ffProbe)
if (-not $ffok) {
  $wrong = Join-Path (Join-Path $root "resources") "ffmpeg.Path"
  if (Test-Path $wrong) {
    New-Item -Force -ItemType Directory -Path $ffdir | Out-Null
    Copy-Item "$wrong\*" $ffdir -Force
    $ffok = (Test-Path $ffExe) -and (Test-Path $ffProbe)
  }
}
if (-not $ffok) {
  Write-Error "FFmpeg not prepared in resources\\ffmpeg"
  exit 1
}
$env:PATH = "$ffdir;$env:PATH"

if (!(Test-Path .\pyinstaller.spec)) {
  @"
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hidden=[]
try: hidden+=collect_submodules("ct2")
except Exception: pass
hidden+=collect_submodules("faster_whisper")
datas=collect_data_files("PySide6")
a=Analysis(["app/main.py"], pathex=[], binaries=[
  ("resources/ffmpeg/ffmpeg.exe","resources/ffmpeg"),
  ("resources/ffmpeg/ffprobe.exe","resources/ffmpeg"),
], datas=datas, hiddenimports=hidden)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,name="TRANSCRIBATORAUD",console=True)
coll=COLLECT(exe,a.binaries,a.zipfiles,a.datas,name="TRANSCRIBATORAUD")
"@ | Out-File -Encoding UTF8 .\pyinstaller.spec
}

$appdata = Join-Path $env:APPDATA "TRANSCRIBATORAUD"
New-Item -Force -ItemType Directory -Path $appdata | Out-Null
@"
device: auto
compute_type: auto
models_dir: "$([System.Text.RegularExpressions.Regex]::Escape($appdata))\\models"
"@ | Out-File -Encoding UTF8 (Join-Path $appdata "config.yaml")

python -m PyInstaller --noconfirm --clean --workpath ".\build\pyinstaller" --distpath ".\dist" pyinstaller.spec | Tee-Object -FilePath .\build\build.log
if ($LASTEXITCODE -ne 0) {
  Write-Error "PyInstaller failed. See build\\build.log"
  exit $LASTEXITCODE
}

$exeA = ".\dist\TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
$exeB = ".\dist\TRANSCRIBATORAUD.exe"
if (Test-Path $exeA) {
  $exe = $exeA
} elseif (Test-Path $exeB) {
  $exe = $exeB
} else {
  $hit = Get-ChildItem -Recurse -Path .\dist\ -Filter TRANSCRIBATORAUD.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($hit) {
    $exe = $hit.FullName
  } else {
    Write-Error "EXE not found after build"
    exit 1
  }
}

Write-Host ""
Write-Host ("READY: " + $exe)
Write-Host ("Run:   `"" + $exe + "`" --help")
