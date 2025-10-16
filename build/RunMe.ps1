#Requires -Version 5.1
[CmdletBinding()]
Param(
  [string]$Python = "3.11",
  [switch]$Clean
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

# Repository root
$root = (Resolve-Path "$PSScriptRoot\..\").Path
Set-Location $root

# Optional cleanup
if ($Clean.IsPresent) {
  Remove-Item -Recurse -Force .venv, "build\cache", dist_*, build\*.log -ErrorAction SilentlyContinue
}

# 1) Virtual environment
if (!(Test-Path .\.venv)) {
  if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -$Python -m venv .venv
  } else {
    & python -m venv .venv
  }
}
& .\.venv\Scripts\Activate.ps1

# 2) Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# 3) Local ffmpeg/ffprobe generation
powershell -NoProfile -ExecutionPolicy Bypass -File ".\build\Ensure-FFmpeg.ps1"

# 4) Add ffmpeg directory to PATH for build/runtime
$ffdir = Join-Path $root "resources\ffmpeg"
if (Test-Path $ffdir) { $env:PATH = "$ffdir;$env:PATH" }

# 5) Generate PyInstaller spec when missing
if (!(Test-Path .\pyinstaller.spec)) {
  @"
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
hidden = []
try:
    hidden += collect_submodules("ct2")
except Exception:
    pass
hidden += collect_submodules("faster_whisper")
datas = collect_data_files("PySide6")
a = Analysis(["app/main.py"], pathex=[], binaries=[
    ("resources/ffmpeg/ffmpeg.exe", "resources/ffmpeg"),
    ("resources/ffmpeg/ffprobe.exe", "resources/ffmpeg"),
], datas=datas, hiddenimports=hidden)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name="TRANSCRIBATORAUD", console=True)
coll = COLLECT(exe, a.binaries, a.zipfiles, a.datas, name="dist_TRANSCRIBATORAUD")
"@ | Out-File -Encoding UTF8 .\pyinstaller.spec
}

# 6) Default application config
$appdata = Join-Path $env:APPDATA "TRANSCRIBATORAUD"
New-Item -Force -ItemType Directory -Path $appdata | Out-Null
@"
device: auto
compute_type: auto
models_dir: "$(($appdata.Replace('\','\\')))\\models"
"@ | Out-File -Encoding UTF8 (Join-Path $appdata "config.yaml")

# 7) Build
pyinstaller --clean pyinstaller.spec | Tee-Object -FilePath .\build\build.log

Write-Host ""
Write-Host "READY: dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
Write-Host "Run:   dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe --help"
