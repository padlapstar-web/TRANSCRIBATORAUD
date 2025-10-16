"""Export helpers for recognised word timelines."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Callable, Dict, Iterable, Sequence

from app.core.asr import Word


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _format_seconds(value: float, separator: str = ".") -> str:
    hours = int(value // 3600)
    minutes = int((value % 3600) // 60)
    seconds = value % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}".replace(".", separator, 1)


def _format_lrc_timestamp(value: float) -> str:
    minutes = int(value // 60)
    seconds = value % 60
    return f"[{minutes:02d}:{seconds:05.2f}]"


def save_jsonl(words: Iterable[Word], path: Path) -> None:
    """Persist recognised words into a JSONL file."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for word in words:
            json.dump(word.as_mapping(), handle, ensure_ascii=False)
            handle.write("\n")


def save_csv(words: Iterable[Word], path: Path) -> None:
    """Persist recognised words into a CSV file."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["i", "start", "end", "word", "prob"])
        for word in words:
            probability = "" if word.probability is None else f"{word.probability:.3f}"
            writer.writerow(
                [
                    word.index,
                    f"{word.start:.3f}",
                    f"{word.end:.3f}",
                    word.word,
                    probability,
                ]
            )


def save_vtt(words: Iterable[Word], path: Path) -> None:
    """Persist recognised words into a WebVTT file."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("WEBVTT\n\n")
        for word in words:
            start = _format_seconds(word.start, ".")
            end = _format_seconds(word.end, ".")
            handle.write(f"{start} --> {end}\n")
            handle.write(f"{word.word}\n\n")


def save_srt(words: Iterable[Word], path: Path) -> None:
    """Persist recognised words into an SRT file."""

    _ensure_parent(path)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for index, word in enumerate(words, start=1):
            start = _format_seconds(word.start, ",")
            end = _format_seconds(word.end, ",")
            handle.write(f"{index}\n{start} --> {end}\n{word.word}\n\n")


def save_lrc(words: Iterable[Word], path: Path) -> None:
    """Persist recognised words into an enhanced LRC file."""

    _ensure_parent(path)
    lines: list[list[str]] = []
    current_line: list[str] = []
    current_start = 0.0

    for word in words:
        if not current_line:
            current_start = word.start
        should_break = (
            word.end - current_start >= 5.0 or word.word.endswith((".", "?", "!"))
        )
        current_line.append(word.word)
        if should_break:
            timestamp = _format_lrc_timestamp(current_start)
            lines.append([timestamp, " ".join(current_line)])
            current_line = []

    if current_line:
        timestamp = _format_lrc_timestamp(current_start)
        lines.append([timestamp, " ".join(current_line)])

    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for timestamp, text in lines:
            handle.write(f"{timestamp}{text}\n")


EXPORTERS: Dict[str, Callable[[Iterable[Word], Path], None]] = {
    "jsonl": save_jsonl,
    "csv": save_csv,
    "vtt": save_vtt,
    "srt": save_srt,
    "lrc": save_lrc,
}


def normalise_formats(formats: Sequence[str]) -> list[str]:
    """Normalise and validate requested export formats."""

    normalised = []
    for item in formats:
        entry = item.strip().lower()
        if not entry:
            continue
        if entry not in EXPORTERS:
            raise ValueError(f"Unsupported export format: {entry}")
        if entry not in normalised:
            normalised.append(entry)
    return normalised

