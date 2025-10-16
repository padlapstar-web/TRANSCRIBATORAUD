Param(
  [string]$OutDir = "$(Resolve-Path "$PSScriptRoot\..\resources\ffmpeg").Path"
)
$ErrorActionPreference = "Stop"
New-Item -Force -ItemType Directory -Path $OutDir | Out-Null

$ff = Join-Path $OutDir "ffmpeg.exe"
$fp = Join-Path $OutDir "ffprobe.exe"
if ((Test-Path $ff) -and (Test-Path $fp)) {
  Write-Host "ffmpeg/ffprobe уже существуют → $OutDir"
  exit 0
}

$cache = "$(Resolve-Path "$PSScriptRoot\cache").Path"
New-Item -Force -ItemType Directory -Path $cache | Out-Null
$zip = Join-Path $cache "ffmpeg-win64.zip"
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "Скачиваю FFmpeg: $url"
Invoke-WebRequest -Uri $url -OutFile $zip

$tmp = Join-Path $cache "unpack"
if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
Expand-Archive -Path $zip -DestinationPath $tmp

$bin = Get-ChildItem -Recurse -Path $tmp -Filter "ffmpeg.exe" | Select-Object -First 1
$bin2 = Get-ChildItem -Recurse -Path $tmp -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $bin -or -not $bin2) { throw "Не найден ffmpeg/ffprobe в архиве" }

Copy-Item $bin.FullName $ff -Force
Copy-Item $bin2.FullName $fp -Force
Write-Host "Готово: $ff, $fp"
