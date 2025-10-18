param(
  [string]$ExeDir
)

$ErrorActionPreference = 'Stop'

function Log($m) { Write-Host "[post-ffmpeg] $m" }

function Find-FromPath([string]$name) {
  $c = Get-Command $name -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  return $null
}

function Find-FFmpeg {
  if ($env:FFMPEG_BIN -and (Test-Path $env:FFMPEG_BIN)) { return $env:FFMPEG_BIN }

  if ($env:FFMPEG_HOME) {
    $p = Join-Path $env:FFMPEG_HOME 'bin\ffmpeg.exe'
    if (Test-Path $p) { return $p }
  }

  $fromPath = Find-FromPath 'ffmpeg.exe'
  if ($fromPath) {
    if ($fromPath -match '\\chocolatey\\bin\\ffmpeg\.exe$' -and $env:ChocolateyInstall) {
      $cand = Get-ChildItem -Path (Join-Path $env:ChocolateyInstall 'lib\ffmpeg\tools') -Filter 'ffmpeg.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($cand) { return $cand.FullName }
    }
    return $fromPath
  }

  if ($env:ChocolateyInstall) {
    $cand = Get-ChildItem -Path (Join-Path $env:ChocolateyInstall 'lib\ffmpeg\tools') -Filter 'ffmpeg.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cand) { return $cand.FullName }
  }

  return $null
}

function MaybeFind-FFprobe($ffDir) {
  $p = Join-Path $ffDir 'ffprobe.exe'
  if (Test-Path $p) { return $p }

  $fromPath = Find-FromPath 'ffprobe.exe'
  if ($fromPath) { return $fromPath }

  if ($env:ChocolateyInstall) {
    $cand = Get-ChildItem -Path (Join-Path $env:ChocolateyInstall 'lib\ffmpeg\tools') -Filter 'ffprobe.exe' -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($cand) { return $cand.FullName }
  }

  return $null
}

# Resolve ExeDir if not passed
if (-not $ExeDir) {
  $distGuess = Resolve-Path (Join-Path $PSScriptRoot '..\dist\TRANSCRIBATORAUD') -ErrorAction SilentlyContinue
  if ($distGuess) { $ExeDir = $distGuess.Path } else { throw "ExeDir not provided and dist folder not found." }
}

$dst = Join-Path $ExeDir 'resources\ffmpeg\bin'
New-Item -ItemType Directory -Force -Path $dst | Out-Null

$ffmpegPath = Find-FFmpeg
if (-not $ffmpegPath) {
  Log 'ffmpeg.exe not found in FFMPEG_BIN / FFMPEG_HOME / PATH / Chocolatey. Skipping copy.'
  exit 0  # do not fail the build
}

Log "ffmpeg.exe: $ffmpegPath"
Copy-Item -Path $ffmpegPath -Destination (Join-Path $dst 'ffmpeg.exe') -Force

$ffprobePath = MaybeFind-FFprobe (Split-Path -Parent $ffmpegPath)
if ($ffprobePath) {
  Log "ffprobe.exe: $ffprobePath"
  Copy-Item -Path $ffprobePath -Destination (Join-Path $dst 'ffprobe.exe') -Force
} else {
  Log 'ffprobe.exe not found, continue without it.'
}

Log "Installed to: $dst"
exit 0
