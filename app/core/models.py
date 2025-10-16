"""Model discovery helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

_APP_NAME = "TRANSCRIBATORAUD"


def _appdata_root() -> Path:
    appdata_env = os.environ.get("APPDATA")
    if appdata_env:
        return Path(appdata_env) / _APP_NAME
    return Path.home() / f".{_APP_NAME.lower()}"


MODELS_DIR = _appdata_root() / "models"


def get_model_path(name: str) -> Optional[Path]:
    """Return a path to a locally available model if it exists."""

    candidate = MODELS_DIR / name
    if candidate.exists():
        return candidate

    if not candidate.suffix and (candidate.with_suffix(".bin")).exists():
        return candidate.with_suffix(".bin")

    return None


def list_available_models() -> list[str]:
    """List locally available model names."""

    if not MODELS_DIR.exists():
        return []
    return sorted({item.stem for item in MODELS_DIR.iterdir() if item.is_file()})

