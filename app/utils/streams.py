import sys
import threading
from typing import Optional

__all__ = ["hook_gui_streams"]


_local = threading.local()


def _write_to_stream(stream: Optional[object], text: str) -> None:
    if stream is None or not text:
        return
    try:
        stream.write(text)
    except Exception:
        pass


class _SafeStream:
    """Fallback stream writing directly to the original std handles."""

    def __init__(self, fallback: Optional[object]) -> None:
        self._fallback = fallback

    def write(self, text: str) -> None:  # pragma: no cover - integration path
        if not text:
            return
        target = self._fallback or getattr(sys, "__stderr__", None) or getattr(sys, "__stdout__", None)
        if target is None:
            return
        if getattr(_local, "in_write", False):
            _write_to_stream(target, text)
            return
        try:
            _local.in_write = True
            _write_to_stream(target, text)
        finally:
            _local.in_write = False

    def flush(self) -> None:  # pragma: no cover - integration path
        target = self._fallback or getattr(sys, "__stderr__", None) or getattr(sys, "__stdout__", None)
        if target is None:
            return
        try:
            target.flush()
        except Exception:
            pass


def hook_gui_streams(log_path: Optional[str] = None) -> None:
    """Replace absent stdout/stderr with safe fallbacks for GUI executables."""

    _ = log_path  # preserved for backwards compatibility

    if getattr(sys, "stderr", None) is None:
        sys.stderr = _SafeStream(getattr(sys, "__stderr__", None))
    if getattr(sys, "stdout", None) is None:
        sys.stdout = _SafeStream(getattr(sys, "__stdout__", None))
