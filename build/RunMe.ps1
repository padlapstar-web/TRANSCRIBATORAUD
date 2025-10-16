#Requires -Version 5.1
[CmdletBinding()]
Param(
  [ValidateSet("auto","3.12","3.11","3.10")] [string]$Python = "auto",
  [switch]$Clean
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [Text.UTF8Encoding]::new() } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

function Get-PyLauncher { if (Get-Command py -ErrorAction SilentlyContinue) { return "py" } return $null }

function Select-PythonVersion {
  param([string]$Preferred = "auto")
  $order = @("3.12","3.11","3.10")
  if ($Preferred -ne "auto") { return $Preferred }

  $py = Get-PyLauncher
  if ($py) {
    $list = & $py -0p 2>$null
    foreach ($v in $order) {
      if ($list -match " -$([Regex]::Escape($v)) ") { return $v }
    }
  }
  if (Get-Command python -ErrorAction SilentlyContinue) {
    try {
      $v = (& python -c "import sys;print(f'{sys.version_info.major}.{sys.version_info.minor}')" ).Trim()
      if ($order -contains $v) { return $v }
    } catch {}
  }
  throw "Python 3.12/3.11/3.10 не найден. Установи любой из них и перезапусти."
}

$root = (Resolve-Path "$PSScriptRoot\..\").Path
Set-Location $root

if ($Clean.IsPresent) {
  Remove-Item -Recurse -Force .venv, "build\cache", dist_*, build\*.log -ErrorAction SilentlyContinue
}

$ver = Select-PythonVersion -Preferred $Python
Write-Host ("Using Python " + $ver)

if (!(Test-Path .\.venv)) {
  if (Get-PyLauncher) { & py -$ver -m venv .venv } else { & python -m venv .venv }
}
if (!(Test-Path .\.venv\Scripts\Activate.ps1)) { throw "Не найден .\\.venv\\Scripts\\Activate.ps1" }
& .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

powershell -NoProfile -ExecutionPolicy Bypass -File ".\build\Ensure-FFmpeg.ps1"

$ffdir = Join-Path $root "resources\ffmpeg"
if (Test-Path $ffdir) { $env:PATH = "$ffdir;$env:PATH" }

if (!(Test-Path .\pyinstaller.spec)) {
  @"
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hidden=[]; 
try: hidden+=collect_submodules("ct2")
except Exception: pass
hidden+=collect_submodules("faster_whisper")
datas=collect_data_files("PySide6")
a=Analysis(["app/main.py"], pathex=[], binaries=[
  ("resources/ffmpeg/ffmpeg.exe","resources/ffmpeg"),
  ("resources/ffmpeg/ffprobe.exe","resources/ffmpeg"),
], datas=datas, hiddenimports=hidden)
pyz=PYZ(a.pure); exe=EXE(pyz,a.scripts,name="TRANSCRIBATORAUD",console=True)
coll=COLLECT(exe,a.binaries,a.zipfiles,a.datas,name="dist_TRANSCRIBATORAUD")
"@ | Out-File -Encoding UTF8 .\pyinstaller.spec
}

$appdata = Join-Path $env:APPDATA "TRANSCRIBATORAUD"
New-Item -Force -ItemType Directory -Path $appdata | Out-Null
@"
device: auto
compute_type: auto
models_dir: "$(($appdata.Replace('\','\\')))\\models"
"@ | Out-File -Encoding UTF8 (Join-Path $appdata "config.yaml")

pyinstaller --clean pyinstaller.spec | Tee-Object -FilePath .\build\build.log

Write-Host ""
Write-Host "READY: dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
Write-Host "Run:   dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe --help"
