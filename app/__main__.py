"""Application entry-point orchestrating logging console spawning."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")


def _parse_args(argv: list[str]) -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--log-console", action="store_true", default=False)
    try:
        ns, remainder = parser.parse_known_args(argv)
    except SystemExit:
        class _NS:
            log_console = False

        return _NS(), argv
    return ns, remainder


def _install_excepthook() -> None:
    def _hook(exc_type, exc, tb):
        logging.critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        try:
            sys.__excepthook__(exc_type, exc, tb)
        finally:
            for handler in logging.getLogger().handlers:
                flush = getattr(handler, "flush", None)
                if callable(flush):
                    try:
                        flush()
                    except Exception:
                        pass

    sys.excepthook = _hook


def _maybe_spawn_log_console() -> None:
    from app.core.logging_setup import get_file_log_path_fallback, setup_logging
    from app.utils.log_console import spawn_detached_log_console

    log_path = get_file_log_path_fallback()
    if log_path is None:
        log_path = Path(setup_logging(debug=True))
    spawn_detached_log_console(log_path)


def main() -> None:
    argv = sys.argv[1:]
    ns, remainder = _parse_args(argv)
    sys.argv = [sys.argv[0], *remainder]

    _install_excepthook()

    want_console = ns.log_console or os.environ.get("TRANSCRIBATORAUD_LOG_CONSOLE") == "1"
    if want_console and sys.platform == "win32":
        _maybe_spawn_log_console()

    from app import main as app_main

    raise SystemExit(app_main.main())


if __name__ == "__main__":
    main()
