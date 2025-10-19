"""Utilities for downloading Whisper models with progress and validation."""
from __future__ import annotations

import fnmatch
import logging
import os
import threading
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


class TqdmToLogger(tqdm):
    """Redirect tqdm updates into the application logger."""

    def display(self, msg: str | None = None, pos: int | None = None) -> None:  # noqa: D401
        if msg:
            log.info("[download] %s", msg)
        super().display(msg, pos)


def _log_model_bin_growth(directory: Path, stop_event: threading.Event, total_expected: int | None) -> None:
    """Continuously log growth of model.bin* files until ``stop_event`` is set."""

    last_size = -1
    while not stop_event.is_set():
        files = [p for p in directory.glob("model.bin*") if p.is_file()]
        total = sum(p.stat().st_size for p in files)
        if files and total != last_size:
            if total_expected:
                log.info("model.bin progress: %.2f / %.2f MB", total / (1024 * 1024), total_expected / (1024 * 1024))
            else:
                log.info("model.bin progress: %.2f MB", total / (1024 * 1024))
            last_size = total
        if stop_event.wait(1.0):
            break


def _patterns_match(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in REQUIRED_PATTERNS)


def prefetch_model(repo_id: str, target_dir: Path | None = None, revision: str = "main") -> Path:
    """Download all required CT2 model files into a local directory and return the path."""

    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE))
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")

    out_dir = Path(target_dir or (MODELS_DIR / repo_id.replace("/", "__")))
    out_dir.mkdir(parents=True, exist_ok=True)

    log.info("Prefetch model: repo_id=%s → %s", repo_id, out_dir)

    api = HfApi()
    try:
        info = api.model_info(repo_id, revision=revision)
    except Exception as exc:  # pragma: no cover - network issues
        log.error("HF API probe failed for %s: %s", repo_id, exc)
        raise

    matched_siblings = [s for s in info.siblings or [] if _patterns_match(s.rfilename)]
    total_remote_bytes = sum((s.size or 0) for s in matched_siblings)
    log.info(
        "Remote snapshot contains %d tracked files (%.2f MB)",
        len(matched_siblings),
        total_remote_bytes / (1024 * 1024) if total_remote_bytes else 0.0,
    )

    stop_event = threading.Event()
    watcher = threading.Thread(
        target=_log_model_bin_growth,
        args=(out_dir, stop_event, total_remote_bytes),
        daemon=True,
    )
    watcher.start()
    try:
        snapshot_download(
            repo_id=repo_id,
            revision=revision,
            local_dir=str(out_dir),
            local_dir_use_symlinks=False,
            allow_patterns=list(REQUIRED_PATTERNS),
            resume_download=True,
            max_workers=4,
            tqdm_class=TqdmToLogger,
            etag_timeout=30,
        )
    finally:
        stop_event.set()
        watcher.join(timeout=2)

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
