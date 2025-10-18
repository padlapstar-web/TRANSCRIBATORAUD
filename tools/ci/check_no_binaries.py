#!/usr/bin/env python3
"""Fail the build if banned binary artefacts are committed or staged."""
from __future__ import annotations

import mimetypes
import os
import pathlib
import subprocess
import sys
from typing import Iterable, List, Sequence, Tuple

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

BAD_EXT = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".a",
    ".lib",
    ".pyd",
    ".o",
    ".obj",
    ".bin",
    ".dat",
    ".pack",
    ".zip",
    ".7z",
    ".rar",
    ".tar",
    ".gz",
    ".xz",
    ".mp3",
    ".wav",
    ".flac",
    ".aac",
    ".m4a",
    ".ogg",
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tiff",
    ".webp",
    ".pdf",
    ".psd",
    ".ai",
    ".sketch",
    ".ico",
    ".safetensors",
    ".pth",
    ".pt",
    ".onnx",
}

MAX_BYTES = 2_000_000


def git(args: Sequence[str]) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()


def run_git_optional(args: Sequence[str]) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def git_lines(args: Sequence[str]) -> List[str]:
    out = subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True)
    return [line for line in out.splitlines() if line.strip()]


def has_git_lfs_files() -> List[str]:
    try:
        out = subprocess.check_output(["git", "lfs", "ls-files"], cwd=REPO_ROOT, text=True)
    except FileNotFoundError:
        return []
    except subprocess.CalledProcessError:
        return []
    lines = [line.strip() for line in out.splitlines() if line.strip()]
    return lines


def iter_tracked_files() -> Iterable[pathlib.Path]:
    out = subprocess.check_output(["git", "ls-files", "-z"], cwd=REPO_ROOT)
    for rel in out.split(b"\0"):
        if not rel:
            continue
        yield REPO_ROOT / rel.decode("utf-8")


def is_text_file(path: pathlib.Path) -> bool:
    try:
        with path.open("rb") as fh:
            sample = fh.read(8192)
    except FileNotFoundError:
        return True
    if not sample:
        return True
    if b"\0" in sample:
        return False
    mime, _ = mimetypes.guess_type(path.as_posix())
    if mime is None:
        return True
    if mime.startswith("text"):
        return True
    if "yaml" in mime or "yml" in mime:
        return True
    return mime in {"application/json", "application/xml", "application/x-sh"}


def classify_file(path: pathlib.Path) -> Tuple[str, str | None]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    ext = path.suffix.lower()
    if ext in BAD_EXT:
        return rel, "banned-extension"
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return rel, None
    if size > MAX_BYTES:
        return rel, "too-large"
    if not is_text_file(path):
        return rel, "non-text"
    return rel, None


def diff_files() -> List[pathlib.Path]:
    base_ref = os.environ.get("GITHUB_BASE_REF")
    if base_ref:
        target = f"origin/{base_ref}"
    else:
        upstream = run_git_optional(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
        if upstream:
            target = upstream
        else:
            return []
    merge_base = run_git_optional(["merge-base", "HEAD", target])
    if not merge_base:
        return []
    names = git_lines(["diff", "--name-only", "--diff-filter=ACMRTUXB", merge_base, "HEAD"])
    return [REPO_ROOT / name for name in names]


def staged_files() -> List[pathlib.Path]:
    names = git_lines(["diff", "--name-only", "--cached", "--diff-filter=ACMRTUXB"])
    return [REPO_ROOT / name for name in names]


def main() -> int:
    errors: List[Tuple[str, str]] = []

    for path in iter_tracked_files():
        rel, problem = classify_file(path)
        if problem:
            errors.append((rel, problem))

    for path in diff_files() + staged_files():
        rel, problem = classify_file(path)
        if problem:
            errors.append((rel, f"diff-{problem}"))

    lfs_files = has_git_lfs_files()
    for entry in lfs_files:
        errors.append((entry, "git-lfs-tracked"))

    if errors:
        print("❌ Binary/forbidden artefacts detected:")
        for rel, reason in sorted(set(errors)):
            print(f" - {rel} -> {reason}")
        print("Remove the files above or move them to an ignored directory before committing.")
        return 1

    print("✅ No binaries or forbidden artefacts detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
