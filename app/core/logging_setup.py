"""Comprehensive logging configuration for GUI and CLI modes."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.paths import APP_DIR

_LOGGER_ATTR = "_transcribatoraud_logging_configured"


def _logs_root() -> Path:
    return APP_DIR / "logs"


def setup_logging(debug: bool = False) -> str:
    """Initialise application-wide logging and return the log file path."""

    log_dir = _logs_root()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] [%(threadName)s] %(name)s: %(message)s"

    root = logging.getLogger()
    already_configured: Optional[bool] = getattr(root, _LOGGER_ATTR, None)

    if already_configured:
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
        return str(log_file)

    root.setLevel(level)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(stream_handler)

    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(file_handler)

    hf_level = logging.DEBUG if debug else logging.WARNING
    logging.getLogger("huggingface_hub").setLevel(hf_level)
    logging.getLogger("hf_transfer").setLevel(hf_level)
    logging.getLogger("ctranslate2").setLevel(logging.DEBUG if debug else logging.INFO)

    setattr(root, _LOGGER_ATTR, True)
    return str(log_file)
