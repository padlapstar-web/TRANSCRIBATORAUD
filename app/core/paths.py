from __future__ import annotations

import os
from pathlib import Path

APP_DIR = Path(os.getenv("LOCALAPPDATA", ".")) / "TranscribatorAud"
MODELS_DIR = APP_DIR / "models"
TORCH_MODELS_DIR = APP_DIR / "torch_models"
HF_CACHE = Path(os.getenv("HUGGINGFACE_HUB_CACHE", str(APP_DIR / "hf_cache")))

MODELS_DIR.mkdir(parents=True, exist_ok=True)
TORCH_MODELS_DIR.mkdir(parents=True, exist_ok=True)
HF_CACHE.mkdir(parents=True, exist_ok=True)
