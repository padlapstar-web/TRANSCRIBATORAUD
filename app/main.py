"""Entry point for TRANSCRIBATORAUD application."""
from __future__ import annotations

import os
import sys
from typing import Sequence

from app.cli import run_cli


def _prepend_ffmpeg_to_path() -> None:
    """Ensure bundled ffmpeg binaries are available via PATH."""
    root = os.path.dirname(os.path.dirname(__file__))
    ffmpeg_dir = os.path.join(root, "resources", "ffmpeg")
    if os.path.isdir(ffmpeg_dir):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


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
