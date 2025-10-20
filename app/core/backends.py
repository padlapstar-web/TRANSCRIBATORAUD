"""Abstractions for transcription backends (faster-whisper / torch)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from app.core.asr import Word, segments_to_words

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class BackendInfo:
    name: str
    device: str
    compute_type: str
    engine: str


class ASRBackend:
    """Common interface for transcription engines."""

    def __init__(self, info: BackendInfo) -> None:
        self.info = info

    def transcribe(self, wav_path: Path, *, language: Optional[str], beam_size: int) -> List[Word]:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - backends may not need explicit cleanup
        return


class FasterWhisperBackend(ASRBackend):
    def __init__(self, model, device: str, compute_type: str, engine: str = "faster-whisper") -> None:
        super().__init__(BackendInfo(name="whisper", device=device, compute_type=compute_type, engine=engine))
        self._model = model

    def transcribe(self, wav_path: Path, *, language: Optional[str], beam_size: int) -> List[Word]:
        language_arg = None if not language or language.lower() == "auto" else language
        segments, _info = self._model.transcribe(
            str(wav_path),
            beam_size=beam_size,
            language=language_arg,
            word_timestamps=True,
            vad_filter=False,
        )
        return list(segments_to_words(segments, keep_punct=True))


class TorchWhisperBackend(ASRBackend):
    def __init__(
        self,
        model_name: str,
        device: str,
        dtype: str,
        cache_dir: Path,
    ) -> None:
        import torch  # type: ignore
        import whisper  # type: ignore

        cache_dir.mkdir(parents=True, exist_ok=True)

        dtype_normalised = dtype.lower()
        torch_dtype = torch.float16 if dtype_normalised in {"float16", "fp16", "int8"} else torch.float32

        LOGGER.info("Loading torch whisper model %s on %s (%s)", model_name, device, torch_dtype)
        model = whisper.load_model(model_name, device=device, download_root=str(cache_dir), dtype=torch_dtype)
        info = BackendInfo(name=model_name, device=device, compute_type=str(torch_dtype), engine="torch-whisper")
        super().__init__(info)
        self._model = model

    def transcribe(self, wav_path: Path, *, language: Optional[str], beam_size: int) -> List[Word]:
        options = dict(
            language=None if not language or language.lower() == "auto" else language,
            word_timestamps=True,
            verbose=False,
            beam_size=beam_size,
        )
        result = self._model.transcribe(str(wav_path), **options)
        words: List[Word] = []
        index = 1
        for segment in result.get("segments", []):
            for raw in segment.get("words", []) or []:
                word_text = str(raw.get("word", "")).strip()
                if not word_text:
                    continue
                start = float(raw.get("start", segment.get("start", 0.0)))
                end = float(raw.get("end", segment.get("end", start)))
                probability = raw.get("probability")
                prob_value: Optional[float]
                try:
                    prob_value = float(probability) if probability is not None else None
                except (TypeError, ValueError):
                    prob_value = None
                words.append(Word(index=index, start=start, end=end, word=word_text, probability=prob_value))
                index += 1
        return words
