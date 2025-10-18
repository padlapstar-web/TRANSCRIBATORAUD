"""Qt worker thread for sequential transcription without multiprocessing."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from app.core.asr import Word, segments_to_words
from app.core.exporter import EXPORTERS, normalise_formats

__all__ = ["JobConfig", "TranscribeWorker"]

try:  # pragma: no cover - optional dependency for GUI runtime
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover - GUI not installed in some environments
    QThread = object  # type: ignore[misc,assignment]
    Signal = lambda *args, **kwargs: None  # type: ignore[misc,assignment]


@dataclass(slots=True)
class JobConfig:
    """Configuration for a transcription job executed in a dedicated thread."""

    ffmpeg: Path
    files: Sequence[Path]
    formats: Sequence[str]
    model_name: str
    device: str
    compute_type: str
    language: str
    output_dir: Path
    beam_size: int = 1


class TranscribeWorker(QThread):  # pragma: no cover - exercised via GUI runtime
    """Sequential transcription worker compatible with frozen PyInstaller builds."""

    log = Signal(str)
    progress = Signal(int)
    done_file = Signal(str)
    finished_all = Signal()
    error = Signal(str)

    def __init__(self, config: JobConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._files = [Path(path) for path in config.files]
        self._stop_requested = False
        self._had_error = False
        self._formats = normalise_formats(config.formats)

    def stop(self) -> None:
        """Request the worker to stop after the current file completes."""

        self._stop_requested = True

    # Internal helpers -------------------------------------------------

    def _ensure_ffmpeg(self) -> Path:
        ffmpeg_path = self._config.ffmpeg
        if not ffmpeg_path or not ffmpeg_path.exists():
            raise FileNotFoundError("FFmpeg binary not found")
        return ffmpeg_path

    def _decode_to_wav(self, ffmpeg_path: Path, source: Path) -> Path:
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        destination = Path(tmp_path)
        command: List[str] = [
            str(ffmpeg_path),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(destination),
        ]
        self.log.emit(f"FFmpeg decode: {' '.join(shlex.quote(arg) for arg in command)}")
        try:
            process = subprocess.run(
                command,
                capture_output=True,
                check=False,
                text=False,
                timeout=600,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"ffmpeg timeout for {source}") from exc
        if process.returncode != 0:
            stderr = process.stderr.decode("utf-8", "ignore") if process.stderr else ""
            raise RuntimeError(f"ffmpeg failed for {source}: {stderr}")
        return destination

    def _transcribe_segments(self, model, wav_path: Path, language: str) -> List[Word]:
        language_arg = None if not language or language.lower() == "auto" else language
        segments, _info = model.transcribe(
            str(wav_path),
            beam_size=self._config.beam_size,
            language=language_arg,
            word_timestamps=True,
            vad_filter=False,
        )
        return list(segments_to_words(segments, keep_punct=True))

    def _export_outputs(self, words: Iterable[Word], source: Path) -> None:
        output_dir = self._config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        for fmt in self._formats:
            exporter = EXPORTERS[fmt]
            destination = output_dir / f"{source.stem}.words.{fmt}"
            exporter(words, destination)
            self.done_file.emit(str(destination))

    # QThread entry point ----------------------------------------------

    def run(self) -> None:  # type: ignore[override]
        try:
            ffmpeg_path = self._ensure_ffmpeg()
        except Exception as exc:
            self._had_error = True
            self.error.emit(str(exc))
            self.finished_all.emit()
            return

        if not self._files:
            self.finished_all.emit()
            return

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency issue
            self._had_error = True
            self.error.emit(f"Failed to import faster_whisper: {exc}")
            self.finished_all.emit()
            return

        model = None
        try:
            start = time.time()
            device = self._config.device.lower()
            compute_type = self._config.compute_type
            self.log.emit(
                f"Loading Whisper model '{self._config.model_name}' ({device}/{compute_type})"
            )
            try:
                model = WhisperModel(
                    self._config.model_name,
                    device=device,
                    compute_type=compute_type,
                    local_files_only=False,
                )
            except Exception as exc:
                if device == "cuda":
                    self.log.emit(f"CUDA init failed ({exc}); fallback to CPU int8")
                    model = WhisperModel(
                        self._config.model_name,
                        device="cpu",
                        compute_type="int8",
                        local_files_only=False,
                    )
                else:
                    raise
            duration = time.time() - start
            self.log.emit(f"Model ready in {duration:.1f}s")
        except Exception as exc:
            self._had_error = True
            self.error.emit(f"Model init error: {exc}")
            self.finished_all.emit()
            return

        total = len(self._files)
        self.log.emit(f"Найдено файлов для обработки: {total}")
        for index, source in enumerate(self._files, start=1):
            if self._stop_requested:
                break
            try:
                self.log.emit(f"[{index}/{total}] Decode: {source.name}")
                wav_path = self._decode_to_wav(ffmpeg_path, source)
                try:
                    self.log.emit(f"[{index}/{total}] Transcribe: {source.name}")
                    words = self._transcribe_segments(model, wav_path, self._config.language)
                    self._export_outputs(words, source)
                    self.log.emit(f"[{index}/{total}] Done: {source.name}")
                finally:
                    try:
                        os.remove(wav_path)
                    except OSError:
                        pass
            except Exception as exc:
                self._had_error = True
                self.error.emit(f"Failed to process {source}: {exc}")

            percent = int(index * 100 / total)
            self.progress.emit(percent)

        self.finished_all.emit()

    @property
    def had_error(self) -> bool:
        return self._had_error

