#!/usr/bin/env python3
"""
stem_to_sp1.py
--------------
Takes a stereo WAV (or MP3/FLAC/etc.), splits it into 4 stems via Demucs,
then merges them into a single 8-channel 24-bit 48kHz PCM WAV ready for
the Teenage Engineering SP-1 / Solderless Stemloader.

Usage:
    python stem_to_sp1.py mysong.wav
    python stem_to_sp1.py mysong.wav --output mysong_sp1.wav
    python stem_to_sp1.py mysong.wav --bpm 120
    python stem_to_sp1.py mysong.wav --model htdemucs_ft

Requirements: run setup.sh first, then use run.sh to invoke this script.

Stem order in the output (channels 1-2, 3-4, 5-6, 7-8):
    1-2: drums       → SP-1 stem 1
    3-4: bass        → SP-1 stem 2
    5-6: other       → SP-1 stem 3
    7-8: vocals      → SP-1 stem 4

BPM note:
    BPM controls MIDI clock, gate effect, looping, and other time-based
    effects on SP-1. It's embedded in the output filename as e.g. "120BPM"
    so Stemloader auto-detects it on import (range: 30-300 BPM).
"""

import argparse
import re
import subprocess
import sys
import shutil
import tempfile
from pathlib import Path

TARGET_SR        = 48_000
TARGET_CHANNELS  = 8
TARGET_SUBTYPE   = "PCM_24"
STEM_ORDER       = ["drums", "bass", "other", "vocals"]
BPM_MIN, BPM_MAX = 30, 300


def check_dependencies():
    missing = []
    for pkg in ["demucs", "soundfile", "numpy", "soxr"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"[!] Missing packages: {', '.join(missing)}")
        print(f"    Did you run setup.sh first?")
        sys.exit(1)


def detect_bpm(input_path: Path) -> int:
    """Estimate BPM from an onset envelope using soundfile/numpy only."""
    import numpy as np
    import soundfile as sf

    print(f"[*] Detecting BPM...")

    data, sr = sf.read(str(input_path), dtype="float32", always_2d=True)
    data = data[: sr * 90].mean(axis=1)
    if data.size < sr * 4:
        return 120

    hop = 512
    frame = 2048
    usable = data[: ((len(data) - frame) // hop) * hop + frame]
    frames = np.lib.stride_tricks.sliding_window_view(usable, frame)[::hop]
    window = np.hanning(frame).astype("float32")
    spectrum = np.abs(np.fft.rfft(frames * window, axis=1))
    flux = np.maximum(0, np.diff(spectrum, axis=0)).sum(axis=1)
    flux -= flux.mean()
    if np.max(np.abs(flux)) > 0:
        flux /= np.max(np.abs(flux))

    corr = np.correlate(flux, flux, mode="full")[len(flux) - 1:]
    min_lag = max(1, int((60 / BPM_MAX) * sr / hop))
    max_lag = min(len(corr) - 1, int((60 / BPM_MIN) * sr / hop))
    if max_lag <= min_lag:
        return 120

    lag = min_lag + int(np.argmax(corr[min_lag:max_lag]))
    bpm = 60 * sr / (lag * hop)
    while bpm < 80:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    bpm = int(round(max(BPM_MIN, min(BPM_MAX, bpm))))
    print(f"    Detected BPM: {bpm}")
    return bpm


def extract_bpm_from_filename(path: Path) -> int | None:
    """Parse BPM from filename if present, e.g. 'mysong_120BPM.wav' -> 120."""
    match = re.search(r'(\d+)\s*BPM', path.stem, re.IGNORECASE)
    if match:
        bpm = int(match.group(1))
        if BPM_MIN <= bpm <= BPM_MAX:
            return bpm
    return None


def build_output_path(input_path: Path, bpm: int, user_output: str | None) -> Path:
    """Construct output path with BPM embedded so Stemloader auto-detects it."""
    if user_output:
        p = Path(user_output)
        if not re.search(r'\d+BPM', p.stem, re.IGNORECASE):
            return p.with_name(f"{p.stem}_{bpm}BPM{p.suffix}")
        return p
    return input_path.with_name(f"{input_path.stem}_{bpm}BPM_sp1.wav")


def run_demucs(input_path: Path, out_dir: Path, model: str) -> Path:
    """Run Demucs separation and return the folder containing the 4 stem WAVs."""
    print(f"[*] Running Demucs ({model}) on: {input_path.name}")
    cmd = [
        sys.executable, "-m", "demucs",
        "-n", model,
        "--out", str(out_dir),
        str(input_path),
    ]
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print("[!] Demucs failed.")
        sys.exit(1)

    song_name = input_path.stem
    stem_dir  = out_dir / model / song_name
    if not stem_dir.exists():
        candidates = list(out_dir.rglob(song_name))
        if candidates:
            stem_dir = candidates[0]
        else:
            print(f"[!] Could not find Demucs output at {stem_dir}")
            sys.exit(1)

    print(f"[*] Stems written to: {stem_dir}")
    return stem_dir


def load_and_resample(path: Path, target_sr: int):
    """Load a WAV, ensure stereo, resample to target_sr using soxr. Returns (samples, 2) array."""
    import soundfile as sf
    import numpy as np
    import soxr

    data, sr = sf.read(str(path), dtype="float32")

    # Ensure stereo
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    elif data.shape[1] == 1:
        data = np.concatenate([data, data], axis=1)

    # Resample if needed — soxr is fast and high quality
    if sr != target_sr:
        print(f"    Resampling {path.name}: {sr}Hz -> {target_sr}Hz")
        data = soxr.resample(data, sr, target_sr, quality="HQ")

    return data


def merge_stems(stem_dir: Path, output_path: Path):
    """Load 4 stereo stems, concatenate to 8 channels, write 24-bit/48kHz WAV."""
    import numpy as np
    import soundfile as sf

    stem_arrays = []
    for stem_name in STEM_ORDER:
        stem_path = stem_dir / f"{stem_name}.wav"
        if not stem_path.exists():
            print(f"[!] Missing stem: {stem_path}")
            sys.exit(1)
        print(f"    Loading: {stem_path.name}")
        arr = load_and_resample(stem_path, TARGET_SR)
        stem_arrays.append(arr)

    # Pad all stems to the same length
    max_len = max(a.shape[0] for a in stem_arrays)
    padded  = []
    for arr in stem_arrays:
        if arr.shape[0] < max_len:
            pad = np.zeros((max_len - arr.shape[0], 2), dtype=arr.dtype)
            arr = np.concatenate([arr, pad], axis=0)
        padded.append(arr)

    # Interleave into 8 channels: L_drums, R_drums, L_bass, R_bass, L_other, R_other, L_vox, R_vox
    merged = np.concatenate(padded, axis=1)
    assert merged.shape[1] == TARGET_CHANNELS
    merged = np.clip(merged, -1.0, 1.0)

    duration_s   = merged.shape[0] / TARGET_SR
    transfer_min = duration_s / 60 * 10

    print(f"[*] Writing {TARGET_CHANNELS}-ch {TARGET_SUBTYPE} WAV @ {TARGET_SR}Hz")
    print(f"    Duration: {duration_s:.1f}s ({duration_s / 60:.1f} min)")
    print(f"    Estimated SP-1 transfer time: ~{transfer_min:.0f} min")
    sf.write(str(output_path), merged, TARGET_SR, subtype=TARGET_SUBTYPE)
    print(f"[✓] Output: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert a song to SP-1 8-channel stem WAV.")
    parser.add_argument("input", help="Input audio file (WAV, MP3, FLAC, etc.)")
    parser.add_argument("--output", "-o", help="Output WAV path")
    parser.add_argument("--bpm", "-b", type=int,
                        help="Song BPM (30-300). Overrides auto-detection.")
    parser.add_argument("--model", "-m", default="htdemucs",
                        help="Demucs model (default: htdemucs). Options: htdemucs, htdemucs_ft, mdx_extra")
    parser.add_argument("--keep-stems", action="store_true",
                        help="Save individual stem WAVs alongside the output")
    args = parser.parse_args()

    check_dependencies()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        print(f"[!] Input file not found: {input_path}")
        sys.exit(1)

    # Resolve BPM: CLI flag > filename hint > auto-detect
    if args.bpm:
        if not (BPM_MIN <= args.bpm <= BPM_MAX):
            print(f"[!] BPM must be between {BPM_MIN} and {BPM_MAX}.")
            sys.exit(1)
        bpm = args.bpm
        print(f"[*] Using BPM from flag: {bpm}")
    elif (filename_bpm := extract_bpm_from_filename(input_path)):
        bpm = filename_bpm
        print(f"[*] Using BPM from filename: {bpm}")
    else:
        bpm = detect_bpm(input_path)
        print(f"[!] Auto-detected BPM: {bpm} — verify this looks right!")
        print(f"    Override with: --bpm <value>")

    output_path = build_output_path(input_path, bpm, args.output)

    with tempfile.TemporaryDirectory() as tmp:
        stem_dir = run_demucs(input_path, Path(tmp), args.model)

        if args.keep_stems:
            stems_out = output_path.with_name(output_path.stem + "_stems")
            stems_out.mkdir(exist_ok=True)
            for f in stem_dir.glob("*.wav"):
                shutil.copy(f, stems_out / f.name)
            print(f"[*] Individual stems saved to: {stems_out}")

        merge_stems(stem_dir, output_path)

    print(f"\n[✓] Done. Drag {output_path.name} into Stemloader.")
    print(f"    BPM ({bpm}) is in the filename — Stemloader will detect it automatically.")


if __name__ == "__main__":
    main()
