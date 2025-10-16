"""Configuration helpers."""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

APPDATA = Path.home() / "AppData" / "Roaming" / "TRANSCRIBATORAUD"
CONFIG_PATH = APPDATA / "config.json"


@dataclass
class AppConfig:
    last_input: str | None = None
    last_output: str | None = None


def load_config() -> AppConfig:
    if CONFIG_PATH.exists():
        data: Dict[str, Any] = json.loads(CONFIG_PATH.read_text())
        return AppConfig(**data)
    return AppConfig()


def save_config(config: AppConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2))

