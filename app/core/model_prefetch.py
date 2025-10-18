"""Utilities to ensure Whisper models are available locally."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from huggingface_hub import snapshot_download

_LOGGER = logging.getLogger(__name__)


def resolve_repo_id(model_name: str) -> str:
    """Resolve a user-provided model name to a HuggingFace repo id."""

    if "/" in model_name:
        return model_name
    return f"Systran/faster-whisper-{model_name}"


def ensure_local_model(model_name: str, local_root: str | os.PathLike[str]) -> str:
    """Guarantee that the requested model is stored locally and return its path."""

    if os.path.isdir(model_name) and os.path.exists(os.path.join(model_name, "model.bin")):
        _LOGGER.info("Using pre-downloaded model directory: %s", model_name)
        return model_name

    repo_id = resolve_repo_id(model_name)
    target = Path(local_root) / repo_id.replace("/", "__")
    target.mkdir(parents=True, exist_ok=True)

    _LOGGER.info("Prefetch model: repo_id=%s → %s", repo_id, target)
    snapshot_download(
        repo_id=repo_id,
        local_dir=str(target),
        local_dir_use_symlinks=False,
        resume_download=True,
        max_workers=1,
        allow_patterns=["*"],
    )
    _LOGGER.info("Prefetch done for %s", repo_id)
    return str(target)
