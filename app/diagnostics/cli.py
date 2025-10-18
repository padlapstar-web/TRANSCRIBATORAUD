"""Standalone diagnostics entry point."""
from __future__ import annotations

import argparse
import logging
import os

from app.core.logging_setup import setup_logging
from app.core.model_prefetch import ensure_local_model
from app.diagnostics.runtime_info import dump_runtime_info


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostics for TRANSCRIBATORAUD")
    parser.add_argument("--model", default="small", help="Model name or local path")
    args = parser.parse_args()

    log_file = setup_logging(debug=True)
    logging.getLogger(__name__).info("Diagnostics log file: %s", log_file)
    dump_runtime_info()

    models_root = os.path.join(os.getenv("LOCALAPPDATA", os.path.expanduser("~")), "TranscribatorAud", "models")
    local_model = ensure_local_model(args.model, models_root)
    logging.getLogger(__name__).info("Model cached at %s", local_model)
    logging.getLogger(__name__).info("Diagnostics completed")
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    raise SystemExit(main())
