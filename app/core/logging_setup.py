"""Compatibility wrapper for the relocated logging setup helpers."""
from __future__ import annotations

from app.logging_setup import (
    get_file_log_path_fallback,
    get_log_file_path,
    setup_logging,
)

__all__ = [
    "get_file_log_path_fallback",
    "get_log_file_path",
    "setup_logging",
]
