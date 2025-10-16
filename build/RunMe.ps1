Param(
  [string]$Python = "3.11",
  [switch]$Clean
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $root

if ($Clean) {
  Remove-Item -Recurse -Force .venv, build\cache, dist_*, build\*.log -ErrorAction SilentlyContinue
}

if (!(Test-Path .\.venv)) {
  & py -$Python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

& powershell -NoProfile -ExecutionPolicy Bypass -File "./build/Ensure-FFmpeg.ps1"

$ffdir = Join-Path $root "resources\ffmpeg"
if (Test-Path $ffdir) {
  $env:PATH = "$ffdir;$env:PATH"
}

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

$appdata = Join-Path $env:APPDATA "TRANSCRIBATORAUD"
New-Item -Force -ItemType Directory -Path $appdata | Out-Null
@"
device: auto
compute_type: auto
models_dir: "$($appdata.Replace('\','\\'))\\models"
"@ | Out-File -Encoding UTF8 (Join-Path $appdata "config.yaml")

pyinstaller --clean pyinstaller.spec | Tee-Object -FilePath .\build\build.log

Write-Host "`nГОТОВО: dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
Write-Host "Запуск: dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe --help"
