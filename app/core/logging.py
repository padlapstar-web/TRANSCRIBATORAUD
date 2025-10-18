"""Logging helpers for the application."""
from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path

_APP_NAME = "TRANSCRIBATORAUD"


def _appdata_root() -> Path:
    appdata_env = os.environ.get("APPDATA")
    if appdata_env:
        return Path(appdata_env) / _APP_NAME
    return Path.home() / f".{_APP_NAME.lower()}"


def setup_logging() -> logging.Logger:
    """Configure application logging with daily file rotation."""

    log_dir = _appdata_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now():%Y-%m-%d}.txt"

    logger = logging.getLogger("transcribatoraud")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger

