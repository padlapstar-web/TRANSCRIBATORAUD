"""Qt worker thread for sequential transcription without multiprocessing."""
from __future__ import annotations

import logging
import os
import queue
import shlex
import shutil
import subprocess
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List, Sequence, Tuple

import sys

from faster_whisper import WhisperModel

from app.core.asr import Word
from app.core.backends import ASRBackend, FasterWhisperBackend, TorchWhisperBackend
from app.core.exporter import EXPORTERS, normalise_formats
from app.core.model_prefetch import VOCABULARY_CANDIDATES, ensure_model, validate_snapshot
from app.core.models import resolve_repo_id
from app.core.paths import MODELS_DIR, TORCH_MODELS_DIR
from app.diagnostics.runtime_info import dump_runtime_info

try:  # pragma: no cover - optional dependency for GUI runtime
    from PySide6.QtCore import QThread, Signal
except ImportError:  # pragma: no cover - GUI not installed in some environments
    QThread = object  # type: ignore[misc,assignment]

    def Signal(*_args, **_kwargs):  # type: ignore[misc,assignment]
        return lambda *_a, **_k: None


__all__ = ["JobConfig", "TranscribeWorker", "load_whisper"]

LOGGER = logging.getLogger(__name__)

_TORCH_MODEL_MAP = {
    "tiny": "tiny",
    "tiny.en": "tiny.en",
    "base": "base",
    "base.en": "base.en",
    "small": "small",
    "small.en": "small.en",
    "medium": "medium",
    "medium.en": "medium.en",
    "large": "large",
    "large-v2": "large-v2",
    "large-v3": "large-v3",
}


def _normalise_model_name(model_name: str) -> str:
    tail = model_name.strip().lower()
    if "/" in tail:
        tail = tail.split("/")[-1]
    if tail.startswith("faster-whisper-"):
        tail = tail[len("faster-whisper-") :]
    return tail


def _resolve_torch_model(model_name: str) -> str:
    normalised = _normalise_model_name(model_name)
    for key, mapped in _TORCH_MODEL_MAP.items():
        if normalised == key:
            return mapped
    # fallback: try to match by prefix (e.g. "medium-int8")
    for key, mapped in _TORCH_MODEL_MAP.items():
        if normalised.startswith(key):
            return mapped
    LOGGER.warning("Unknown model '%s' for torch backend; defaulting to 'medium'", model_name)
    return "medium"


def _torch_cuda_available() -> bool:
    try:
        import torch  # type: ignore

        return bool(getattr(torch, "cuda", None)) and torch.cuda.is_available()
    except Exception:  # pragma: no cover - torch optional
        return False
class CancelledError(RuntimeError):
    """Raised when the user cancels the running job."""


def _gpu_name() -> str:
    candidate = shutil.which("nvidia-smi")
    if not candidate:
        return "nvidia-smi not found"
    try:
        result = subprocess.run(
            [candidate, "--query-gpu=name,pci.bus_id", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = (result.stdout or "").strip()
        if output:
            return output
    except Exception as exc:  # pragma: no cover - diagnostics only
        LOGGER.debug("Failed to query GPU name: %r", exc)
    return "unknown GPU"


def _validate_local_model_dir(path: Path) -> Path:
    ok, issues = validate_snapshot(path)
    if not ok:
        details = ', '.join(f"{name}: {reason}" for name, reason in issues.items()) or 'unknown error'
        raise FileNotFoundError(f"Model directory invalid: {path} ({details})")
    return path


def _percent(done: int, total: int) -> int:
    if total <= 0:
        return 0
    return max(0, min(100, int(done * 100 / total)))


def _try_windows_torch_backend(
    model_name: str,
    *,
    dtype: str,
    status_cb: Callable[[str], None] | None,
) -> tuple[ASRBackend, str, str, Path] | None:
    if sys.platform != "win32":
        return None
    if not _torch_cuda_available():
        return None
    torch_model = _resolve_torch_model(model_name)
    cache_dir = TORCH_MODELS_DIR / torch_model.replace("/", "__")
    try:
        backend = TorchWhisperBackend(torch_model, device="cuda", dtype=dtype, cache_dir=cache_dir)
    except ImportError as exc:  # pragma: no cover - torch not installed
        LOGGER.warning("PyTorch not installed (%s); fallback to CPU", exc)
        return None
    except Exception as exc:  # pragma: no cover - backend init issues
        LOGGER.warning("Torch backend initialisation failed: %s", exc)
        if status_cb:
            status_cb("PyTorch backend не запустился, используем CPU.")
        return None
    if status_cb:
        status_cb("Запущен PyTorch backend (CUDA).")
    LOGGER.info(
        "Using torch backend %s on CUDA (cache=%s)",
        backend.info.name,
        cache_dir,
    )
    return backend, "cuda", "float16", cache_dir


def _periodic_log(message: str, delay: float = 30.0, interval: float = 5.0):
    """Yield a context manager logging *message* periodically while active."""

    class _PeriodicLogger:
        def __init__(self) -> None:
            self._stop = threading.Event()
            self._thread = threading.Thread(target=self._run, daemon=True)

        def __enter__(self):
            self._thread.start()
            return self

        def __exit__(self, *_exc):
            self._stop.set()
            self._thread.join(timeout=1)

        def _run(self) -> None:
            if not self._stop.wait(delay):
                while not self._stop.wait(interval):
                    LOGGER.info(message)

    return _PeriodicLogger()


def load_whisper(
    repo_id: str,
    *,
    prefer_cuda: bool = True,
    compute_type_cuda: str = "float16",
    compute_type_cpu: str = "int8",
    timeout_sec: int = 600,
    local_override: Path | None = None,
    allow_download: bool = True,
    offline: bool = False,
    status_cb: Callable[[str], None] | None = None,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Tuple[ASRBackend, str, str, Path]:
    """Load a transcription backend ensuring the model is available locally."""

    os.environ.setdefault("CT2_VERBOSE", "1")
    os.environ.setdefault("CT2_LOG_LEVEL", "INFO")

    if not offline and os.environ.get("TRANSCRIBATORAUD_OFFLINE") == "1":
        offline = True

    if offline:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")

    torch_candidate: tuple[ASRBackend, str, str, Path] | None = None
    if prefer_cuda and sys.platform == "win32":
        torch_candidate = _try_windows_torch_backend(repo_id, dtype=compute_type_cuda, status_cb=status_cb)
        if torch_candidate is None:
            LOGGER.warning(
                "CUDA запрос отклонён: PyTorch backend недоступен или не инициализировался. Используем CPU.",
            )
            if status_cb:
                status_cb("CUDA недоступна, выполняем на CPU.")
            prefer_cuda = False
        else:
            return torch_candidate

    if local_override is not None:
        model_dir = _validate_local_model_dir(local_override)
    else:
        if not allow_download:
            raise RuntimeError("Model download disabled but local snapshot not found")
        target_dir = MODELS_DIR / repo_id.replace("/", "__")
        model_dir = Path(
            ensure_model(
                repo_id,
                str(target_dir),
                on_status=status_cb,
                on_progress=progress_cb,
                allow_download=allow_download,
                offline=offline,
            )
        )

    if progress_cb:
        try:
            progress_cb(1, 1)
        except Exception:
            LOGGER.exception("progress callback failed")

    timeout_limit = max(60, int(timeout_sec))

    def _attempt(device: str, compute: str) -> WhisperModel:
        if status_cb:
            status_cb(f"Инициализация модели на {device}/{compute}…")
        LOGGER.info("Loading Whisper model (%s/%s) from %s", device, compute, model_dir)
        result_queue: "queue.Queue[WhisperModel | Exception]" = queue.Queue()

        def _target() -> None:
            try:
                with _periodic_log("Whisper initialisation still in progress…"):
                    model_instance = WhisperModel(
                        str(model_dir),
                        device=device,
                        compute_type=compute,
                        local_files_only=True,
                        download_root=str(model_dir.parent),
                        num_workers=1,
                    )
                result_queue.put(model_instance)
            except Exception as exc:  # pragma: no cover - handled at call site
                result_queue.put(exc)

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout_limit)
        if thread.is_alive():
            LOGGER.error("Model init timeout after %s sec", timeout_limit)
            raise TimeoutError(f"Model initialization exceeded {timeout_limit} seconds")
        result = result_queue.get()
        if isinstance(result, Exception):
            raise result
        return result

    attempts: list[Tuple[str, str]] = []
    if prefer_cuda and sys.platform != "win32":
        attempts.append(("cuda", compute_type_cuda))
    attempts.append(("cpu", compute_type_cpu))

    last_error: Exception | None = None
    repair_attempted = False
    for device_name, compute_name in attempts:
        while True:
            try:
                model_instance = _attempt(device_name, compute_name)
                descriptor = _gpu_name() if device_name == "cuda" else "CPU"
                LOGGER.info("Model initialised using %s/%s (%s)", device_name, compute_name, descriptor)
                if status_cb:
                    status_cb("Модель инициализирована.")
                backend = FasterWhisperBackend(model_instance, device_name, compute_name)
                return backend, device_name, compute_name, model_dir
            except Exception as exc:
                last_error = exc
                LOGGER.warning("Failed to initialise Whisper on %s/%s: %s", device_name, compute_name, exc)
                message = str(exc).lower()
                tokenizer_issue = any(key in message for key in ("vocabulary", "tokenizer", "tokeniser"))
                if allow_download and not repair_attempted and tokenizer_issue:
                    LOGGER.warning("Tokenizer validation failed during init; refreshing local files.")
                    if status_cb:
                        status_cb("Повреждён токенизатор модели, выполняем повторную загрузку…")
                    model_dir = Path(
                        ensure_model(
                            repo_id,
                            str(model_dir),
                            on_status=status_cb,
                            on_progress=progress_cb,
                            force_files=("tokenizer.json", "config.json", *VOCABULARY_CANDIDATES),
                        )
                    )
                    repair_attempted = True
                    continue
                if device_name == "cuda" and status_cb:
                    status_cb("CUDA недоступна, переключаемся на CPU…")
                break

    assert last_error is not None
    raise last_error

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
    offline: bool = False
    init_timeout: int = 600


class TranscribeWorker(QThread):  # pragma: no cover - exercised via GUI runtime
    """Sequential transcription worker compatible with frozen PyInstaller builds."""

    log = Signal(str)
    status = Signal(str)
    download_progress = Signal(int)
    progress = Signal(int)
    done_file = Signal(str)
    finished_all = Signal()
    error = Signal(str)

    def __init__(self, config: JobConfig, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._files = [Path(path) for path in config.files]
        self._cancel_requested = False
        self._had_error = False
        self._formats = normalise_formats(config.formats)
        self._logger = LOGGER.getChild("worker")

    def stop(self) -> None:  # pragma: no cover - invoked from UI thread
        """Request the worker to stop after the current file completes."""

        self._cancel_requested = True

    def _check_cancelled(self) -> None:
        if self._cancel_requested:
            raise CancelledError("Operation cancelled by user")

    def _log(self, message: str, level: int = logging.INFO) -> None:
        self._logger.log(level, message)
        self.log.emit(message)

    def _emit_status(self, message: str) -> None:
        self.status.emit(message)

    def _emit_download_progress(self, done: int, total: int) -> None:
        percent = _percent(done, total)
        self.download_progress.emit(percent)

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

    def _transcribe_segments(self, backend: ASRBackend, wav_path: Path, language: str) -> List[Word]:
        language_arg = None if not language or language.lower() == "auto" else language
        return backend.transcribe(wav_path, language=language_arg, beam_size=self._config.beam_size)

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
            self.error.emit(f"FFmpeg error: {exc!r} ({type(exc).__name__})")
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
        backend: ASRBackend | None = None

        try:
            self._check_cancelled()
            backend, resolved_device, resolved_compute, _model_dir = load_whisper(
                repo_id,
                prefer_cuda=prefer_cuda,
                compute_type_cuda=compute_cuda,
                compute_type_cpu=compute_cpu,
                timeout_sec=self._config.init_timeout,
                local_override=self._config.local_model_dir,
                allow_download=self._config.allow_download,
                offline=self._config.offline or not self._config.allow_download,
                status_cb=self._emit_status,
                progress_cb=self._emit_download_progress,
            )
            self.download_progress.emit(100)
            self._check_cancelled()
            self._log(
                f"Backend {backend.info.engine} готов ({resolved_device}/{resolved_compute}). Обрабатываем {len(self._files)} файл(ов)."
            )
        except CancelledError:
            self._log("Операция отменена пользователем до старта транскрибации.")
            self.finished_all.emit()
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    self._logger.debug("Backend close failed", exc_info=True)
            return
        except Exception as exc:
            self._had_error = True
            self._logger.exception("Model initialisation failed")
            if isinstance(exc, TimeoutError):
                friendly = "Инициализация превысила лимит времени. Проверьте сеть/CDN или используйте офлайн модель."
            else:
                friendly = f"Model init error: {exc!r} ({type(exc).__name__})"
            self.error.emit(friendly)
            self.finished_all.emit()
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    self._logger.debug("Backend close failed", exc_info=True)
            return

        total = len(self._files)
        self._log(f"Найдено файлов для обработки: {total}")

        try:
            for index, source in enumerate(self._files, start=1):
                try:
                    self._check_cancelled()
                except CancelledError:
                    self._log("Операция отменена пользователем.")
                    break
                try:
                    self._log(f"[{index}/{total}] Decode: {source.name}")
                    wav_path = self._decode_to_wav(ffmpeg_path, source)
                    try:
                        self._check_cancelled()
                        self._log(f"[{index}/{total}] Transcribe: {source.name}")
                        assert backend is not None
                        words = self._transcribe_segments(backend, wav_path, self._config.language)
                        self._export_outputs(words, source)
                        self._log(f"[{index}/{total}] Done: {source.name}")
                    finally:
                        try:
                            os.remove(wav_path)
                        except OSError:
                            pass
                except CancelledError:
                    self._log("Операция отменена пользователем.")
                    break
                except Exception as exc:
                    self._had_error = True
                    self._logger.exception("Failed to process %s", source)
                    self.error.emit(f"Failed to process {source}: {exc!r} ({type(exc).__name__})")

                percent = int(index * 100 / total)
                self.progress.emit(percent)
        finally:
            self.finished_all.emit()
            if backend is not None:
                try:
                    backend.close()
                except Exception:
                    self._logger.debug("Backend close failed", exc_info=True)

    @property
    def had_error(self) -> bool:
        return self._had_error
