#!/bin/bash
# Convert every audio file in a folder into SP-1-ready WAVs.
# Usage: bash batch_convert.sh input_dir output_dir [extra run.sh args...]

set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "Usage: bash batch_convert.sh input_dir output_dir [extra run.sh args...]"
    echo 'Example: bash batch_convert.sh ./songs ./converted --model htdemucs_ft'
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
INPUT_DIR="$1"
OUTPUT_DIR="$2"
shift 2

if [ ! -d "$INPUT_DIR" ]; then
    echo "[!] Input directory not found: $INPUT_DIR"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

find "$INPUT_DIR" -maxdepth 1 -type f \( \
    -iname '*.wav' -o \
    -iname '*.mp3' -o \
    -iname '*.flac' -o \
    -iname '*.aiff' -o \
    -iname '*.aif' -o \
    -iname '*.m4a' \
\) -print0 |
    sort -z |
    while IFS= read -r -d '' input; do
        name="$(basename "${input%.*}")"
        if find "$OUTPUT_DIR" -maxdepth 1 -type f -name "${name}_sp1_*BPM.wav" | grep -q .; then
            echo "[*] Skipping existing output for: $name"
            continue
        fi
        echo "[*] Converting: $name"
        bash "$SCRIPT_DIR/run.sh" "$input" --output "$OUTPUT_DIR/${name}_sp1.wav" "$@"
    done
