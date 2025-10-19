"""Model download helper with progress callbacks."""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable, Optional

from huggingface_hub import snapshot_download

from app.core.paths import HF_CACHE

log = logging.getLogger(__name__)

TRACKED_FILES = ["model.bin", "model.bin.*", "tokenizer.json", "config.json", "README.md"]

StatusCallback = Optional[Callable[[str], None]]
ProgressCallback = Optional[Callable[[int, int], None]]


def _bytes_fmt(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def ensure_model(
    repo_id: str,
    local_dir: str,
    on_status: StatusCallback = None,
    on_progress: ProgressCallback = None,
) -> str:
    """Ensure that the requested model snapshot exists locally and report progress."""

    path = Path(local_dir).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)

    if on_status:
        on_status(f"Проверка модели {repo_id}…")

    if os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") != "1":
        log.warning("hf_transfer не включен; установите HF_HUB_ENABLE_HF_TRANSFER=1 для ускорения.")

    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(HF_CACHE))
    if "HUGGINGFACE_HUB_CACHE" in os.environ:
        cache_info = os.environ["HUGGINGFACE_HUB_CACHE"]
        log.debug("Using HF cache: %s", cache_info)

    total_bytes = 0
    downloaded_bytes = 0

    def _tqdm_factory(*_args, **kwargs):
        class _Reporter:
            def __init__(self, total=None, **_kw):
                nonlocal total_bytes
                try:
                    total_bytes = int(total or 0)
                except (TypeError, ValueError):
                    total_bytes = 0

            def update(self, n):
                nonlocal downloaded_bytes
                try:
                    delta = int(n or 0)
                except (TypeError, ValueError):
                    delta = 0
                downloaded_bytes += delta
                if on_progress:
                    on_progress(downloaded_bytes, total_bytes)

            def close(self):
                pass

        return _Reporter(total=kwargs.get("total"))

    start = time.time()
    log.info("Prefetch model: repo_id=%s → %s", repo_id, path)
    if on_status:
        on_status("Подключение к Hugging Face…")

    snapshot_path = snapshot_download(
        repo_id=repo_id,
        local_dir=str(path),
        local_dir_use_symlinks=False,
        allow_patterns=TRACKED_FILES,
        resume_download=True,
        max_workers=4,
        tqdm_class=_tqdm_factory,
    )

    required_patterns = ["model.bin", "model.bin.*", "tokenizer.json", "config.json"]
    missing: list[str] = []
    snapshot_root = Path(snapshot_path)
    for pattern in required_patterns:
        if "*" in pattern:
            if not any(snapshot_root.glob(pattern)):
                missing.append(pattern)
        else:
            if not (snapshot_root / pattern).is_file():
                missing.append(pattern)
    if missing:
        raise RuntimeError(f"Модель скачана не полностью, отсутствуют: {', '.join(missing)}")

    elapsed = time.time() - start
    size_on_disk = sum(f.stat().st_size for f in Path(snapshot_path).rglob("*") if f.is_file())
    log.info("Model ready at %s (%s) за %.1f с", snapshot_path, _bytes_fmt(size_on_disk), elapsed)
    if on_status:
        on_status(f"Модель готова ({_bytes_fmt(size_on_disk)} за {elapsed:.1f}с)")
    if on_progress:
        on_progress(downloaded_bytes or size_on_disk, total_bytes or size_on_disk)
    return str(snapshot_path)
