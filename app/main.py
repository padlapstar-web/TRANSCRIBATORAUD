"""Entry point for TRANSCRIBATORAUD application."""
from __future__ import annotations

import os
from app.utils.streams import hook_gui_streams

# Гарантируем корректные stdout/stderr и отключаем прогресс-бары HF до любых импортов hub.
hook_gui_streams()
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_ENABLE_XET", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import argparse
import sys
from pathlib import Path
from typing import Sequence

from app.cli import run_cli
from app.core.ffmpeg import find_ffmpeg
from app.core.logging_setup import setup_logging
from app.diagnostics.runtime_info import dump_runtime_info


def _prepend_ffmpeg_to_path() -> None:
    """Ensure bundled ffmpeg binaries are available via PATH."""

    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    candidate_dirs = [
        root / "resources" / "ffmpeg" / "bin",
        root / "resources" / "ffmpeg",
    ]

    existing = [path for path in candidate_dirs if path.is_dir()]
    if not existing:
        return

    path_env = os.environ.get("PATH", "")
    prefixes = os.pathsep.join(str(path) for path in existing)
    os.environ["PATH"] = prefixes + (os.pathsep + path_env if path_env else "")


_prepend_ffmpeg_to_path()


def _run_gui() -> int:
    try:
        from PySide6 import QtCore
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - GUI dependency missing
        print(
            "PySide6 не найден. Установите зависимости (pip install -r requirements.txt) "
            "или используйте CLI: python app/cli.py ...",
            file=sys.stderr,
        )
        return 1

    from app.ui.main_window import MainWindow
    from app.ui.console import LogDock

    log_file = setup_logging(debug=True)
    dump_runtime_info()
    app = QApplication(sys.argv)
    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        print(f"FFmpeg обнаружен: {ffmpeg_path}")
    else:
        print(
            "Внимание: FFmpeg не найден. Установите ffmpeg и добавьте его в PATH или переменные окружения.",
            file=sys.stderr,
        )
    window = MainWindow()
    window.set_log_file_path(Path(log_file))
    console = LogDock(window)
    window.addDockWidget(QtCore.Qt.BottomDockWidgetArea, console)
    console.attach_root_logger()
    window.show()
    return app.exec()


def _enable_console() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        if ctypes.windll.kernel32.GetConsoleWindow():  # type: ignore[attr-defined]
            return
        ctypes.windll.kernel32.AllocConsole()  # type: ignore[attr-defined]
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", buffering=1)
    except Exception:
        pass


def main(argv: Sequence[str] | None = None) -> int:
    """Run GUI by default, fall back to CLI if arguments are provided."""

    raw_args = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--console", action="store_true")
    known, remainder = parser.parse_known_args(raw_args[1:])

    if known.console:
        _enable_console()

    if remainder:
        return run_cli(remainder)

    return _run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
