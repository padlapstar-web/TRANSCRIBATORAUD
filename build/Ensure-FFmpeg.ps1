Param(
  [string]$OutDir = "$(Resolve-Path "$PSScriptRoot\..\resources\ffmpeg").Path"
)
$ErrorActionPreference = "Stop"
New-Item -Force -ItemType Directory -Path $OutDir | Out-Null

$ffmpegExe = Join-Path $OutDir "ffmpeg.exe"
$ffprobeExe = Join-Path $OutDir "ffprobe.exe"
if ((Test-Path $ffmpegExe) -and (Test-Path $ffprobeExe)) {
  Write-Host "ffmpeg/ffprobe уже существуют в $OutDir"
  return
}

$cacheDir = "$(Resolve-Path "$PSScriptRoot\cache").Path"
New-Item -Force -ItemType Directory -Path $cacheDir | Out-Null
$archivePath = Join-Path $cacheDir "ffmpeg-win64.zip"
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "Скачиваю FFmpeg → $archivePath"
Invoke-WebRequest -Uri $url -OutFile $archivePath -UseBasicParsing

$tempDir = Join-Path $cacheDir "unpack"
if (Test-Path $tempDir) {
  Remove-Item -Recurse -Force $tempDir
}
Expand-Archive -Path $archivePath -DestinationPath $tempDir

$ffmpegSrc = Get-ChildItem -Recurse -Path $tempDir -Filter "ffmpeg.exe" | Select-Object -First 1
$ffprobeSrc = Get-ChildItem -Recurse -Path $tempDir -Filter "ffprobe.exe" | Select-Object -First 1
if (-not $ffmpegSrc -or -not $ffprobeSrc) {
  throw "Не найден ffmpeg/ffprobe в архиве"
}

Copy-Item $ffmpegSrc.FullName $ffmpegExe -Force
Copy-Item $ffprobeSrc.FullName $ffprobeExe -Force
Write-Host "FFmpeg готов: $ffmpegExe, $ffprobeExe"
