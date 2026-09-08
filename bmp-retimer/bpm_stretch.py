#!/usr/bin/env python3
"""
bpm_stretch.py — measure a track's BPM and time-stretch it to a target BPM
(pitch stays the same; only tempo changes).

Usage:
    python bpm_stretch.py input.wav output.wav --target-bpm 40
    python bpm_stretch.py input.mp3 output.wav --target-bpm 40 --source-bpm 94

If --source-bpm is omitted, BPM is auto-detected with librosa's beat tracker.
Auto-detection can be wrong on very slow / rubato / drum-less tracks — if the
output feels off, pass --source-bpm manually with the value you already know
(e.g. from your Suno prompt) for a more reliable stretch ratio.

Quality note: this uses librosa's STFT phase-vocoder time-stretch. It's decent
for stretch ratios up to roughly 2x-2.5x. Beyond that (e.g. 94 -> 40 BPM is a
~2.35x stretch) you may start hearing mild "phasiness"/smearing on transients.
For near-transparent quality at large stretch ratios, the rubberband library
sounds notably cleaner but requires the `rubberband` command-line binary
installed on your system. This script auto-uses rubberband if it's available,
and falls back to librosa otherwise.

REQUIREMENT — install rubberband-cli for best quality (small, ~1-3 MB, not
a heavy dependency):
    Linux (Ubuntu/Debian): sudo apt install rubberband-cli
    macOS:                 brew install rubberband
    Windows:                no official installer; use WSL and follow the
                            Linux instructions above, or fall back to the
                            librosa path (works fine, slightly less clean
                            on transients at large stretch ratios).

Without rubberband-cli installed, this script silently falls back to the
librosa phase-vocoder — it will still work, just with the quality caveat
above.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import os

import numpy as np
import librosa
import soundfile as sf


def detect_bpm(y, sr):
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    # librosa can return a 0-d array depending on version
    bpm = float(np.atleast_1d(tempo)[0])
    return bpm


def stretch_with_rubberband(in_path, out_path, ratio):
    """ratio = source_bpm / target_bpm (stretch factor for duration)."""
    # rubberband CLI: --tempo <factor> where factor = new_tempo/old_tempo... but
    # rubberband's --time parameter stretches DURATION by that factor.
    # duration_ratio = source_bpm / target_bpm  (slower target -> longer duration)
    cmd = [
        "rubberband",
        "--time", str(ratio),
        "--pitch-hq",
        in_path,
        out_path,
    ]
    subprocess.run(cmd, check=True)


def stretch_with_librosa(y, sr, duration_ratio):
    # librosa time_stretch rate: >1 speeds up (shorter), <1 slows down (longer)
    # duration_ratio = new_duration / old_duration = source_bpm / target_bpm
    rate = 1.0 / duration_ratio
    y_stretched = librosa.effects.time_stretch(y, rate=rate)
    return y_stretched


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input audio file (wav/mp3/flac/etc.)")
    ap.add_argument("output", help="output wav file")
    ap.add_argument("--target-bpm", type=float, required=True, help="desired BPM")
    ap.add_argument("--source-bpm", type=float, default=None,
                     help="known source BPM (skips auto-detection; recommended for accuracy)")
    ap.add_argument("--sr", type=int, default=None, help="resample rate (default: keep native)")
    args = ap.parse_args()

    print(f"Loading {args.input} ...")
    y, sr = librosa.load(args.input, sr=args.sr, mono=False)
    if y.ndim == 1:
        y_mono_for_detect = y
    else:
        y_mono_for_detect = np.mean(y, axis=0)

    if args.source_bpm is not None:
        source_bpm = args.source_bpm
        print(f"Using provided source BPM: {source_bpm:.2f}")
    else:
        source_bpm = detect_bpm(y_mono_for_detect, sr)
        print(f"Detected BPM: {source_bpm:.2f}  "
              f"(auto-detection can be off by 2x on some tracks — sanity check this)")

    duration_ratio = source_bpm / args.target_bpm
    print(f"Target BPM: {args.target_bpm:.2f}  ->  duration ratio: {duration_ratio:.4f}x "
          f"({'slower/longer' if duration_ratio > 1 else 'faster/shorter'})")

    rubberband_bin = shutil.which("rubberband")

    if rubberband_bin:
        print("rubberband found — using it for higher-quality stretch.")
        with tempfile.TemporaryDirectory() as td:
            tmp_in = os.path.join(td, "in.wav")
            sf.write(tmp_in, y.T if y.ndim > 1 else y, sr)
            stretch_with_rubberband(tmp_in, args.output, duration_ratio)
    else:
        print("rubberband not found on PATH — falling back to librosa phase-vocoder "
              "(fine for modest ratios, may smear a bit on large stretches like this one).")
        if y.ndim > 1:
            # process each channel separately, then stack
            channels = [stretch_with_librosa(ch, sr, duration_ratio) for ch in y]
            min_len = min(len(c) for c in channels)
            y_out = np.stack([c[:min_len] for c in channels], axis=0)
            sf.write(args.output, y_out.T, sr)
        else:
            y_out = stretch_with_librosa(y, sr, duration_ratio)
            sf.write(args.output, y_out, sr)

    print(f"Done. Wrote {args.output}")


if __name__ == "__main__":
    main()
