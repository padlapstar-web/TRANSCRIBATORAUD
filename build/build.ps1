Param(
  [string]$Python = "3.11",
  [ValidateSet("cpu","cuda")] [string]$Device = "cpu",
  [ValidateSet("int8","float16","float32")] [string]$ComputeType = "int8",
  [ValidateSet("Release","Debug")] [string]$Mode = "Release",
  [ValidateSet("download","none")] [string]$Ffmpeg = "download",
  [switch]$Clean
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $root

if ($Clean) { Remove-Item -Recurse -Force .venv, build\cache, dist_*, build\*.log -ErrorAction SilentlyContinue }

# 1) venv
if (!(Test-Path .\.venv)) {
  & py -$Python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# 2) ffmpeg/ffprobe (локальная генерация бинарей в resources\ffmpeg)
if ($Ffmpeg -eq "download") {
  & powershell -ExecutionPolicy Bypass -File ".\build\ensure-ffmpeg.ps1"
}

# 3) Добавить resources\ffmpeg в PATH на время сборки (и запуска)
$ffp = Join-Path $root "resources\ffmpeg"
if (Test-Path $ffp) { $env:PATH = "$ffp;$env:PATH" }

# 4) PyInstaller spec автогенерация (если нет)
if (!(Test-Path .\pyinstaller.spec)) {
  @"
# auto-generated spec
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

# 5) Сборка
if ($Mode -eq "Release") { $env:PYTHONOPTIMIZE="2" }
pyinstaller --clean pyinstaller.spec | Tee-Object -FilePath .\build\build.log

# 6) Инфо о сборке
$bi = Join-Path "$root\dist_TRANSCRIBATORAUD" "build_info.txt"
@"
device=$Device
compute_type=$ComputeType
mode=$Mode
date=$(Get-Date -Format s)
"@ | Out-File -Encoding UTF8 $bi

Write-Host "`nOK: dist_TRANSCRIBATORAUD\TRANSCRIBATORAUD.exe"
