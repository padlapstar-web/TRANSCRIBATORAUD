"""YAML-backed configuration helpers."""
from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

_APP_NAME = "TRANSCRIBATORAUD"


def _appdata_root() -> Path:
    appdata_env = os.environ.get("APPDATA")
    if appdata_env:
        return Path(appdata_env) / _APP_NAME
    return Path.home() / f".{_APP_NAME.lower()}"


CONFIG_PATH = _appdata_root() / "config.yaml"


@dataclass
class AppConfig:
    last_input: str | None = None
    last_output: str | None = None
    model: str = "base"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "auto"
    formats: List[str] = field(default_factory=lambda: ["jsonl"])
    keep_punct: bool = True
    vad: bool = False
    parallel: int = 1


def load_config() -> AppConfig:
    """Load persisted configuration values."""

    if CONFIG_PATH.exists():
        raw: Dict[str, Any] = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        return AppConfig(**raw)
    return AppConfig()


def save_config(config: AppConfig) -> None:
    """Persist configuration values to disk."""

    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(asdict(config), handle, allow_unicode=True, sort_keys=False)

