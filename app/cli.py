"""Command line interface bootstrap."""
from __future__ import annotations

import argparse
from typing import Iterable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcribatoraud",
        description="Offline batch transcription tool (stub).",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Path to an audio file or folder. Implementation pending.",
    )
    return parser


def run_cli(args: Iterable[str]) -> int:
    parser = build_parser()
    parser.parse_args(list(args))
    parser.print_help()
    return 0

