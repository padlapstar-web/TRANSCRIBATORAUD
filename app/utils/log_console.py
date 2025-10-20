"""Utilities to spawn a detached log console on Windows."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

CREATE_NEW_CONSOLE = 0x00000010


def spawn_detached_log_console(log_path: str | Path) -> None:
    """Launch a detached console tailing ``log_path`` on Windows."""

    if sys.platform != "win32":
        return

    resolved = Path(log_path).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get("TRANSCRIBATORAUD_LOG_CONSOLE_ATTACHED") == "1":
        return

    ps_cmd = f"Get-Content -LiteralPath {shlex.quote(str(resolved))} -Tail 300 -Wait"
    cmd = [
        "cmd.exe",
        "/K",
        "powershell",
        "-NoLogo",
        "-NoProfile",
        "-Command",
        ps_cmd,
    ]

    env = os.environ.copy()
    env["TRANSCRIBATORAUD_LOG_CONSOLE_ATTACHED"] = "1"

    subprocess.Popen(
        cmd,
        creationflags=CREATE_NEW_CONSOLE,
        close_fds=True,
        env=env,
    )
