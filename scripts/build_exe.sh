#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VENV_DIR=${VENV_DIR:-.venv}

if [ -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  # shellcheck disable=SC1090
  source "$PROJECT_ROOT/$VENV_DIR/bin/activate"
fi

SPEC_FILE=${SPEC_FILE:-build/TRANSCRIBATORAUD.spec}
OUTPUT_DIR=${OUTPUT_DIR:-dist}

if [ ! -f "$PROJECT_ROOT/$SPEC_FILE" ]; then
  echo "Spec file $SPEC_FILE not found; skipping PyInstaller build." >&2
  exit 0
fi

pyinstaller --clean "$PROJECT_ROOT/$SPEC_FILE"

mkdir -p "$PROJECT_ROOT/$OUTPUT_DIR"

if git -C "$PROJECT_ROOT" status --short | grep -E '^(\?\?|MM|AM| M).*' >/dev/null 2>&1; then
  echo "Warning: build produced modifications. Ensure build artefacts stay ignored." >&2
fi
