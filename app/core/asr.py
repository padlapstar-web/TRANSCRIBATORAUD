"""ASR integration stubs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class Word:
    """Represents a single transcribed word."""

    index: int
    start: float
    end: float
    word: str
    probability: Optional[float] = None


def transcribe_to_words(path: Path) -> List[Word]:
    """Stub transcription implementation returning an empty result."""
    _ = path
    return []

