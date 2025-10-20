"""Helpers to launch a detached log tail console on Windows."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
CREATE_BREAKAWAY_FROM_JOB = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0x01000000)

_ENV_FLAG = "TRANSCRIBATORAUD_LOG_CONSOLE_ATTACHED"


def _write_tail_script(log_path: str, title: str, tail_lines: int) -> Path:
    """Persist a temporary PowerShell script that tails ``log_path``."""

    ps_path = Path(tempfile.gettempdir()) / "transaud_tail.ps1"
    content = (
        "$Host.UI.RawUI.WindowTitle = '{title}';\n"
        "$ProgressPreference = 'SilentlyContinue';\n"
        "$ErrorActionPreference = 'Continue';\n"
        "Write-Host ('Tailing: ' + '{log_path}');\n"
        f"Get-Content -Path '{log_path}' -Encoding UTF8 -Tail {tail_lines} -Wait;\n"
        "Write-Host '--- log tail ended ---';\n"
    ).format(title=title, log_path=log_path)
    ps_path.write_text(content, encoding="utf-8")
    return ps_path


def launch_log_console(log_path: str | Path, tail_lines: int = 300) -> Optional[subprocess.Popen]:
    """Spawn a dedicated console window that tails the provided log file."""

    if sys.platform != "win32":
        return None

    resolved = Path(log_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    if os.environ.get(_ENV_FLAG) == "1":
        return None

    script = _write_tail_script(str(resolved), "TranscribatorAud — logs", tail_lines)

    env = os.environ.copy()
    env[_ENV_FLAG] = "1"

    creationflags = CREATE_NEW_CONSOLE | CREATE_BREAKAWAY_FROM_JOB

    return subprocess.Popen(
        [
            "powershell.exe",
            "-NoLogo",
            "-NoProfile",
            "-NoExit",
            "-File",
            str(script),
        ],
        creationflags=creationflags,
        close_fds=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )
