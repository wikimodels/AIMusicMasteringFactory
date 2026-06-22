
# =============================================================================
# CLASSICAL / JAZZ / ORCHESTRAL MASTERING  (AIMusicMasteringFactory)
# Pipeline: HPF → Dynamic De-harsh → High-Shelf trim → Dither → EBU R128
#
# ❌ No saturation   — already warm, saturation compounds buzz artifacts
# ❌ No M/S widen    — natural stereo, widening destroys orchestral image
# ❌ No air boost    — highs already excessive in AI-generated orchestral
# ✅ Surgical dynamic de-harsh 3-5 kHz  — kills xylophone/string AI buzz
# ✅ Gentle high-shelf -2 dB @ 9 kHz   — tames AI sparkle, stays natural
# ✅ EBU R128 -14 LUFS                 — Spotify / Apple Music standard
# =============================================================================
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os, subprocess, time
from pathlib import Path

import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy.signal import butter, sosfiltfilt
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress,
    SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT         = Path(__file__).parent.parent
INPUT_DIR    = ROOT / "sound" / "wav_input"
OUTPUT_DIR   = ROOT / "sound" / "wav_output"
ANALYSIS_DIR = ROOT / "analysis"
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

console = Console(legacy_windows=False)

# ─── DSP helpers ──────────────────────────────────────────────────────────────
def _rms_env(mono: np.ndarray, window: int) -> np.ndarray:
    kernel = np.ones(max(window, 1)) / max(window, 1)
    return np.sqrt(np.convolve(mono ** 2, kernel, mode="same") + 1e-12)


# ─── DSP modules ──────────────────────────────────────────────────────────────
def apply_hpf(y: np.ndarray, sr: int) -> np.ndarray:
    """Remove DC + infrasound below 30 Hz."""
    sos = butter(4, 30, "hp", fs=sr, output="sos")
    if y.ndim > 1:
        return np.stack([sosfiltfilt(sos, y[0] - np.mean(y[0])),
                         sosfiltfilt(sos, y[1] - np.mean(y[1]))])
    return sosfiltfilt(sos, y - np.mean(y))


def de_harsh_orchestral(y: np.ndarray, sr: int,
                         freq_lo: float = 3000, freq_hi: float = 5000,
                         threshold_db: float = -28,
                         reduction_db: float = 5.0) -> np.ndarray:
    """
    Dynamic EQ targeting 3-5 kHz — the AI buzz zone for xylophone / strings.
    Lower threshold (-28 dB vs -22 dB in phonk version) = more sensitive.
    Narrower band (3-5 kHz) = more surgical, doesn't touch guitar presence.
    """
    sos_bp = butter(4, [freq_lo, freq_hi], "bp", fs=sr, output="sos")
    if y.ndim > 1:
        harsh = np.sqrt((sosfiltfilt(sos_bp, y[0]) ** 2 +
                         sosfiltfilt(sos_bp, y[1]) ** 2) / 2)
    else:
        harsh = np.abs(sosfiltfilt(sos_bp, y))

    thr  = 10 ** (threshold_db  / 20)
    redu = 10 ** (-reduction_db / 20)
    env  = _rms_env(harsh, int(0.05 * sr))   # 50ms window
    gain = np.where(env > thr, redu, 1.0)
    # 10ms smoothing — no clicks
    gain = np.convolve(gain, np.ones(max(int(0.01 * sr), 1)) /
                       max(int(0.01 * sr), 1), mode="same")

    return np.stack([y[0] * gain, y[1] * gain]) if y.ndim > 1 else y * gain


def high_shelf_trim(y: np.ndarray, sr: int,
                    freq: float = 9000, gain_db: float = -2.0) -> np.ndarray:
    """
    Gentle high-shelf cut (-2 dB above 9 kHz).
    Tames AI 'sparkle/shimmer' without touching presence (1-5 kHz).
    """
    A = 10 ** (gain_db / 40)
    omega = 2 * np.pi * freq / sr
    sn, cs = np.sin(omega), np.cos(omega)
    beta = np.sqrt(A)

    b = np.array([
        A * ((A + 1) + (A - 1) * cs + 2 * np.sqrt(A) * sn),
        -2 * A * ((A - 1) + (A + 1) * cs),
        A * ((A + 1) + (A - 1) * cs - 2 * np.sqrt(A) * sn)
    ])
    a = np.array([
        (A + 1) - (A - 1) * cs + 2 * np.sqrt(A) * sn,
        2 * ((A - 1) - (A + 1) * cs),
        (A + 1) - (A - 1) * cs - 2 * np.sqrt(A) * sn
    ])

    from scipy.signal import lfilter
    if y.ndim > 1:
        return np.stack([lfilter(b, a, y[0]), lfilter(b, a, y[1])])
    return lfilter(b, a, y)


def apply_dither(y: np.ndarray, bits: int = 16) -> np.ndarray:
    scale = 2 ** (bits - 1)
    return y + (np.random.random(y.shape) - np.random.random(y.shape)) / scale


# ─── Full DSP pipeline ────────────────────────────────────────────────────────
def process_dsp(input_path: Path, tmp_wav: Path, progress=None, task=None) -> None:
    def tick(label: str):
        if progress and task is not None:
            progress.advance(task)
            progress.update(task, description=f"[yellow]⚙️  DSP — {label}")

    import librosa
    y, sr = librosa.load(str(input_path), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    tick("HPF 30 Hz")

    # 1. HPF
    y = apply_hpf(y, sr)
    tick("De-harsh 3-5 kHz")

    # 2. Dynamic de-harsh (orchestral tuning)
    y = de_harsh_orchestral(y, sr)
    tick("High-Shelf -2 dB @ 9kHz")

    # 3. Gentle high-shelf trim
    y = high_shelf_trim(y, sr)
    tick("Saving")

    # Peak normalize + dither
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak * 0.9
    y = apply_dither(y)
    sf.write(str(tmp_wav), y.T, sr)


# ─── Spectrum analysis ────────────────────────────────────────────────────────
def compare_spectra(original: Path, master: Path, stem: str) -> Path:
    import soundfile as sf
    orig_data,   sr = sf.read(str(original))
    master_data, _  = sf.read(str(master))
    om = orig_data.mean(axis=1)   if orig_data.ndim   > 1 else orig_data
    mm = master_data.mean(axis=1) if master_data.ndim > 1 else master_data
    n  = min(len(om), len(mm)); om, mm = om[:n], mm[:n]

    def fft_db(s, n=65536):
        w   = np.hanning(min(n, len(s)))
        sig = s[:len(w)] * w
        sp  = np.abs(np.fft.rfft(sig, n=n))
        f   = np.fft.rfftfreq(n, 1 / sr)
        db  = 20 * np.log10(sp + 1e-9)
        return f, np.convolve(db, np.ones(80) / 80, mode="same")

    def rms_curve(s, ms=10):
        fr = int(sr * ms / 1000); nf = len(s) // fr
        r  = np.array([np.sqrt(np.mean(s[i*fr:(i+1)*fr]**2)) for i in range(nf)])
        return np.arange(nf) * ms / 1000, 20 * np.log10(r + 1e-9)

    fo, do = fft_db(om);  fm, dm = fft_db(mm)
    to, ro = rms_curve(om); tm, rm = rms_curve(mm)

    ORIG, MASTER_C, BG, GR = "#7ec8e3", "#c084fc", "#1a1a1a", "#2a2a2a"
    TICKS   = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    TLABELS = ["50","100","200","500","1k","2k","5k","10k","20k"]

    fig = plt.figure(figsize=(14, 10), facecolor="#0d0d0d")
    fig.suptitle(f"Classical Mastering Analysis — {stem}",
                 color="#e0e0e0", fontsize=13, fontweight="bold", y=0.98)
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

    def sa(ax, t):
        ax.set_facecolor(BG); ax.tick_params(colors="#888")
        ax.set_title(t, color="#ccc", fontsize=10, pad=6)
        ax.spines[:].set_color(GR); ax.grid(True, color=GR, linewidth=0.5)
        [l.set_color("#888") for l in ax.get_xticklabels() + ax.get_yticklabels()]

    mask = (fo >= 20) & (fo <= 20000)

    ax1 = fig.add_subplot(gs[0, :])
    ax1.semilogx(fo[mask], do[mask], color=ORIG,     lw=1.5, label="Original", alpha=0.85)
    ax1.semilogx(fm[mask], dm[mask], color=MASTER_C, lw=1.5, label="Master",   alpha=0.85)
    ax1.set_xlim(20, 20000); ax1.set_ylim(-90, -10)
    ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABELS)
    ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
    ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
    sa(ax1, "Frequency Spectrum")

    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(to, ro, color=ORIG,     lw=1.0, label="Original", alpha=0.8)
    ax2.plot(tm, rm, color=MASTER_C, lw=1.0, label="Master",   alpha=0.8)
    ax2.set_xlabel("Time (s)", color="#888", fontsize=9)
    ax2.set_ylabel("RMS (dB)", color="#888", fontsize=9)
    ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
    sa(ax2, "RMS Loudness Over Time")

    ax3 = fig.add_subplot(gs[1, 1])
    diff = dm[mask] - do[mask]
    ax3.semilogx(fo[mask], diff, color="#f9a825", lw=1.5, alpha=0.9)
    ax3.axhline(0, color="#555", lw=0.8, linestyle="--")
    ax3.fill_between(fo[mask], 0, diff, where=diff > 0, color=MASTER_C, alpha=0.2)
    ax3.fill_between(fo[mask], 0, diff, where=diff < 0, color=ORIG,     alpha=0.2)
    ax3.set_xlim(20, 20000); ax3.set_xticks(TICKS); ax3.set_xticklabels(TLABELS)
    ax3.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax3.set_ylabel("Delta (dB)", color="#888", fontsize=9)
    sa(ax3, "Spectrum Delta (Master − Original)")

    out_png = ANALYSIS_DIR / f"{stem}_classical_analysis.png"
    plt.savefig(str(out_png), dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_png


# ─── Loudnorm via ffmpeg ──────────────────────────────────────────────────────
def loudness_norm(tmp_wav: Path, out_wav: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(tmp_wav),
        "-map_metadata", "-1",
        "-filter_complex",
        "loudnorm=I=-14:TP=-1.0:LRA=11:linear=true",
        "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le",
        str(out_wav)
    ]
    return subprocess.run(cmd).returncode == 0


# ─── QA ──────────────────────────────────────────────────────────────────────
def inspect(file_path: Path) -> dict:
    data, rate = sf.read(str(file_path))
    meter    = pyln.Meter(rate)
    loudness = meter.integrated_loudness(data)
    peak     = np.max(np.abs(data))
    peak_db  = 20 * np.log10(peak + 1e-9)
    rms      = np.sqrt(np.mean(data ** 2))
    crest    = 20 * np.log10(peak / (rms + 1e-9))
    corr     = float(np.corrcoef(data[:, 0], data[:, 1])[0, 1]) if data.ndim > 1 else 1.0
    return dict(loudness=loudness, peak_db=peak_db, crest=crest, corr=corr)


def render_report(stem: str, m: dict):
    tbl = Table(
        title=f"📊  {stem}", box=box.ROUNDED, border_style="bright_black",
        show_header=True, header_style="bold cyan", min_width=54,
    )
    tbl.add_column("Metric",  style="bold white", width=24)
    tbl.add_column("Value",   justify="right",    width=14)
    tbl.add_column("Target",  justify="center",   width=16)

    def row(label, val, ok, note, warn=""):
        color = "green" if ok else ("red" if warn else "yellow")
        tbl.add_row(label, Text(val, style=color), Text(note, style="bright_black"))
        return f"{'✅' if ok else '⚠️'}  {label}: {val}"

    lines = []
    lines.append(row("Loudness",     f"{m['loudness']:.2f} LUFS",
                     -15.0 <= m['loudness'] <= -13.0, "-14 LUFS"))
    clip = m['peak_db'] > -0.9
    lines.append(row("True Peak",    f"{m['peak_db']:.2f} dBFS",
                     not clip and m['peak_db'] >= -2.0, "-1.0 dBTP",
                     "CLIPPING" if clip else ""))
    lines.append(row("Dynamics",     f"{m['crest']:.1f} dB",
                     m['crest'] > 6, "> 6 dB crest",
                     "FLAT" if m['crest'] <= 6 else ""))
    lines.append(row("Stereo Phase", f"{m['corr']:.2f}",
                     m['corr'] > 0, "> 0.0",
                     "PHASE !" if m['corr'] <= 0 else ""))
    return tbl, lines


# ─── Main ─────────────────────────────────────────────────────────────────────
DSP_STEPS = 3  # HPF, De-harsh, High-Shelf

def main():
    total_t0 = time.time()
    files = sorted([f for f in INPUT_DIR.glob("*")
                    if f.suffix.lower() in (".wav", ".mp3", ".flac")])

    if not files:
        console.print(Panel(f"[red]No audio files found in [bold]{INPUT_DIR}[/bold]",
                            border_style="red"))
        return

    results = []

    console.print()
    console.print(Panel.fit(
        "[bold cyan]🎻  CLASSICAL / JAZZ MASTERING[/bold cyan]\n"
        "[dim]HPF · Dynamic De-harsh 3-5kHz · High-Shelf -2dB · EBU R128[/dim]\n"
        "[dim]No saturation · No widening · Transparent & natural[/dim]",
        border_style="cyan", padding=(0, 2),
    ))
    console.print()

    progress = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=28, style="cyan", complete_style="bright_cyan"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console, transient=False,
    )

    with progress:
        overall = progress.add_task("[cyan]Total", total=len(files))

        for idx, src in enumerate(files, 1):
            stem     = src.stem
            tmp_wav  = OUTPUT_DIR / f"{stem}_tmp.wav"
            out_wav  = OUTPUT_DIR / f"{stem}.wav"

            if out_wav.exists():
                console.rule(f"[bold cyan][{idx}/{len(files)}] {stem}[/bold cyan]")
                console.print("  [dim]⏭️  Already mastered. Skipping...[/dim]\n")
                results.append(out_wav)
                progress.advance(overall)
                continue

            t0 = time.time()
            console.rule(f"[bold cyan][{idx}/{len(files)}] {stem}[/bold cyan]")

            # Step 1: DSP
            task = progress.add_task("[yellow]⚙️  DSP — Loading",
                                     total=DSP_STEPS, completed=0)
            try:
                process_dsp(src, tmp_wav, progress=progress, task=task)
                progress.update(task, description="[green]✅ DSP done",
                                completed=DSP_STEPS)
            except Exception as e:
                progress.update(task, description=f"[red]❌ DSP failed: {e}")
                progress.advance(overall)
                continue

            # Step 2: Loudnorm
            task2 = progress.add_task("[yellow]🔊 Loudnorm EBU R128 -14 LUFS",
                                      total=None)
            ok = loudness_norm(tmp_wav, out_wav)
            if tmp_wav.exists():
                tmp_wav.unlink()
            if not ok:
                progress.update(task2, description="[red]❌ ffmpeg failed")
                progress.advance(overall)
                continue
            progress.update(task2, description="[green]✅ Loudnorm done",
                            completed=1, total=1)

            # Step 3: QA
            task3 = progress.add_task("[yellow]🕵️  QA Inspector", total=None)
            try:
                metrics = inspect(out_wav)
                tbl, _ = render_report(stem, metrics)
                progress.update(task3, description="[green]✅ QA done",
                                completed=1, total=1)
                console.print()
                console.print(tbl)
            except Exception as e:
                progress.update(task3, description=f"[red]❌ QA error: {e}")
                progress.advance(overall)
                continue

            duration = time.time() - t0
            console.print(f"  [dim]⏱  {duration:.1f}s → [bold]{out_wav}[/bold][/dim]\n")

            # Step 4: Analysis
            task4 = progress.add_task("[yellow]📊 Spectrum Analysis", total=None)
            try:
                png = compare_spectra(src, out_wav, stem)
                progress.update(task4, description="[green]✅ Analysis saved",
                                completed=1, total=1)
                console.print(f"  [dim]📊 → [bold]{png}[/bold][/dim]\n")
            except Exception as e:
                progress.update(task4,
                                description=f"[yellow]⚠️  Analysis skipped: {e}")

            results.append(out_wav)
            progress.advance(overall)

    total_dur = time.time() - total_t0
    console.print()
    console.print(Panel(
        f"[bold green]✅  Done![/bold green]  "
        f"[white]{len(results)}/{len(files)}[/white] tracks mastered  "
        f"[dim]in {total_dur:.0f}s[/dim]\n\n"
        + "\n".join(f"  [bright_cyan]•[/bright_cyan] [white]{p.name}[/white]"
                    for p in results),
        title="[bold cyan]📦 OUTPUT", border_style="green", padding=(0, 2),
    ))
    console.print()


if __name__ == "__main__":
    main()
