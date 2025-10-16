"""Batch processing placeholder."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, List


def discover_inputs(source: Path, recursive: bool = False) -> List[Path]:
    """Return discovered inputs (stub)."""
    _ = (source, recursive)
    return []


def process_batch(paths: Iterable[Path]) -> None:
    """Process a batch of paths (stub)."""
    for path in paths:
        print(f"Processing {path} (stub)")

