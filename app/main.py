"""Entry point for TRANSCRIBATORAUD application."""
from __future__ import annotations

import sys
from typing import Sequence

from app.cli import run_cli
from app.ui.main_window import launch_gui


def main(argv: Sequence[str] | None = None) -> int:
    """Run GUI by default, fall back to CLI if arguments are provided."""
    args = list(sys.argv if argv is None else argv)

    if len(args) > 1:
        return run_cli(args[1:])

    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
