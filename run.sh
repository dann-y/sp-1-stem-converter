#!/bin/bash
# run.sh — runs stem_to_sp1.py inside the local venv
# Usage: bash run.sh mysong.wav [options]

set -e

SCRIPT_DIR="$(dirname "$0")"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "[!] Virtual environment not found. Run setup.sh first:"
    echo "    bash setup.sh"
    exit 1
fi

"$VENV_PYTHON" "$SCRIPT_DIR/stem_to_sp1.py" "$@"
