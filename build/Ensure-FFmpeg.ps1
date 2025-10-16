#Requires -Version 5.1
Param(
  [string]$OutDir = "$(Resolve-Path "$PSScriptRoot\..\resources\ffmpeg").Path"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

New-Item -Force -ItemType Directory -Path $OutDir | Out-Null
$ff = Join-Path $OutDir "ffmpeg.exe"
$fp = Join-Path $OutDir "ffprobe.exe"
if ((Test-Path $ff) -and (Test-Path $fp)) {
  Write-Host "FFmpeg already present -> $OutDir"
  exit 0
}

$cache = Join-Path $PSScriptRoot "cache"
New-Item -Force -ItemType Directory -Path $cache | Out-Null
$zip = Join-Path $cache "ffmpeg-win64.zip"
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "Downloading FFmpeg -> $zip"
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

$tmp = Join-Path $cache "unpack"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive -Path $zip -DestinationPath $tmp

$bin  = Get-ChildItem -Recurse -Path $tmp -Filter "ffmpeg.exe"  | Select-Object -First 1
$bin2 = Get-ChildItem -Recurse -Path $tmp -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $bin -or -not $bin2) { throw "ffmpeg/ffprobe not found in archive" }

Copy-Item $bin.FullName  $ff -Force
Copy-Item $bin2.FullName $fp -Force
Write-Host "FFmpeg ready: $ff, $fp"
