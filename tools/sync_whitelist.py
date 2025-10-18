#!/usr/bin/env python3
"""Sync whitelisted files from polluted branch without pulling binaries."""
import os
import subprocess
import sys
from pathlib import Path

SRC_REF = sys.argv[1] if len(sys.argv) > 1 else "origin/codex/prepare-for-audio-transcription-app"
ROOT = Path(__file__).resolve().parents[1]

ALLOW_DIRS = {
    "app",
    "build",
    "tools",
    ".github/workflows",
    "docs",
    "tests",
}

ALLOW_FILES = {
    "README.md",
    "LICENSE",
    "requirements.txt",
    "pyproject.toml",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
}

BAD_EXT = {
    ".exe",
    ".dll",
    ".bin",
    ".pyd",
    ".lib",
    ".so",
    ".dylib",
    ".a",
    ".whl",
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
    ".onnx",
    ".safetensors",
    ".pt",
    ".pth",
    ".iso",
    ".img",
}

BAD_DIRS = {
    "dist",
    "build/pyinstaller",
    "build/output",
    "build/cache",
    ".venv",
    "__pycache__",
    "pycache",
    "models",
    "resources/ffmpeg",
}


def git_ls(ref: str) -> list[str]:
    out = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", ref], text=True)
    return [p for p in out.splitlines() if p]


def allowed(path: str) -> bool:
    p = Path(path).as_posix()
    for bad in BAD_DIRS:
        if p == bad or p.startswith(bad.rstrip("/") + "/"):
            return False
    if Path(p).suffix.lower() in BAD_EXT:
        return False
    if p in ALLOW_FILES:
        return True
    top = p.split("/", 1)[0]
    return top in ALLOW_DIRS


def restore_file(ref: str, rel: str) -> None:
    dst = ROOT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    blob = subprocess.check_output(["git", "show", f"{ref}:{rel}"])
    with open(dst, "wb") as fh:
        fh.write(blob)


def main() -> None:
    files = git_ls(SRC_REF)
    copied = 0
    for rel in files:
        if allowed(rel):
            restore_file(SRC_REF, rel)
            copied += 1
    ffmpeg_dir = ROOT / "resources/ffmpeg"
    ffmpeg_dir.mkdir(parents=True, exist_ok=True)
    (ffmpeg_dir / ".gitkeep").write_text("", encoding="utf-8")
    print(f"Copied {copied} allowed files from {SRC_REF}")


if __name__ == "__main__":
    main()
