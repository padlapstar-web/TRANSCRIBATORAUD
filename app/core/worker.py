"""Qt worker thread for sequential transcription without multiprocessing."""
from __future__ import annotations

import logging
import os
import queue
import shlex
import subprocess
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from faster_whisper import WhisperModel

from app.core.asr import Word, segments_to_words
from app.core.exporter import EXPORTERS, normalise_formats
from app.core.model_prefetch import prefetch_model
from app.core.models import resolve_repo_id
from app.core.paths import MODELS_DIR
from app.diagnostics.runtime_info import dump_runtime_info

try:  # pragma: no cover - optional dependency for GUI runtime
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover - GUI not installed in some environments
    QThread = object  # type: ignore[misc,assignment]

    def Signal(*_args, **_kwargs):  # type: ignore[misc,assignment]
        return lambda *_a, **_k: None


__all__ = ["JobConfig", "TranscribeWorker", "load_model_with_timeout"]

LOGGER = logging.getLogger(__name__)
_REQUIRED_LOCAL_FILES = ("config.json", "tokenizer.json")


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


def _validate_local_model_dir(path: Path) -> Path:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Model directory not found: {path}")
    if not list(path.glob("model.bin*")):
        raise FileNotFoundError(f"model.bin* not found in {path}")
    for required in _REQUIRED_LOCAL_FILES:
        candidate = path / required
        if not candidate.exists():
            raise FileNotFoundError(f"{required} missing in {path}")
    return path


def _load_model_impl(
    repo_or_path: str,
    device: str,
    compute_type: str,
    download_root: Path | None,
    local_only: bool,
) -> WhisperModel:
    return WhisperModel(
        repo_or_path,
        device=device,
        compute_type=compute_type,
        download_root=str(download_root) if download_root else None,
        local_files_only=local_only,
        num_workers=1,
    )


def load_model_with_timeout(
    repo_id: str,
    *,
    prefer_cuda: bool = True,
    compute_type_cuda: str = "float16",
    compute_type_cpu: str = "int8",
    timeout_sec: int = 600,
    allow_download: bool = True,
) -> Tuple[WhisperModel, str, str]:
    """Initialise a WhisperModel with optional CUDA and a timeout."""

    repo_path = Path(repo_id)
    if repo_path.exists():
        local_dir = _validate_local_model_dir(repo_path)
    else:
        if not allow_download:
            raise RuntimeError("Model download disabled but local snapshot not found")
        target_dir = MODELS_DIR / repo_id.replace("/", "__")
        local_dir = prefetch_model(repo_id, target_dir=target_dir)

    device_try = "cuda" if prefer_cuda else "cpu"
    compute_try = compute_type_cuda if prefer_cuda else compute_type_cpu

    result_queue: "queue.Queue[Tuple[WhisperModel, str, str] | Exception]" = queue.Queue()

    def try_make(device: str, ctype: str, local_only: bool = True) -> WhisperModel:
        with _periodic_log("Whisper initialisation still in progress…"):
            return _load_model_impl(str(local_dir), device, ctype, download_root=local_dir.parent, local_only=local_only)

    def worker() -> None:
        try:
            model = try_make(device_try, compute_try, local_only=True)
            result_queue.put((model, device_try, compute_try))
        except Exception as cuda_exc:
            if device_try == "cuda":
                LOGGER.warning("CUDA init failed (%s). Falling back to CPU/int8…", cuda_exc)
                try:
                    model_cpu = try_make("cpu", compute_type_cpu, local_only=True)
                    result_queue.put((model_cpu, "cpu", compute_type_cpu))
                except Exception as cpu_exc:
                    result_queue.put(RuntimeError(f"Both CUDA and CPU init failed: {cuda_exc} // {cpu_exc}"))
            else:
                result_queue.put(cuda_exc)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        LOGGER.error("Model init timeout after %s sec", timeout_sec)
        raise TimeoutError(f"Model initialization exceeded {timeout_sec} seconds")

    result = result_queue.get()
    if isinstance(result, Exception):
        raise result

    model, device_used, compute_used = result
    try:
        LOGGER.info("Model initialized OK at %s (%s/%s)", local_dir, device_used, compute_used)
    except Exception:  # pragma: no cover - logging shouldn't break execution
        pass
    return model, device_used, compute_used


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
    local_model_dir: Path | None = None
    allow_download: bool = True


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

    def _transcribe_segments(self, model: WhisperModel, wav_path: Path, language: str) -> List[Word]:
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

        prefer_cuda = self._config.device.lower() in {"cuda", "auto"}
        compute_raw = self._config.compute_type.lower()
        compute_cuda = compute_raw if compute_raw in {"float16", "int8_float16", "int8"} else "float16"
        compute_cpu = compute_raw if compute_raw.startswith("int8") else "int8"

        repo_id = resolve_repo_id(self._config.model_name)
        try:
            if self._config.local_model_dir is not None:
                local_dir = _validate_local_model_dir(self._config.local_model_dir)
                source_identifier = str(local_dir)
                allow_download = False
            else:
                source_identifier = repo_id
                allow_download = self._config.allow_download

            self._log(
                f"Loading Whisper model '{self._config.model_name}' "
                f"({self._config.device}/{self._config.compute_type})"
            )
            model, resolved_device, resolved_compute = load_model_with_timeout(
                source_identifier,
                prefer_cuda=prefer_cuda,
                compute_type_cuda=compute_cuda,
                compute_type_cpu=compute_cpu,
                timeout_sec=600,
                allow_download=allow_download,
            )
            self._log(
                f"Model ready ({resolved_device}/{resolved_compute}). Starting transcription of {len(self._files)} file(s)."
            )
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
