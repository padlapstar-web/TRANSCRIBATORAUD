#!/usr/bin/env python3
"""Binary and large file guard for the repository.

This script enforces two policies:
1. No tracked file may match known binary or media patterns.
2. No tracked file may exceed the configured size limit.

It is intended to run in CI, but can also be executed locally.
"""

from __future__ import annotations

import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

SIZE_LIMIT_BYTES = 2 * 1024 * 1024  # 2 MiB

# Patterns are intentionally broad to catch most binary artefacts that should not be committed.
DENYLIST_PATTERNS: Sequence[str] = (
    # Executables & native libraries
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.pyd",
    "*.lib",
    "*.a",
    "*.obj",
    "*.pdb",
    # Archives & installers
    "*.zip",
    "*.7z",
    "*.rar",
    "*.tar",
    "*.tar.gz",
    "*.tar.bz2",
    "*.tar.xz",
    "*.tgz",
    "*.tbz",
    "*.tbz2",
    "*.gz",
    "*.bz2",
    "*.xz",
    "*.lz",
    "*.lzma",
    # Media assets
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.svg",
    "*.ico",
    "*.icns",
    "*.tif",
    "*.tiff",
    "*.webp",
    "*.psd",
    "*.mp3",
    "*.wav",
    "*.ogg",
    "*.flac",
    "*.aac",
    "*.mp4",
    "*.m4a",
    "*.avi",
    "*.mov",
    "*.mkv",
    "*.webm",
    # Models & database files
    "*.bin",
    "*.pt",
    "*.onnx",
    "*.safetensors",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    # Fonts
    "*.ttf",
    "*.otf",
)


@dataclass
class Violation:
    path: Path
    reason: str

    def format(self, root: Path) -> str:
        rel_path = self.path.relative_to(root)
        return f"{rel_path} -> {self.reason}"


def run_git_command(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def repository_root() -> Path:
    return Path(run_git_command(["rev-parse", "--show-toplevel"]))


def tracked_files() -> List[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    paths = [Path(p) for p in output.decode().split("\0") if p]
    return paths


def matches_denylist(path: Path, patterns: Iterable[str]) -> bool:
    filename = path.name
    for pattern in patterns:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(str(path), pattern):
            return True
    return False


def check_files(root: Path) -> List[Violation]:
    violations: List[Violation] = []
    for relative_path in tracked_files():
        absolute_path = root / relative_path
        if not absolute_path.exists():
            # Skip deleted files that might still appear in git ls-files in sparse checkouts.
            continue

        if matches_denylist(relative_path, DENYLIST_PATTERNS):
            violations.append(
                Violation(absolute_path, "matches binary/media denylist"),
            )
            continue

        try:
            size = absolute_path.stat().st_size
        except OSError as exc:
            violations.append(Violation(absolute_path, f"unable to read file size: {exc}"))
            continue

        if size > SIZE_LIMIT_BYTES:
            violations.append(
                Violation(absolute_path, f"file size {size} bytes exceeds limit of {SIZE_LIMIT_BYTES} bytes"),
            )

    return violations


def main() -> int:
    try:
        root = repository_root()
    except subprocess.CalledProcessError as exc:
        print(f"Failed to determine repository root: {exc}", file=sys.stderr)
        return 2

    os.chdir(root)
    violations = check_files(root)

    if violations:
        print("Binary guard detected forbidden files:")
        for violation in violations:
            print(f"  - {violation.format(root)}")
        print("\nPlease remove these files from the repository or add them to an allowlist if absolutely necessary.")
        return 1

    print("Binary guard check passed: no forbidden files detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
