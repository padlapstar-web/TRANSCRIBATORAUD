"""Executable entry point for launching the TranscribatorAud GUI."""
from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import List

os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

def _install_global_hooks() -> None:
    """Capture uncaught exceptions and Qt messages into the application log."""

    def _excepthook(exc_type, exc, tb):
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

    sys.excepthook = _excepthook

    try:
        from PySide6.QtCore import QtMsgType, qInstallMessageHandler

        def _qt_handler(mode, context, message):
            level_map = {
                QtMsgType.QtDebugMsg: logging.DEBUG,
                QtMsgType.QtInfoMsg: logging.INFO,
                QtMsgType.QtWarningMsg: logging.WARNING,
                QtMsgType.QtCriticalMsg: logging.ERROR,
                QtMsgType.QtFatalMsg: logging.CRITICAL,
            }
            logging.log(level_map.get(mode, logging.INFO), "Qt: %s (%s:%s)", message, context.file, context.line)

        qInstallMessageHandler(_qt_handler)
    except Exception:
        pass


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--debug-console", action="store_true", help="Open dedicated log console window")
    try:
        ns, remainder = parser.parse_known_args(argv)
    except SystemExit:
        class _NS:
            debug_console = False
        ns = _NS()
        remainder = argv
    sys.argv = [sys.argv[0], *remainder]
    return ns


def _should_launch_console(ns: argparse.Namespace) -> bool:
    env_flag = os.environ.get("TRANSCRIBATORAUD_LOG_CONSOLE")
    if env_flag == "0":
        return False
    if ns.debug_console or env_flag == "1":
        return True
    if getattr(sys, "frozen", False):
        return True
    return False


def main() -> None:
    args = _parse_args(sys.argv[1:])

    from app.logging_setup import setup_logging
    from app.utils.log_console import launch_log_console

    log_path = setup_logging()
    _install_global_hooks()

    if _should_launch_console(args) and sys.platform == "win32":
        try:
            launch_log_console(log_path)
        except Exception:
            logging.exception("Failed to launch log console")

    from app import main as app_main

    raise SystemExit(app_main.main())


if __name__ == "__main__":
    main()
