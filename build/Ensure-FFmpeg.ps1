#Requires -Version 5.1
[CmdletBinding()]
Param([string]$OutDir)

function Ensure-FFmpeg {
    [CmdletBinding()]
    Param([string]$OutDir)

    Set-StrictMode -Version Latest
    $ErrorActionPreference = "Stop"
    try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch {}

    if (-not $OutDir) {
        $default = Join-Path $PSScriptRoot "..\resources\ffmpeg"
        if (Test-Path $default) {
            $OutDir = (Resolve-Path $default).Path
        } else {
            $OutDir = [System.IO.Path]::GetFullPath($default)
        }
    }

    New-Item -Force -ItemType Directory -Path $OutDir | Out-Null

    $ff = Join-Path $OutDir "ffmpeg.exe"
    $fp = Join-Path $OutDir "ffprobe.exe"
    if ((Test-Path $ff) -and (Test-Path $fp)) {
        Write-Host "FFmpeg already present -> $OutDir"
        return
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
}

if ($MyInvocation.InvocationName -ne ".") {
    Ensure-FFmpeg -OutDir $OutDir
}
