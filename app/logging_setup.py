"""Central logging configuration for TranscribatorAud."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app.core.paths import APP_DIR

LOG_DIR = APP_DIR / "logs"
LOG_FILE = LOG_DIR / "app.log"
_MARKER = "_transaud_logging_configured"


def setup_logging(debug: bool = False) -> str:
    """Configure root logging and return the absolute log file path."""

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if debug else logging.INFO
    root = logging.getLogger()

    if getattr(root, _MARKER, False):
        root.setLevel(level)
        for handler in root.handlers:
            handler.setLevel(level)
        return str(LOG_FILE)

    root.handlers.clear()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("huggingface_hub").setLevel(logging.INFO if not debug else logging.DEBUG)
    logging.getLogger("ctranslate2").setLevel(logging.DEBUG if debug else logging.INFO)
    logging.getLogger("ext.stderr").setLevel(logging.DEBUG)

    setattr(root, _MARKER, True)
    return str(LOG_FILE)


def get_log_file_path() -> Path:
    """Return the path to the primary application log file."""

    return LOG_FILE


def get_file_log_path_fallback() -> Optional[Path]:
    """Return the active file-handler path if logging was already configured."""

    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, logging.FileHandler):
            try:
                return Path(handler.baseFilename)
            except Exception:
                continue
    return None
