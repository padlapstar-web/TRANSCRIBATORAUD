"""Audio helper utilities."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

SUPPORTED_EXTENSIONS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".flac",
    ".ogg",
    ".opus",
    ".aac",
}


def is_supported_audio(path: Path) -> bool:
    """Return True if the path points to a supported audio file."""

    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def _ffprobe_candidates() -> list[Path]:
    here = Path(__file__).resolve().parents[2]
    resources_dir = here / "resources" / "ffmpeg"
    candidates: list[Path] = []
    for name in ("ffprobe", "ffprobe.exe"):
        local = resources_dir / name
        if local.exists():
            candidates.append(local)
    probe_in_path = shutil.which("ffprobe")
    if probe_in_path:
        candidates.append(Path(probe_in_path))
    return candidates


def _resolve_ffprobe() -> Optional[Path]:
    for candidate in _ffprobe_candidates():
        if candidate.exists():
            return candidate
    return None


def probe_duration(path: Path) -> Optional[float]:
    """Return the duration of an audio file in seconds using ffprobe."""

    ffprobe_path = _resolve_ffprobe()
    if ffprobe_path is None:
        return None

    command = [
        str(ffprobe_path),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None

    output = result.stdout.strip()
    if not output:
        return None

    try:
        return float(output)
    except ValueError:
        return None

