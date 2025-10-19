import os
import logging
from typing import Callable, Optional

from huggingface_hub import snapshot_download

log = logging.getLogger(__name__)

FILES = ["model.bin", "tokenizer.json", "config.json", "README.md"]


def ensure_model(
    repo_id: str,
    local_dir: str,
    on_status: Optional[Callable[[str], None]] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> str:
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
    os.environ.setdefault("HF_HUB_ENABLE_XET", "1")

    os.makedirs(local_dir, exist_ok=True)

    def _status(msg: str) -> None:
        if on_status:
            try:
                on_status(msg)
            except Exception:
                log.exception("status callback failed")
        log.info(msg)

    _status("Подключение к Hugging Face…")

    if on_progress:
        try:
            on_progress(0, 1)
        except Exception:
            log.exception("progress callback failed")

    try:
        path = snapshot_download(
            repo_id=repo_id,
            local_dir=local_dir,
            local_dir_use_symlinks=False,
            allow_patterns=FILES,
            resume_download=True,
            max_workers=4,
            tqdm_class=None,
        )
    except Exception:
        log.exception("snapshot_download failed")
        raise

    missing = [
        name
        for name in ("model.bin", "tokenizer.json", "config.json")
        if not os.path.isfile(os.path.join(path, name))
    ]
    if missing:
        raise RuntimeError("Модель скачана не полностью: " + ", ".join(missing))

    if on_progress:
        try:
            on_progress(1, 1)
        except Exception:
            log.exception("progress callback failed")

    return path
