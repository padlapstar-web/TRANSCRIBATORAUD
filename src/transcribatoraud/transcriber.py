"""Core transcription domain objects and services.

This module provides a small abstraction layer on top of the Whisper
transcription models so that the rest of the application can rely on a
simple, well typed API.  The actual model implementation is loaded on demand
which keeps import time fast and allows the project to run without the heavy
``faster-whisper`` dependency being installed (useful for unit tests and
continuous integration in the early development stages).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional


@dataclass(slots=True)
class TranscriptionSegment:
    """A single piece of the transcription timeline."""

    start: float
    end: float
    text: str
    probability: Optional[float] = None


@dataclass(slots=True)
class TranscriptionResult:
    """Container with the full transcription output."""

    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: Optional[str] = None
    duration: Optional[float] = None

    @property
    def text(self) -> str:
        """Return the concatenated transcription text."""

        return " ".join(segment.text.strip() for segment in self.segments if segment.text)


@dataclass(slots=True)
class TranscriptionConfig:
    """Configuration used when building the Whisper model."""

    model_size: str = "medium"
    compute_type: str = "int8"
    beam_size: int = 5
    vad_filter: bool = True
    language: Optional[str] = None

    def model_kwargs(self) -> dict[str, object]:
        """Return keyword arguments for the Whisper model factory."""

        return {"compute_type": self.compute_type}

    def transcription_kwargs(self, *, language: Optional[str] = None) -> dict[str, object]:
        """Return keyword arguments for the ``transcribe`` call."""

        effective_language = language or self.language
        kwargs: dict[str, object] = {
            "beam_size": self.beam_size,
            "vad_filter": self.vad_filter,
        }
        if effective_language:
            kwargs["language"] = effective_language
        return kwargs


class WhisperTranscriber:
    """Lazy wrapper around the Whisper model implementation."""

    def __init__(self, config: Optional[TranscriptionConfig] = None, *, lazy_load: bool = True) -> None:
        self.config = config or TranscriptionConfig()
        self._model = None

        if not lazy_load:
            self._ensure_model()

    def _ensure_model(self):
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel  # type: ignore import-not-found
        except ImportError as exc:  # pragma: no cover - exercised when dependency missing
            raise RuntimeError(
                "The optional dependency 'faster-whisper' is not installed. "
                "Install project dependencies to enable transcription."
            ) from exc

        model = WhisperModel(self.config.model_size, **self.config.model_kwargs())
        self._model = model
        return model

    def transcribe(self, source: Path | str, *, language: Optional[str] = None) -> TranscriptionResult:
        """Transcribe the provided audio file."""

        audio_path = Path(source)
        if not audio_path.exists():
            raise FileNotFoundError(audio_path)

        model = self._ensure_model()
        segments_iter, info = model.transcribe(
            str(audio_path),
            **self.config.transcription_kwargs(language=language),
        )

        return TranscriptionResult(
            segments=list(_map_segments(segments_iter)),
            language=info.language if getattr(info, "language", None) else language or self.config.language,
            duration=getattr(info, "duration", None),
        )


def _map_segments(segments: Iterable[object]) -> Iterable[TranscriptionSegment]:
    for segment in segments:
        # ``faster-whisper`` segments expose ``start``, ``end``, ``text`` and ``avg_logprob``
        probability = None
        if hasattr(segment, "avg_logprob") and segment.avg_logprob is not None:
            probability = math.exp(segment.avg_logprob)
        yield TranscriptionSegment(
            start=float(getattr(segment, "start", 0.0)),
            end=float(getattr(segment, "end", 0.0)),
            text=str(getattr(segment, "text", "")).strip(),
            probability=probability,
        )
