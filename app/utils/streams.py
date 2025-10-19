import io
import os
import sys
import threading
from typing import Optional

__all__ = ["hook_gui_streams"]

_LOCK = threading.RLock()
_LOG_FH: Optional[io.TextIOBase] = None


def _open_log_file(path: str) -> io.TextIOBase:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)


class _FileStream:
    """Fallback stream that writes redirected output into a log file."""

    def __init__(self, handle: io.TextIOBase) -> None:
        self._handle = handle

    def write(self, text: str) -> None:  # pragma: no cover - integration specific
        if not text:
            return
        with _LOCK:
            try:
                self._handle.write(text)
            except Exception:
                pass

    def flush(self) -> None:  # pragma: no cover - integration specific
        with _LOCK:
            try:
                self._handle.flush()
            except Exception:
                pass


def hook_gui_streams(log_path: Optional[str] = None) -> None:
    """Ensure stdout/stderr exist in windowed executables by redirecting to a log file."""

    global _LOG_FH

    if log_path is None:
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        log_path = os.path.join(base, "TranscribatorAud", "logs", "ext-stderr.log")

    if _LOG_FH is None:
        try:
            _LOG_FH = _open_log_file(log_path)
        except Exception:
            _LOG_FH = io.StringIO()

    if sys.stderr is None:
        sys.stderr = _FileStream(_LOG_FH)
    if sys.stdout is None:
        sys.stdout = _FileStream(_LOG_FH)
