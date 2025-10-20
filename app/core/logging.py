"""Compatibility wrapper around the new logging setup module."""
from __future__ import annotations

import logging

from app.logging_setup import setup_logging as _setup_logging


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configure logging via :mod:`logging_setup` and return a namespaced logger."""

    _setup_logging(debug=debug)
    return logging.getLogger("transcribatoraud")

