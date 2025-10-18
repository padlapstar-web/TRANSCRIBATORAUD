#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN=${PYTHON_BIN:-python3.12}
VENV_DIR=${VENV_DIR:-.venv}
PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3.12 interpreter ('$PYTHON_BIN') is required." >&2
  exit 1
fi

if [ ! -d "$PROJECT_ROOT/$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$PROJECT_ROOT/$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$PROJECT_ROOT/$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
  python -m pip install -r "$PROJECT_ROOT/requirements.txt"
fi
python -m pip install --upgrade pyinstaller

python "$PROJECT_ROOT/scripts/fetch_assets.py"

bash "$PROJECT_ROOT/scripts/build_exe.sh"
