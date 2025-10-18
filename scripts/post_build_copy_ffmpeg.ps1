#requires -version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Resolve-Executable {
    param(
        [string[]]$Names
    )

    $candidates = @()
    if ($env:FFMPEG_BIN) {
        $candidates += $env:FFMPEG_BIN
    }
    if ($env:FFMPEG_HOME) {
        foreach ($name in $Names) {
            $candidates += (Join-Path $env:FFMPEG_HOME $name)
            $candidates += (Join-Path (Join-Path $env:FFMPEG_HOME 'bin') $name)
        }
    }
    foreach ($name in $Names) {
        try {
            $cmd = Get-Command $name -ErrorAction Stop
            if ($cmd.Source) {
                $candidates += $cmd.Source
            }
        } catch {
            continue
        }
    }

    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) { continue }
        $path = Resolve-Path -LiteralPath $candidate -ErrorAction SilentlyContinue
        if ($path) { return $path.Path }
        if ($candidate -notmatch '\.exe$') {
            $exeCandidate = "$candidate.exe"
            $path = Resolve-Path -LiteralPath $exeCandidate -ErrorAction SilentlyContinue
            if ($path) { return $path.Path }
        }
    }

    return $null
}

$distPath = Resolve-Path -LiteralPath $DistDir -ErrorAction SilentlyContinue
if (-not $distPath) {
    Write-Warning "Dist directory '$DistDir' не найден"
    return
}
$distPath = $distPath.Path

$ffmpegPath = Resolve-Executable @('ffmpeg.exe', 'ffmpeg')
if (-not $ffmpegPath) {
    Write-Warning 'FFmpeg не найден в системе. Пропускаем копирование.'
    return
}

$targetBin = Join-Path $distPath 'resources/ffmpeg/bin'
New-Item -ItemType Directory -Force -Path $targetBin | Out-Null
Copy-Item -LiteralPath $ffmpegPath -Destination (Join-Path $targetBin 'ffmpeg.exe') -Force

$ffprobePath = Resolve-Executable @('ffprobe.exe', 'ffprobe')
if ($ffprobePath) {
    Copy-Item -LiteralPath $ffprobePath -Destination (Join-Path $targetBin 'ffprobe.exe') -Force
}
else {
    Write-Warning 'FFprobe не найден — продолжим без него.'
}
