"""Qt worker thread for sequential transcription without multiprocessing."""

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from app.core.asr import Word, segments_to_words
from app.core.exporter import EXPORTERS, normalise_formats
from app.core.model_prefetch import ensure_local_model
from app.diagnostics.runtime_info import dump_runtime_info

__all__ = ["JobConfig", "TranscribeWorker"]

LOGGER = logging.getLogger(__name__)


@contextmanager
def _periodic_log(message: str, delay: float = 30.0, interval: float = 5.0):
    """Log *message* every ``interval`` seconds after ``delay`` seconds have passed."""

    stop_event = threading.Event()

    def _run() -> None:
        if not stop_event.wait(delay):
            while not stop_event.wait(interval):
                LOGGER.info(message)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop_event.set()
        thread.join(timeout=1)


def _gpu_available() -> bool:
    try:
        import ctranslate2 as ct2  # type: ignore

        return ct2.get_cuda_device_count() > 0
    except Exception:
        return False


def _gpu_name() -> str:
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return "nvidia-smi not found"
    proc = subprocess.run([nvsmi, "--query-gpu=name", "--format=csv,noheader"], capture_output=True, text=True)
    if proc.returncode != 0:
        return f"nvidia-smi exit {proc.returncode}"
    return (proc.stdout or "").strip() or "unknown GPU"


def _init_whisper(config: "JobConfig"):
    from faster_whisper import WhisperModel  # type: ignore

    base_env = os.getenv("LOCALAPPDATA")
    base_path = Path(base_env) if base_env else Path.home()
    models_root = base_path / "TranscribatorAud" / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    local_model_dir = Path(ensure_local_model(config.model_name, models_root))

    requested_device = config.device.lower()
    device = "cuda" if requested_device in {"cuda", "auto"} and _gpu_available() else "cpu"
    if requested_device == "cuda" and device != "cuda":
        LOGGER.warning("CUDA requested but not available, falling back to CPU")
    compute = config.compute_type.lower()
    if device == "cuda":
        if compute not in {"float16", "int8_float16"}:
            compute = "float16"
    else:
        if not compute.startswith("int8"):
            compute = "int8"

    LOGGER.info("Initialising Whisper from %s", local_model_dir)
    LOGGER.info("Device=%s (%s) compute_type=%s", device, _gpu_name() if device == "cuda" else "no GPU", compute)

    start = time.perf_counter()
    try:
        with _periodic_log("Whisper initialisation still in progress…"):
            model = WhisperModel(
                str(local_model_dir),
                device=device,
                compute_type=compute,
                local_files_only=True,
                device_index=0,
                cpu_threads=os.cpu_count() or 1,
            )
    except Exception as exc:
        if device == "cuda":
            LOGGER.warning("CUDA initialisation failed (%s). Retrying on CPU.", exc)
            with _periodic_log("Whisper CPU initialisation in progress…"):
                model = WhisperModel(
                    str(local_model_dir),
                    device="cpu",
                    compute_type="int8",
                    local_files_only=True,
                    device_index=0,
                    cpu_threads=os.cpu_count() or 1,
                )
            device = "cpu"
            compute = "int8"
        else:
            raise

    duration = time.perf_counter() - start
    LOGGER.info("Whisper ready in %.2fs", duration)
    return model, device, compute, duration

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
        self._logger = LOGGER.getChild("worker")

    def stop(self) -> None:
        """Request the worker to stop after the current file completes."""

        self._stop_requested = True

    def _log(self, message: str, level: int = logging.INFO) -> None:
        self._logger.log(level, message)
        self.log.emit(message)

    def _emit_error(self, message: str) -> None:
        self._log(message, logging.ERROR)
        self.error.emit(message)

    # Internal helpers -------------------------------------------------

    def _ensure_ffmpeg(self) -> Path:
        ffmpeg_path = self._config.ffmpeg
        if not ffmpeg_path or not ffmpeg_path.exists():
            raise FileNotFoundError("FFmpeg binary not found")
        self._log(f"Using FFmpeg at {ffmpeg_path}")
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
        self._log(f"FFmpeg decode: {' '.join(shlex.quote(arg) for arg in command)}")
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
            self._logger.exception("FFmpeg validation failed")
            self._emit_error(f"FFmpeg error: {exc!r} ({type(exc).__name__})")
            self.finished_all.emit()
            return

        if not self._files:
            self._log("Нет файлов для обработки")
            self.finished_all.emit()
            return

        try:
            dump_runtime_info()
        except Exception as exc:  # pragma: no cover - diagnostic failure should not abort
            self._logger.warning("Runtime diagnostics failed: %r", exc)

        try:
            self._log(
                f"Loading Whisper model '{self._config.model_name}' "
                f"({self._config.device}/{self._config.compute_type})"
            )
            model, resolved_device, resolved_compute, duration = _init_whisper(self._config)
            self._log(f"Model ready in {duration:.1f}s ({resolved_device}/{resolved_compute})")
        except Exception as exc:
            self._had_error = True
            self._logger.exception("Model initialisation failed")
            self._emit_error(f"Model init error: {exc!r} ({type(exc).__name__})")
            self.finished_all.emit()
            return

        total = len(self._files)
        self._log(f"Найдено файлов для обработки: {total}")
        for index, source in enumerate(self._files, start=1):
            if self._stop_requested:
                break
            try:
                self._log(f"[{index}/{total}] Decode: {source.name}")
                wav_path = self._decode_to_wav(ffmpeg_path, source)
                try:
                    self._log(f"[{index}/{total}] Transcribe: {source.name}")
                    words = self._transcribe_segments(model, wav_path, self._config.language)
                    self._export_outputs(words, source)
                    self._log(f"[{index}/{total}] Done: {source.name}")
                finally:
                    try:
                        os.remove(wav_path)
                    except OSError:
                        pass
            except Exception as exc:
                self._had_error = True
                self._logger.exception("Failed to process %s", source)
                self._emit_error(f"Failed to process {source}: {exc!r} ({type(exc).__name__})")

            percent = int(index * 100 / total)
            self.progress.emit(percent)

        self.finished_all.emit()

    @property
    def had_error(self) -> bool:
        return self._had_error

