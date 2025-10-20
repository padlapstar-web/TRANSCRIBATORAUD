"""Helpers for working with locally cached Whisper models."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.core.paths import MODELS_DIR


def resolve_repo_id(name: str) -> str:
    """Normalise a model selector to a Hugging Face repo identifier."""

    if "/" in name:
        return name
    return f"Systran/faster-whisper-{name}"


def iter_local_models() -> Iterable[Path]:
    if MODELS_DIR.exists():
        yield from (path for path in MODELS_DIR.iterdir() if path.is_dir())
    else:
        return


def get_model_path(name: str) -> Path | None:
    repo = resolve_repo_id(name).replace("/", "__")
    candidate = MODELS_DIR / repo
    return candidate if candidate.exists() else None
