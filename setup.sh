#!/bin/bash
# setup.sh — creates a self-contained venv for stem_to_sp1
# Run once: bash setup.sh

set -e

VENV_DIR="$(dirname "$0")/.venv"

echo "[*] Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

echo "[*] Installing dependencies..."
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install -r "$(dirname "$0")/requirements.txt"

echo ""
echo "[✓] Setup complete."
echo "    Run your conversions with:  bash run.sh mysong.wav"
echo "    Or with options:            bash run.sh mysong.wav --bpm 120 --model htdemucs_ft"
