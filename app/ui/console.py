"""Dockable logging console for the Qt GUI."""
from __future__ import annotations

import logging

from PySide6 import QtCore, QtGui, QtWidgets


class QtLogHandler(logging.Handler, QtCore.QObject):
    """Bridge Python logging records into Qt signals."""

    log_signal = QtCore.Signal(str)

    def __init__(self) -> None:
        logging.Handler.__init__(self)
        QtCore.QObject.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - GUI runtime
        try:
            message = self.format(record)
        except Exception:  # pragma: no cover - formatting failures
            return
        self.log_signal.emit(message)


class LogDock(QtWidgets.QDockWidget):  # pragma: no cover - GUI runtime
    """Simple dock widget that displays log messages."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("Console", parent)
        self.setObjectName("ConsoleDock")
        self._text = QtWidgets.QPlainTextEdit(self)
        self._text.setReadOnly(True)
        self.setWidget(self._text)
        self._handler: QtLogHandler | None = None

    def attach_root_logger(self) -> None:
        handler = QtLogHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        handler.log_signal.connect(self._append_message)
        logging.getLogger().addHandler(handler)
        self._handler = handler

    @QtCore.Slot(str)
    def _append_message(self, message: str) -> None:
        self._text.appendPlainText(message)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # type: ignore[override]
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None
        super().closeEvent(event)
