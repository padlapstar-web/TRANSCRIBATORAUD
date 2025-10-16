"""Model discovery helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

APPDATA = Path.home() / "AppData" / "Roaming" / "TRANSCRIBATORAUD"
MODELS_DIR = APPDATA / "models"


def get_model_path(name: str) -> Optional[Path]:
    candidate = MODELS_DIR / name
    return candidate if candidate.exists() else None

