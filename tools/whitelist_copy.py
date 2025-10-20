#!/usr/bin/env python3
from pathlib import Path
import shutil
import os
import sys

ALLOW = [
  # код
  "app/**/*.py", "app/*.py",
  "tests/**/*.py", "tests/*.py",
  # сборка и конфиги
  "build/**/*.ps1","build/**/*.bat","build/**/*.sh","build/*.ps1","build/*.bat","build/*.sh","build/**/*.spec","build/*.spec",
  "*.spec","pyproject.toml","setup.cfg","requirements*.txt",
  ".editorconfig",".gitattributes",".pre-commit-config.yaml",
  # CI/доки
  ".github/**/*.yml",".github/**/*.yaml","docs/**/*.md","README.md","LICENSE",
  # корневые модули
  "*.md","*.toml","*.ini","*.cfg","*.yml","*.yaml"
]
DENY_DIRS = {"dist","build/pyinstaller","resources/ffmpeg","models",".venv",".git", ".github/workflows/cache"}

def match(glob: str, base: Path):
    return [p for p in base.glob(glob) if p.is_file()]

def copy_from(src_root: Path, dst_root: Path):
    seen = set()
    for pat in ALLOW:
        for p in match(pat, src_root):
            if any(d in p.parts for d in DENY_DIRS) and p.name != '.gitkeep':
                continue
            rel = p.relative_to(src_root)
            if rel in seen:
                continue
            dst = dst_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst)
            seen.add(rel)
    return seen

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: whitelist_copy.py <src_branch_checkout> <dst_checkout>")
        sys.exit(2)
    copied = copy_from(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"Copied {len(copied)} files.")
