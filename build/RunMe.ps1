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

function Find-PythonExe {
  param([string[]]$Order = @("3.12","3.11","3.10"), [string]$Preferred = "auto")

  if ($Preferred -ne "auto") {
    $candidate = $null
    if (Get-Command py -ErrorAction SilentlyContinue) {
      try {
        $candidate = (& py -$Preferred -c "import sys,sysconfig;print(sys.executable)" 2>$null).Trim()
      } catch {}
    }
    if (-not $candidate -and (Get-Command python -ErrorAction SilentlyContinue)) {
      try { $candidate = (& python -c "import sys;print(sys.executable)" 2>$null).Trim() } catch {}
    }
    if ($candidate -and (Test-Path $candidate)) { return $candidate }
  }

  $candidates = @()
  $regRoots = @(
    "HKCU:\Software\Python\PythonCore",
    "HKLM:\Software\Python\PythonCore",
    "HKLM:\Software\WOW6432Node\Python\PythonCore"
  )
  foreach ($root in $regRoots) {
    foreach ($v in $Order) {
      $subKey = Join-Path $root $v
      try {
        $install = Get-ItemProperty -Path "$subKey\InstallPath" -ErrorAction Stop
        $path = Join-Path $install.'(default)' 'python.exe'
        if ($path -and (Test-Path $path)) { $candidates += $path }
      } catch {}
    }
  }

  $commonDirs = @(
    "$env:LocalAppData\Programs\Python",
    "$env:ProgramFiles\Python312",
    "$env:ProgramFiles\Python311",
    "$env:ProgramFiles\Python310",
    "$env:ProgramFiles(x86)\Python312",
    "$env:ProgramFiles(x86)\Python311",
    "$env:ProgramFiles(x86)\Python310"
  )
  foreach ($dir in $commonDirs) {
    if (Test-Path $dir) {
      $candidates += (Get-ChildItem -Path $dir -Recurse -Filter python.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    }
  }

  if (Get-Command py -ErrorAction SilentlyContinue) {
    $list = & py -0p 2>$null
    foreach ($v in $Order) {
      $match = ($list | Select-String " -$([Regex]::Escape($v)) ")
      if ($match) {
        $parts = ($match.Line -split '\s+',3)
        if ($parts.Length -ge 3 -and (Test-Path $parts[2])) { $candidates += $parts[2] }
      }
    }
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd) { $candidates += $pythonCmd.Source }

  $candidates = $candidates | Where-Object { $_ } | Select-Object -Unique | Where-Object { $_ -notmatch 'anaconda|miniconda' }
  if ($candidates.Count -gt 0) { return $candidates[0] }

  throw "Python 3.12/3.11/3.10 not found. Install one of them and re-run."
}

$root = (Resolve-Path "$PSScriptRoot\..\").Path
Set-Location $root

if ($Clean.IsPresent) {
  Remove-Item -Recurse -Force .venv, "build\cache", dist_*, build\*.log -ErrorAction SilentlyContinue
}

$order = @("3.12","3.11","3.10")
try {
  $pyExe = Find-PythonExe -Order $order -Preferred $Python
} catch {
  Write-Host "Installing python.org 3.12 via winget..."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements --silent --scope user
    $pyExe = Find-PythonExe -Order $order -Preferred "3.12"
  } else {
    throw "winget not available; install Python 3.12 from python.org and re-run"
  }
}
Write-Host ("Using interpreter: " + $pyExe)

if (!(Test-Path .\.venv)) { & "$pyExe" -m venv .venv }
if (!(Test-Path .\.venv\Scripts\Activate.ps1)) { throw "Missing .\\.venv\\Scripts\\Activate.ps1" }
& .\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
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
if (Test-Path $ffdir) { $env:PATH = "$ffdir;$env:PATH" }

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
coll=COLLECT(exe,a.binaries,a.zipfiles,a.datas,name="TRANSCRIBATORAUD")
"@ | Out-File -Encoding UTF8 .\pyinstaller.spec

$appdata = Join-Path $env:APPDATA "TRANSCRIBATORAUD"
New-Item -Force -ItemType Directory -Path $appdata | Out-Null
@"
device: auto
compute_type: auto
models_dir: "$(($appdata.Replace('\','\\')))\\models"
"@ | Out-File -Encoding UTF8 (Join-Path $appdata "config.yaml")

$env:PYTHONNOUSERSITE = "1"
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
    Write-Error "EXE not found after build (checked dist\\TRANSCRIBATORAUD and dist root)"
    exit 1
  }
}

Write-Host ""
Write-Host ("READY: " + $exe)
Write-Host ("Run:   `"" + $exe + "`" --help")
