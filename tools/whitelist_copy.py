#!/usr/bin/env python3
"""Restore files from a clean branch based on a whitelist of patterns."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from fnmatch import fnmatch
from typing import Iterable, Iterator, List

DEFAULT_SOURCE_BRANCH = "codex/prepare-for-audio-transcription-app"

ALLOW_PATTERNS: List[str] = [
    "app/**",
    "scripts/**",
    "tools/**",
    "pyproject.toml",
    "poetry.lock",
    "requirements*.txt",
    "setup.cfg",
    "setup.py",
    "README.md",
    "LICENSE",
    "Makefile",
    ".gitignore",
    "*.py",
    "*.pyi",
    "*.md",
    "*.txt",
    "*.toml",
    "*.json",
    "*.yaml",
    "*.yml",
    "*.cfg",
    "*.ini",
    "*.lock",
    "*.sh",
    "*.ps1",
    "*.bat",
    "*.rst",
]

DENY_PATTERNS: List[str] = [
    "dist/**",
    "build/**",
    ".mypy_cache/**",
    ".pytest_cache/**",
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.exe",
    "*.db",
    "*.sqlite",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.ogg",
    "*.zip",
    "*.tar",
    "*.tar.gz",
    "*.7z",
    "*.pdf",
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.bmp",
    "*.ico",
    "*.icns",
    "*.ttf",
    "*.otf",
    "*.log",
]


def run_git_command(args: List[str]) -> subprocess.CompletedProcess[str]:
    """Run a git command and return the completed process."""
    return subprocess.run(["git", *args], check=True, text=True, capture_output=True)


def iter_branch_files(branch: str) -> Iterator[str]:
    """Yield file paths from *branch* tracked by git."""
    result = run_git_command(["ls-tree", "-r", "--full-tree", "--name-only", branch])
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            yield line


def is_allowed(path: str) -> bool:
    """Return True if *path* matches allow rules and not deny rules."""
    if not any(fnmatch(path, pattern) for pattern in ALLOW_PATTERNS):
        return False
    return not any(fnmatch(path, pattern) for pattern in DENY_PATTERNS)


def chunked(iterable: Iterable[str], size: int) -> Iterator[List[str]]:
    """Yield lists of length *size* from *iterable*."""
    chunk: List[str] = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def checkout_paths(branch: str, paths: List[str], dry_run: bool) -> None:
    for batch in chunked(paths, 100):
        if dry_run:
            print(f"Would checkout {len(batch)} paths from {branch}:")
            for path in batch:
                print(f"  {path}")
            continue
        subprocess.run(["git", "checkout", branch, "--", *batch], check=True)


def ensure_git_repo() -> None:
    try:
        run_git_command(["rev-parse", "--is-inside-work-tree"])
    except subprocess.CalledProcessError as exc:  # pragma: no cover - safety net
        raise SystemExit("This script must be run inside a git repository") from exc


def ensure_branch_exists(branch: str) -> None:
    try:
        run_git_command(["rev-parse", "--verify", branch])
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Source branch '{branch}' not found") from exc


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-branch",
        default=os.environ.get("SOURCE_BRANCH", DEFAULT_SOURCE_BRANCH),
        help="Branch containing the clean files to restore.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be restored without checking out files.",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    ensure_git_repo()
    ensure_branch_exists(args.source_branch)

    selected = [path for path in iter_branch_files(args.source_branch) if is_allowed(path)]

    if not selected:
        print("No paths matched the whitelist.")
        return 0

    print(f"Restoring {len(selected)} file(s) from {args.source_branch}...")
    checkout_paths(args.source_branch, selected, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
