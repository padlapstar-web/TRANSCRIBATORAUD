"""Logging helpers."""
from __future__ import annotations

import logging
from pathlib import Path

APPDATA = Path.home() / "AppData" / "Roaming" / "TRANSCRIBATORAUD"
LOG_DIR = APPDATA / "logs"


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "transcribatoraud.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
    return logging.getLogger("transcribatoraud")

