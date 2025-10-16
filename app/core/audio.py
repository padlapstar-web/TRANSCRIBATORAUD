"""Audio helper placeholders."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def is_supported_audio(path: Path) -> bool:
    return path.suffix.lower() in {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".aac"}


def probe_duration(path: Path) -> Optional[float]:
    _ = path
    return None

