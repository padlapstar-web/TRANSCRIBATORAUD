"""Utilities for downloading Whisper models with progress and validation."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Sequence

from huggingface_hub import HfApi, snapshot_download
from tqdm import tqdm

from app.core.paths import HF_CACHE, MODELS_DIR

log = logging.getLogger(__name__)

REQUIRED_PATTERNS: Sequence[str] = (
    "config.json",
    "model.bin*",
    "tokenizer.json",
    "vocabulary.txt",
    "README.md",
)


def prefetch_model(repo_id: str, target_dir: Path | None = None, revision: str = "main") -> Path:
    """Download all required CT2 model files into a local directory and return the path."""

    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE))
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    out_dir = Path(target_dir or (MODELS_DIR / repo_id.replace("/", "__")))
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Prefetch model: repo_id=%s → %s", repo_id, out_dir)

    try:
        HfApi().model_info(repo_id, revision=revision)
    except Exception as exc:  # pragma: no cover - network issues
        log.error("HF API probe failed for %s: %s", repo_id, exc)
        raise

    snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=str(out_dir),
        local_dir_use_symlinks=False,
        allow_patterns=list(REQUIRED_PATTERNS),
        resume_download=True,
        max_workers=4,
        tqdm_class=tqdm,
        etag_timeout=30,
    )

    required_bins = list(out_dir.glob("model.bin*"))
    if not required_bins:
        raise FileNotFoundError(f"model.bin* not found in {out_dir}")
    if not (out_dir / "config.json").exists():
        raise FileNotFoundError(f"config.json not found in {out_dir}")
    if not (out_dir / "tokenizer.json").exists():
        raise FileNotFoundError(f"tokenizer.json not found in {out_dir}")

    total_bytes = sum(p.stat().st_size for p in out_dir.glob("**/*") if p.is_file())
    total_files = sum(1 for _ in out_dir.rglob("*"))
    log.info("Model ready at %s (%.2f MB, %d files)", out_dir, total_bytes / (1024 ** 2), total_files)
    return out_dir
