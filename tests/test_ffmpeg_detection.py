from __future__ import annotations

from pathlib import Path

from app.core import ffmpeg


def _clear_caches() -> None:
    ffmpeg.find_ffmpeg.cache_clear()
    ffmpeg.find_ffprobe.cache_clear()


def test_find_ffmpeg_prefers_env_bin(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg.exe"
    fake.write_text("")

    monkeypatch.setenv("FFMPEG_BIN", str(fake))

    _clear_caches()
    try:
        assert ffmpeg.find_ffmpeg() == fake
    finally:
        _clear_caches()


def test_find_ffprobe_uses_ffmpeg_home(tmp_path, monkeypatch):
    home = tmp_path / "ffmpeg-home"
    bin_dir = home / "bin"
    bin_dir.mkdir(parents=True)
    ffprobe = bin_dir / "ffprobe.exe"
    ffprobe.write_text("")

    monkeypatch.setenv("FFMPEG_HOME", str(home))

    _clear_caches()
    try:
        assert ffmpeg.find_ffprobe() == ffprobe
    finally:
        _clear_caches()
