import os
import sys
import io
import threading
from typing import Optional

_LOCK = threading.RLock()
_LOG_FH = None  # type: Optional[io.TextIOBase]

def _open_log_file(path: str) -> io.TextIOBase:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)


class _FileStream:
    """Поток для подмены sys.stderr/sys.stdout в GUI-сборке без консоли.
    Пишет только в файл, чтобы исключить рекурсию через logging.
    """

    def __init__(self, fh: io.TextIOBase):
        self._fh = fh

    def write(self, s: str):
        if not s:
            return
        with _LOCK:
            try:
                self._fh.write(s)
            except Exception:
                pass

    def flush(self):
        with _LOCK:
            try:
                self._fh.flush()
            except Exception:
                pass


def hook_gui_streams(log_path: Optional[str] = None):
    """Подменяет stdout/stderr, если приложение запущено как оконное."""

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
