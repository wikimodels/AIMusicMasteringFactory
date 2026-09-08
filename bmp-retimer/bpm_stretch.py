#!/usr/bin/env python3
"""
bpm_stretch.py — measure a track's BPM, time-stretch it to a target BPM
(pitch stays the same; only tempo changes), then optionally trim away
sub-sonic rumble and high-frequency hiss/crackle before saving.

Usage:
    python bpm_stretch.py input.wav output.wav --target-bpm 40
    python bpm_stretch.py input.mp3 output.wav --target-bpm 40 --source-bpm 94

    # with frequency trim (on by default, see --low-cut / --high-cut):
    python bpm_stretch.py input.m4a output.m4a --target-bpm 40 --source-bpm 94 --high-cut 5000

    # disable frequency trim entirely:
    python bpm_stretch.py input.wav output.wav --target-bpm 40 --no-trim

If --source-bpm is omitted, BPM is auto-detected with librosa's beat tracker.
Auto-detection can be wrong on very slow / rubato / drum-less tracks — if the
output feels off, pass --source-bpm manually with the value you already know
(e.g. from your Suno prompt) for a more reliable stretch ratio.

STRETCH QUALITY NOTE: this uses librosa's STFT phase-vocoder time-stretch by
default. It's decent for stretch ratios up to roughly 2x-2.5x. Beyond that
(e.g. 94 -> 40 BPM is a ~2.35x stretch) you may start hearing mild
"phasiness"/smearing on transients. For near-transparent quality at large
stretch ratios, the rubberband library sounds notably cleaner but requires
the `rubberband` command-line binary installed on your system. This script
auto-uses rubberband if it's available, and falls back to librosa otherwise.

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

FREQUENCY TRIM: after stretching, the script (by default) high-pass filters
below 30 Hz (sub-sonic rumble — almost never musically useful) and low-pass
filters above 5000 Hz (aggressive — kills hiss/crackle/noise floor along with
any "air"/sparkle; intended for material fed into Suno as a cover reference,
where fine top-end detail isn't important and a noisy top end can hurt
generation quality). Tune with --low-cut / --high-cut, or disable with
--no-trim. Requires ffmpeg on PATH for this step.
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
    # rubberband CLI: --time <factor> stretches DURATION by that factor.
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


def load_audio_any_format(path, sr=None):
    """librosa/soundfile can't read some containers directly (notably m4a/AAC).
    Pre-convert anything to a temp wav via ffmpeg first, then load that —
    this makes wav/mp3/m4a/flac/etc. all work uniformly."""
    with tempfile.TemporaryDirectory() as td:
        tmp_wav = os.path.join(td, "src.wav")
        cmd = ["ffmpeg", "-y", "-i", path]
        if sr:
            cmd += ["-ar", str(sr)]
        cmd += [tmp_wav]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("ffmpeg failed to decode input file:", file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            sys.exit(1)
        y, loaded_sr = librosa.load(tmp_wav, sr=sr, mono=False)
    return y, loaded_sr


def build_freq_filter(low_cut, high_cut, low_poles=2, high_poles=2):
    parts = []
    if low_cut and low_cut > 0:
        parts.append(f"highpass=f={low_cut}:poles={low_poles}")
    if high_cut and high_cut > 0:
        parts.append(f"lowpass=f={high_cut}:poles={high_poles}")
    return ",".join(parts) if parts else None


def apply_freq_trim(in_path, out_path, low_cut, high_cut, low_poles, high_poles, bitrate="256k"):
    """Runs the ffmpeg high-pass/low-pass trim as a final pass over the
    stretched audio. in_path/out_path can be any ffmpeg-readable/writable
    format; the output container is inferred from out_path's extension."""
    filt = build_freq_filter(low_cut, high_cut, low_poles, high_poles)
    if filt is None:
        # nothing to do — just copy through
        shutil.copyfile(in_path, out_path)
        return

    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-af", filt,
        "-b:a", bitrate,
        out_path,
    ]
    print(f"Frequency trim filter chain: {filt}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("ffmpeg frequency trim failed:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="input audio file (wav/mp3/m4a/flac/etc.)")
    ap.add_argument("output", help="output audio file (format inferred from extension)")
    ap.add_argument("--target-bpm", type=float, required=True, help="desired BPM")
    ap.add_argument("--source-bpm", type=float, default=None,
                     help="known source BPM (skips auto-detection; recommended for accuracy)")
    ap.add_argument("--sr", type=int, default=None, help="resample rate (default: keep native)")

    # frequency trim options
    ap.add_argument("--no-trim", action="store_true",
                     help="skip the frequency trim step entirely (just stretch, no filtering)")
    ap.add_argument("--low-cut", type=float, default=30,
                     help="high-pass cutoff in Hz — removes rumble below this (default: 30, 0 disables)")
    ap.add_argument("--high-cut", type=float, default=5000,
                     help="low-pass cutoff in Hz — removes hiss/crackle above this "
                          "(default: 5000, aggressive; use 0 to disable)")
    ap.add_argument("--low-poles", type=int, default=2, help="high-pass filter steepness (default 2)")
    ap.add_argument("--high-poles", type=int, default=2, help="low-pass filter steepness (default 2)")
    ap.add_argument("--bitrate", default="256k", help="output bitrate for lossy formats (default 256k)")

    args = ap.parse_args()

    print(f"Loading {args.input} ...")
    y, sr = load_audio_any_format(args.input, sr=args.sr)
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

    # Stretch step always writes to a temp wav first — the frequency trim
    # step (ffmpeg) then reads that wav and writes the final --output in
    # whatever format its extension implies. If --no-trim is set, the
    # stretched wav is converted straight to the final output instead.
    with tempfile.TemporaryDirectory() as td:
        stretched_wav = os.path.join(td, "stretched.wav")

        if rubberband_bin:
            print("rubberband found — using it for higher-quality stretch.")
            tmp_in = os.path.join(td, "in.wav")
            sf.write(tmp_in, y.T if y.ndim > 1 else y, sr)
            stretch_with_rubberband(tmp_in, stretched_wav, duration_ratio)
        else:
            print("rubberband not found on PATH — falling back to librosa phase-vocoder "
                  "(fine for modest ratios, may smear a bit on large stretches like this one).")
            if y.ndim > 1:
                channels = [stretch_with_librosa(ch, sr, duration_ratio) for ch in y]
                min_len = min(len(c) for c in channels)
                y_out = np.stack([c[:min_len] for c in channels], axis=0)
                sf.write(stretched_wav, y_out.T, sr)
            else:
                y_out = stretch_with_librosa(y, sr, duration_ratio)
                sf.write(stretched_wav, y_out, sr)

        if args.no_trim:
            print("Frequency trim skipped (--no-trim).")
            # just move/convert the stretched wav to the requested output format
            cmd = ["ffmpeg", "-y", "-i", stretched_wav, "-b:a", args.bitrate, args.output]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("ffmpeg output conversion failed:", file=sys.stderr)
                print(result.stderr, file=sys.stderr)
                sys.exit(1)
        else:
            apply_freq_trim(
                stretched_wav, args.output,
                args.low_cut, args.high_cut,
                args.low_poles, args.high_poles,
                bitrate=args.bitrate,
            )

    print(f"Done. Wrote {args.output}")


if __name__ == "__main__":
    main()