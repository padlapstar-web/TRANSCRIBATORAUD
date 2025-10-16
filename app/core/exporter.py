"""Export helpers stubs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.core.asr import Word


def save_jsonl(words: Iterable[Word], path: Path) -> None:
    path.write_text("[]\n")


def save_csv(words: Iterable[Word], path: Path) -> None:
    path.write_text("i,start,end,word,prob\n")


def save_vtt(words: Iterable[Word], path: Path) -> None:
    path.write_text("WEBVTT\n")


def save_srt(words: Iterable[Word], path: Path) -> None:
    path.write_text("")


def save_lrc(words: Iterable[Word], path: Path) -> None:
    path.write_text("")

