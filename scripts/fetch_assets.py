#!/usr/bin/env python3
"""Download or prepare runtime assets for local development.

This script intentionally avoids committing any binaries. It ensures the
expected directories exist and can be extended with actual downloads when
required. Each download must include an SHA256 checksum verification step.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import urllib.request

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESOURCES_DIR = PROJECT_ROOT / "resources"
FFMPEG_DIR = RESOURCES_DIR / "ffmpeg"
MODELS_DIR = PROJECT_ROOT / "models"
CACHE_DIR = PROJECT_ROOT / "cache"

for directory in (RESOURCES_DIR, FFMPEG_DIR, MODELS_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

ASSETS: list[tuple[str, str, Path]] = []  # (url, sha256, destination)


def download(url: str, sha256: str, destination: Path) -> None:
    if destination.exists():
        if sha256:
            if verify_sha256(destination, sha256):
                print(f"✔ {destination} already present with matching SHA256")
                return
            print(f"Checksum mismatch for {destination}, re-downloading…")
            destination.unlink()
        else:
            print(f"Skipping download for {destination} (exists, no checksum provided)")
            return

    print(f"Downloading {url} → {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, open(destination, "wb") as target:
        target.write(response.read())

    if sha256 and not verify_sha256(destination, sha256):
        destination.unlink(missing_ok=True)
        raise RuntimeError(f"Checksum mismatch for {destination}")


def verify_sha256(path: Path, expected: str) -> bool:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    digest = h.hexdigest()
    return digest.lower() == expected.lower()


def main() -> None:
    if not ASSETS:
        print("No external assets configured. Repository stays binary-free by default.")
        return

    for url, sha256, dest in ASSETS:
        download(url, sha256, dest)


if __name__ == "__main__":
    main()
