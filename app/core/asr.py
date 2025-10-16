"""Speech recognition helpers built around faster-whisper."""
from __future__ import annotations

import importlib.util
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from app.core import models
from app.core.logging import setup_logging

_ROOT_LOGGER = setup_logging()
_LOGGER = _ROOT_LOGGER.getChild("asr")
_OOM_SIGNATURES: tuple[str, ...] = (
    "cuda out of memory",
    "failed to allocate memory",
    "cublas",
)


_ct_spec = importlib.util.find_spec("ctranslate2")
if _ct_spec is not None:  # pragma: no branch - import guard
    from ctranslate2 import errors as ct_errors  # type: ignore
else:  # pragma: no cover - fallback for optional dependency
    class _ErrorsModule:
        class CTranslate2Error(RuntimeError):
            """Fallback error type when ctranslate2 is unavailable."""

    ct_errors = _ErrorsModule()  # type: ignore[assignment]


_fw_spec = importlib.util.find_spec("faster_whisper")
if _fw_spec is not None:  # pragma: no branch - import guard
    from faster_whisper import WhisperModel  # type: ignore
else:  # pragma: no cover - fallback for optional dependency
    WhisperModel = None  # type: ignore[assignment]


@dataclass(slots=True)
class Word:
    """Represents a single transcribed word."""

    index: int
    start: float
    end: float
    word: str
    probability: Optional[float] = None

    def as_mapping(self) -> dict[str, object]:
        """Return a JSON-serialisable mapping of the word."""

        return {
            "i": self.index,
            "start": self.start,
            "end": self.end,
            "word": self.word,
            "prob": self.probability,
        }


def _punctuation_table() -> dict[int, None]:
    punctuation = string.punctuation + "«»„“”–—…"
    return str.maketrans({ch: "" for ch in punctuation})


def _instantiate_model(model_name: str, device: str, compute_type: str) -> WhisperModel:
    if WhisperModel is None:  # pragma: no cover - optional dependency
        raise RuntimeError("faster-whisper is not installed")
    model_path = models.get_model_path(model_name)
    source = str(model_path) if model_path else model_name
    _LOGGER.debug("Loading Whisper model %s from %s", model_name, source)
    return WhisperModel(source, device=device, compute_type=compute_type)


def _iter_words(segments: Iterable[object], keep_punct: bool) -> Iterable[Word]:
    punctuation_table = None if keep_punct else _punctuation_table()
    index = 1
    for segment in segments:
        for raw in getattr(segment, "words", []) or []:
            word_text = raw.word
            if not keep_punct and punctuation_table is not None:
                word_text = raw.word.translate(punctuation_table).strip()
                if not word_text:
                    continue
            start = float(raw.start if raw.start is not None else segment.start)
            end = float(raw.end if raw.end is not None else segment.end)
            probability = (
                float(raw.probability)
                if getattr(raw, "probability", None) is not None
                else None
            )
            yield Word(index=index, start=start, end=end, word=word_text, probability=probability)
            index += 1


def _should_retry_on_cpu(error: Exception) -> bool:
    message = str(error).lower()
    return any(signature in message for signature in _OOM_SIGNATURES)


def _normalise_device(device: Optional[str], compute_type: Optional[str]) -> Tuple[str, str]:
    device_value = (device or "auto").strip().lower()
    compute_value = (compute_type or "auto").strip().lower() if compute_type else "auto"

    resolved_device = device_value
    default_compute = "int8"
    if device_value in {"", "auto"}:
        resolved_device = "cpu"
        try:  # pragma: no cover - hardware dependent branch
            import torch  # type: ignore

            if hasattr(torch, "cuda") and torch.cuda.is_available():
                resolved_device = "cuda"
                default_compute = "float16"
            else:
                default_compute = "int8"
        except Exception:  # pragma: no cover - torch may be absent
            resolved_device = "cpu"
            default_compute = "int8"
    elif device_value == "cuda":
        resolved_device = "cuda"
        default_compute = "float16"
    else:
        resolved_device = device_value
        default_compute = "int8"

    if compute_value in {"", "auto"}:
        resolved_compute = default_compute
    else:
        resolved_compute = compute_value

    return resolved_device, resolved_compute


def transcribe_to_words(
    path: Path,
    model: str,
    device: Optional[str],
    compute_type: Optional[str],
    language: Optional[str],
    keep_punct: bool,
    vad: bool,
    beam_size: int = 5,
    *,
    _retried: bool = False,
) -> List[Word]:
    """Transcribe an audio file into a sequence of words."""

    audio_path = Path(path)
    if not audio_path.exists():
        raise FileNotFoundError(audio_path)

    language_arg: Optional[str]
    if language is None or language.lower() == "auto":
        language_arg = None
    else:
        language_arg = language

    device = device or "auto"
    compute_type = compute_type or "auto"
    resolved_device, resolved_compute_type = _normalise_device(device, compute_type)

    try:
        whisper = _instantiate_model(model, resolved_device, resolved_compute_type)
        segments, _info = whisper.transcribe(
            str(audio_path),
            beam_size=beam_size,
            language=language_arg,
            word_timestamps=True,
            vad_filter=vad,
        )
        return list(_iter_words(segments, keep_punct))
    except (RuntimeError, ct_errors.CTranslate2Error) as error:  # pragma: no cover - hardware specific
        if resolved_device.lower() != "cpu" and not _retried and _should_retry_on_cpu(error):
            _LOGGER.warning("CUDA OOM → fallback to CPU int8")
            return transcribe_to_words(
                audio_path,
                model,
                "cpu",
                "int8",
                language,
                keep_punct,
                vad,
                beam_size,
                _retried=True,
            )
        raise

