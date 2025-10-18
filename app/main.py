"""Entry point for TRANSCRIBATORAUD application."""
from __future__ import annotations
import os
import sys
from typing import Sequence

from app.cli import run_cli
from app.core.ffmpeg import find_ffmpeg


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
        from PySide6.QtWidgets import QApplication
    except ImportError as exc:  # pragma: no cover - GUI dependency missing
        print(
            "PySide6 не найден. Установите зависимости (pip install -r requirements.txt) "
            "или используйте CLI: python app/cli.py ...",
            file=sys.stderr,
        )
        return 1

    from app.ui.main_window import MainWindow

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
    window.show()
    return app.exec()


def main(argv: Sequence[str] | None = None) -> int:
    """Run GUI by default, fall back to CLI if arguments are provided."""
    args = list(sys.argv if argv is None else argv)

    if len(args) > 1:
        return run_cli(args[1:])

    return _run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
