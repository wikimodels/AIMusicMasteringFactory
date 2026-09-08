#!/usr/bin/env python3
"""BPM Retimer engine: scan / BPM detect / time-stretch / format convert.

Reuses the proven single-file routines from bpm_stretch.py
(detect_bpm, stretch_with_librosa, stretch_with_rubberband).

Stretch backends, in order of preference:
  1. native `rubberband` CLI on PATH (best quality),
  2. `rubberband` inside WSL (`wsl rubberband ...`, needs `rubberband-cli`
     installed in the distro — file paths are translated to /mnt/...),
  3. librosa phase-vocoder fallback (no external deps).

Output conversion to MP3/M4A/OGG goes through `ffmpeg` on PATH.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import librosa
import soundfile as sf

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from bpm_stretch import (  # noqa: E402
    build_freq_filter as _build_freq_filter,
    detect_bpm as _detect_bpm,
    stretch_with_librosa as _stretch_librosa,
    stretch_with_rubberband as _stretch_rubberband,
)

AUDIO_EXTS = {
    ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus",
    ".aac", ".wma", ".aiff", ".aif",
}

FFMPEG_FMT = {
    # fmt: (extension, extra ffmpeg args)
    "wav": (".wav", []),
    "mp3": (".mp3", ["-codec:a", "libmp3lame", "-b:a", "192k"]),
    "m4a": (".m4a", ["-codec:a", "aac", "-b:a", "192k"]),
    "ogg": (".ogg", ["-codec:a", "libvorbis", "-q:a", "5"]),
}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def scan_inputs(input_dir: str | Path):
    """Recursively collect supported audio files. Returns sorted list of Paths."""
    root = Path(input_dir)
    if not root.is_dir():
        return []
    files = [
        p for p in sorted(root.rglob("*"))
        if p.is_file() and p.suffix.lower() in AUDIO_EXTS
    ]
    return files


def final_bpm_for_track(target_bpm: float, spread_pct: float) -> float:
    """Variant A (per TZ): target * (1 + U(-N%, +N%)) заново для каждого трека."""
    if spread_pct <= 0:
        return float(target_bpm)
    coef = random.uniform(-spread_pct / 100.0, spread_pct / 100.0)
    return float(target_bpm) * (1.0 + coef)


def win_to_wsl(path: str | Path) -> str:
    """D:\\GitHub\\x.wav -> /mnt/d/GitHub/x.wav (для вызова wsl rubberband)."""
    p = str(Path(path).resolve())
    if len(p) >= 2 and p[1] == ":":
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    return p.replace("\\", "/")


def _wsl_has_rubberband() -> bool:
    wsl = shutil.which("wsl")
    if not wsl:
        return False
    try:
        r = subprocess.run(
            [wsl, "which", "rubberband"],
            capture_output=True, text=True, timeout=60,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def stretch_backend() -> str:
    """'rubberband' | 'rubberband-wsl' | 'librosa'."""
    if shutil.which("rubberband"):
        return "rubberband"
    if _wsl_has_rubberband():
        return "rubberband-wsl"
    return "librosa"


def detect_bpm_file(path: str | Path) -> float:
    """Auto-detect source BPM (beat tracking on mono mixdown)."""
    y, sr = librosa.load(str(path), sr=None, mono=True)
    return _detect_bpm(y, sr)


def _run_rubberband_wsl(in_wav: str, out_wav: str, ratio: float):
    cmd = [
        "wsl", "rubberband",
        "--time", str(ratio),
        "--pitch-hq",
        win_to_wsl(in_wav),
        win_to_wsl(out_wav),
    ]
    subprocess.run(cmd, check=True, timeout=3600)


def stretch_to_wav(in_path: str | Path, out_wav_path: str | Path,
                   source_bpm: float, target_bpm: float,
                   backend: str | None = None) -> dict:
    """Stretch in_path to target_bpm, write WAV. Returns info dict."""
    backend = backend or stretch_backend()
    ratio = float(source_bpm) / float(target_bpm)  # >1 => slower/longer
    y, sr = librosa.load(str(in_path), sr=None, mono=False)

    if backend == "rubberband":
        with tempfile.TemporaryDirectory() as td:
            tmp_in = os.path.join(td, "in.wav")
            sf.write(tmp_in, y.T if y.ndim > 1 else y, sr)
            _stretch_rubberband(tmp_in, str(out_wav_path), ratio)
    elif backend == "rubberband-wsl":
        with tempfile.TemporaryDirectory() as td:
            tmp_in = os.path.join(td, "in.wav")
            sf.write(tmp_in, y.T if y.ndim > 1 else y, sr)
            _run_rubberband_wsl(tmp_in, str(out_wav_path), ratio)
    else:
        if y.ndim > 1:
            channels = [_stretch_librosa(ch, sr, ratio) for ch in y]
            min_len = min(len(c) for c in channels)
            y_out = np.stack([c[:min_len] for c in channels], axis=0)
            sf.write(str(out_wav_path), y_out.T, sr)
        else:
            sf.write(str(out_wav_path), _stretch_librosa(y, sr, ratio), sr)
    return {"backend": backend, "ratio": ratio, "sr": int(sr)}


def apply_freq_trim_wav(wav_path: str | Path, low_cut: float = 0,
                        high_cut: float = 0) -> bool:
    """ffmpeg high-pass/low-pass pass over a WAV file, in place (via temp).

    Same filter code as bpm_stretch.apply_freq_trim. Returns True if filtered,
    False if both cuts are 0 (no-op).
    """
    filt = _build_freq_filter(low_cut, high_cut)
    if not filt:
        return False
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH (needed for frequency trim)")
    tmp = str(wav_path) + ".trimtmp.wav"
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(wav_path), "-af", filt, tmp]
    subprocess.run(cmd, check=True, timeout=3600)
    os.replace(tmp, str(wav_path))
    return True


def convert_wav(in_wav: str | Path, out_path: str | Path, fmt: str):
    """Convert WAV to target format. WAV is written directly, rest via ffmpeg."""
    fmt = fmt.lower()
    if fmt not in FFMPEG_FMT:
        raise ValueError(f"unsupported output format: {fmt!r}")
    ext, extra = FFMPEG_FMT[fmt]
    out_path = Path(out_path)
    if out_path.suffix.lower() != ext:
        out_path = out_path.with_suffix(ext)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "wav":
        data, sr = sf.read(str(in_wav), always_2d=False)
        sf.write(str(out_path), data, sr)
        return out_path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found on PATH (needed for mp3/m4a/ogg)")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(in_wav), *extra, str(out_path)]
    subprocess.run(cmd, check=True, timeout=3600)
    return out_path


def output_name(stem: str, final_bpm: float, fmt: str) -> str:
    """<stem>_<bpm>bpm.<ext> — bpm rounded to int (per TZ example)."""
    ext, _ = FFMPEG_FMT[fmt.lower()]
    return f"{stem}_{int(round(final_bpm))}bpm{ext}"


def output_name_rate(stem: str, rate: float, fmt: str) -> str:
    """<stem>_<rate>x.<ext> — when source BPM is unknown (no analysis)."""
    ext, _ = FFMPEG_FMT[fmt.lower()]
    rs = ("%.2f" % float(rate)).rstrip("0").rstrip(".")
    return f"{stem}_{rs}x{ext}"
