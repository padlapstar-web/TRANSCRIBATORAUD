"""Utilities for locating FFmpeg executables without bundling binaries."""

from __future__ import annotations

import os
import shutil
import sys
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional

__all__ = ["find_ffmpeg", "find_ffprobe"]

_EXECUTABLE_NAMES = ("ffmpeg.exe", "ffmpeg")
_FFPROBE_NAMES = ("ffprobe.exe", "ffprobe")


def _iter_candidate_paths(names: Iterable[str]) -> Iterable[Path]:
    # 1. Frozen bundle directory (PyInstaller)
    if hasattr(sys, "_MEIPASS") or getattr(sys, "frozen", False):
        exe_dir = Path(getattr(sys, "executable", Path.cwd())).resolve().parent
        for subdir in ("resources/ffmpeg/bin", "resources/ffmpeg"):
            base = exe_dir / subdir
            for name in names:
                yield base / name

    # 2. Repository checkout (development mode)
    repo_root = Path(__file__).resolve().parents[2]
    for subdir in ("resources/ffmpeg/bin", "resources/ffmpeg"):
        base = repo_root / subdir
        for name in names:
            yield base / name

    # 3. Environment variables
    ffmpeg_bin = os.environ.get("FFMPEG_BIN")
    if ffmpeg_bin:
        yield Path(ffmpeg_bin)
    ffmpeg_home = os.environ.get("FFMPEG_HOME")
    if ffmpeg_home:
        home = Path(ffmpeg_home)
        for subdir in ("", "bin"):
            base = home / subdir if subdir else home
            for name in names:
                yield base / name

    # 4. PATH resolution
    for name in names:
        resolved = shutil.which(name)
        if resolved:
            yield Path(resolved)


def _normalise_candidate(path: Path) -> Optional[Path]:
    if path.is_file():
        return path
    if sys.platform.startswith("win") and path.suffix.lower() != ".exe":
        candidate = path.with_suffix(".exe")
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def find_ffmpeg() -> Optional[Path]:
    """Return the first discovered ffmpeg binary or ``None`` if unavailable."""

    for candidate in _iter_candidate_paths(_EXECUTABLE_NAMES):
        resolved = _normalise_candidate(candidate)
        if resolved:
            return resolved
    return None


@lru_cache(maxsize=1)
def find_ffprobe() -> Optional[Path]:
    """Return the first discovered ffprobe binary or ``None``."""

    for candidate in _iter_candidate_paths(_FFPROBE_NAMES):
        resolved = _normalise_candidate(candidate)
        if resolved:
            return resolved
    return None
