"""Minimal placeholder for the future PySide6 GUI."""
from __future__ import annotations

try:
    from PySide6.QtWidgets import QApplication, QLabel, QWidget
except Exception:  # pragma: no cover - optional dependency during bootstrap
    QApplication = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QWidget = None  # type: ignore[assignment]


def launch_gui() -> int:
    """Launch a minimal window or print a placeholder message."""
    if QApplication is None:
        print("PySide6 is not available yet. GUI will be implemented later.")
        return 0

    app = QApplication([])
    window = QWidget()
    window.setWindowTitle("TRANSCRIBATORAUD (stub)")
    label = QLabel("GUI implementation is coming soon", parent=window)
    label.setMargin(24)
    window.resize(480, 160)
    window.show()
    return app.exec()

