"""Runtime diagnostics used during startup."""
from __future__ import annotations

import logging
import os
import platform
import shutil
import time
from typing import Dict

import ctranslate2 as ct2
import requests
from faster_whisper import __version__ as FW_VERSION
import huggingface_hub
import tokenizers


def check_hf_cdn() -> Dict[str, str]:
    urls = [
        "https://huggingface.co",
        "https://cdn-lfs.huggingface.co",
    ]
    results: Dict[str, str] = {}
    for url in urls:
        start = time.time()
        try:
            response = requests.head(url, timeout=5)
            results[url] = f"{response.status_code} in {time.time() - start:.2f}s"
        except Exception as exc:  # pragma: no cover - network dependent
            results[url] = f"ERR: {exc}"
    return results


def dump_runtime_info() -> None:
    """Log key runtime diagnostics for troubleshooting."""

    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "faster_whisper": FW_VERSION,
        "huggingface_hub": huggingface_hub.__version__,
        "tokenizers": tokenizers.__version__,
        "cuda_devices": None,
        "nvidia_smi": shutil.which("nvidia-smi") or "not found",
        "ffmpeg": shutil.which("ffmpeg") or "not found",
        "HF_HOME": os.getenv("HF_HOME"),
    }
    try:
        info["cuda_devices"] = ct2.get_cuda_device_count()
    except Exception as exc:  # pragma: no cover - hardware dependent
        info["cuda_devices"] = f"error: {exc}"

    logger = logging.getLogger(__name__)
    for key, value in info.items():
        logger.info("[diag] %s: %s", key, value)

    cdn_results = check_hf_cdn()
    for url, status in cdn_results.items():
        logger.info("[diag] hf_cdn %s: %s", url, status)
