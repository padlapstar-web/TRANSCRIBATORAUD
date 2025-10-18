"""Minimal placeholder for the future PySide6 GUI."""
from __future__ import annotations

import importlib.util
from typing import Optional, Tuple

QtWidgets = "PySide6.QtWidgets"


def _load_widgets() -> Optional[Tuple[type, type, type]]:
    if importlib.util.find_spec(QtWidgets) is None:  # pragma: no cover - optional dependency
        return None
    from PySide6.QtWidgets import QApplication, QLabel, QWidget  # type: ignore

    return QApplication, QLabel, QWidget


def launch_gui() -> int:
    """Launch a minimal window or print a placeholder message."""

    widgets = _load_widgets()
    if widgets is None:
        print("PySide6 is not available yet. GUI will be implemented later.")
        return 0

    QApplication, QLabel, QWidget = widgets
    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("TRANSCRIBATORAUD (stub)")
    label = QLabel("GUI implementation is coming soon", parent=window)
    label.setMargin(24)
    window.resize(480, 160)
    window.show()
    return app.exec()

