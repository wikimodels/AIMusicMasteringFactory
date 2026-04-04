# =============================================================================
# SUNO AI -> PLATINUM MASTERING  (local v2 — Full Chain)
# HPF -> M/S EQ -> Widen -> Multiband Comp -> Saturation -> De-harsh -> Dither
# QA : Loudness / Peak / Dynamics / Phase
# TG : Telegram notifications
# =============================================================================
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import subprocess
import time
from pathlib import Path
import json
import re
import shutil

import numpy as np
import librosa
import soundfile as sf
import pyloudnorm as pyln
import requests
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress,
    SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from scipy.signal import butter, sosfiltfilt
import matplotlib
matplotlib.use("Agg")  # non-interactive backend (no window)
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ─── Init ─────────────────────────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

INPUT_DIR    = Path("sound/wav_input")
OUTPUT_DIR   = Path("sound/wav_output")
ANALYSIS_DIR = Path("analysis")
DROPS_DIR    = Path("sound/mp3_drops_output")
METADATA_FILE = Path("metadata.json")
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
DROPS_DIR.mkdir(parents=True, exist_ok=True)

console = Console(legacy_windows=False)

DSP_STEPS = 4  # HPF, M/S EQ+Widen, Saturation, De-harsh, Save


# ─── Telegram ─────────────────────────────────────────────────────────────────
def tg(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
    except Exception:
        pass


# ─── DSP Helpers ──────────────────────────────────────────────────────────────
def _rms_env(mono: np.ndarray, window: int) -> np.ndarray:
    """Vectorized smoothed RMS envelope."""
    kernel = np.ones(max(window, 1)) / max(window, 1)
    return np.sqrt(np.convolve(mono ** 2, kernel, mode="same") + 1e-12)


def _compress(y: np.ndarray, sr: int, threshold_db: float, ratio: float,
              attack_ms: float = 20.0, makeup_db: float = 0.0) -> np.ndarray:
    """Stereo-linked vectorized RMS feed-forward compressor."""
    thr    = 10 ** (threshold_db / 20)
    makeup = 10 ** (makeup_db    / 20)
    frame  = max(int(sr * attack_ms / 1000), 1)
    level  = np.sqrt((y[0] ** 2 + y[1] ** 2) / 2) if y.ndim > 1 else np.abs(y)
    env    = _rms_env(level, frame)
    gain   = np.where(env > thr, (thr / env) ** (1.0 - 1.0 / ratio), 1.0)
    # 5ms gain smoothing to avoid pumping
    gain   = np.convolve(gain, np.ones(max(int(sr * 0.005), 1)) /
                         max(int(sr * 0.005), 1), mode="same")
    result = np.stack([y[0] * gain, y[1] * gain]) if y.ndim > 1 else y * gain
    return result * makeup


# ─── DSP Modules ──────────────────────────────────────────────────────────────
def apply_hpf(y: np.ndarray, sr: int) -> np.ndarray:
    """Remove DC + infrasound below 30 Hz."""
    sos = butter(4, 30, "hp", fs=sr, output="sos")
    if y.ndim > 1:
        return np.stack([sosfiltfilt(sos, y[0] - np.mean(y[0])),
                         sosfiltfilt(sos, y[1] - np.mean(y[1]))])
    return sosfiltfilt(sos, y - np.mean(y))


def ms_eq_widen(y: np.ndarray, sr: int, width: float = 1.15) -> np.ndarray:
    """M/S decompose -> EQ mid (mud cut) + side (air boost) -> widen -> recompose."""
    if y.ndim < 2:
        return y
    mid  = (y[0] + y[1]) * 0.5
    side = (y[0] - y[1]) * 0.5

    # Mid: gentle 250 Hz high-pass to reduce muddiness (40% wet blend)
    sos_mud = butter(2, 250, "hp", fs=sr, output="sos")
    mid = mid * 0.6 + sosfiltfilt(sos_mud, mid) * 0.4

    # Side: remove sub-bass, add subtle 10kHz air (+12%)
    sos_side_hp = butter(2, 120,   "hp", fs=sr, output="sos")
    sos_air     = butter(1, 10000, "hp", fs=sr, output="sos")
    side = sosfiltfilt(sos_side_hp, side)
    side = side + sosfiltfilt(sos_air, side) * 0.12
    side *= width

    return np.stack([mid + side, mid - side])


def multiband_compress(y: np.ndarray, sr: int) -> np.ndarray:
    """3-band compressor with complementary splitting (lo+mid+hi = original)."""
    if y.ndim < 2:
        y = np.stack([y, y])

    # Complementary split — no phase artifacts
    sos_lo = butter(4, 120,  "lp", fs=sr, output="sos")
    sos_hi = butter(4, 4000, "hp", fs=sr, output="sos")

    lo   = np.stack([sosfiltfilt(sos_lo, y[0]), sosfiltfilt(sos_lo, y[1])])
    rest = y - lo
    hi   = np.stack([sosfiltfilt(sos_hi, rest[0]), sosfiltfilt(sos_hi, rest[1])])
    mid  = rest - hi

    # Each band gets its own compression character
    lo_c  = _compress(lo,  sr, threshold_db=-16, ratio=5.0, attack_ms=30, makeup_db=1.5)
    mid_c = _compress(mid, sr, threshold_db=-18, ratio=3.0, attack_ms=15, makeup_db=1.0)
    hi_c  = _compress(hi,  sr, threshold_db=-22, ratio=2.0, attack_ms=8,  makeup_db=0.5)

    return lo_c + mid_c + hi_c


def saturate(y: np.ndarray, drive: float = 1.8, mix: float = 0.25) -> np.ndarray:
    """Soft-clip tanh saturation for analog warmth. 25% wet."""
    norm = float(np.tanh(drive))
    return (1.0 - mix) * y + mix * (np.tanh(drive * y) / norm)


def de_harsh(y: np.ndarray, sr: int,
             freq_lo: float = 3000, freq_hi: float = 8000,
             threshold_db: float = -22, reduction_db: float = 3.5) -> np.ndarray:
    """Dynamic EQ — cuts 3-8kHz when Suno's harsh artifacts exceed threshold."""
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
    # 10ms smoothing to avoid clicks
    gain = np.convolve(gain, np.ones(max(int(0.01 * sr), 1)) /
                       max(int(0.01 * sr), 1), mode="same")

    return np.stack([y[0] * gain, y[1] * gain]) if y.ndim > 1 else y * gain


def apply_dither(y: np.ndarray, bits: int = 16) -> np.ndarray:
    """TPDF dither — correct noise shaping before 16-bit quantization."""
    scale = 2 ** (bits - 1)
    return y + (np.random.random(y.shape) - np.random.random(y.shape)) / scale


# ─── Full DSP pipeline ────────────────────────────────────────────────────────
def process_dsp(input_path: Path, tmp_wav: Path, progress=None, task=None) -> None:
    def tick(label: str):
        if progress and task is not None:
            progress.advance(task)
            progress.update(task, description=f"[yellow]⚙️  DSP — {label}")

    # 1. Load
    y, sr = librosa.load(str(input_path), sr=44100, mono=False)
    if y.ndim == 1:
        y = np.stack([y, y])
    tick("HPF 30 Hz")

    # 2. HPF
    y = apply_hpf(y, sr)
    tick("M/S EQ + Widen")

    # 3. M/S EQ + Stereo Widen
    y = ms_eq_widen(y, sr)
    tick("Saturation")

    # 4. Harmonic saturation
    y = saturate(y)
    tick("De-harsh 3-8kHz")

    # 5. Dynamic de-harshening
    y = de_harsh(y, sr)
    tick("Saving")

    # Peak normalize + TPDF dither + save
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak * 0.9
    y = apply_dither(y)
    sf.write(str(tmp_wav), y.T, sr)


# ─── Spectrum Analysis ───────────────────────────────────────────────────────
def compare_spectra(original: Path, master: Path, stem: str) -> Path:
    """Generates a 3-panel analysis PNG: Spectrum, RMS Waveform, Spectrogram."""
    orig_data,   sr = sf.read(str(original))
    master_data, _  = sf.read(str(master))

    # Convert to mono for analysis
    orig_mono   = orig_data.mean(axis=1)   if orig_data.ndim   > 1 else orig_data
    master_mono = master_data.mean(axis=1) if master_data.ndim > 1 else master_data

    # Trim to same length
    min_len = min(len(orig_mono), len(master_mono))
    orig_mono, master_mono = orig_mono[:min_len], master_mono[:min_len]

    # ── Frequency spectrum (averaged FFT in dB)
    def fft_db(signal, n=65536):
        win  = np.hanning(min(n, len(signal)))
        sig  = signal[:len(win)] * win
        spec = np.abs(np.fft.rfft(sig, n=n))
        freqs = np.fft.rfftfreq(n, 1 / sr)
        db   = 20 * np.log10(spec + 1e-9)
        # Smooth with a rolling average
        kernel = np.ones(80) / 80
        db_smooth = np.convolve(db, kernel, mode="same")
        return freqs, db_smooth

    # ── RMS waveform (10ms frames)
    def rms_curve(signal, frame_ms=10):
        frame = int(sr * frame_ms / 1000)
        n_frames = len(signal) // frame
        rms = np.array([
            np.sqrt(np.mean(signal[i*frame:(i+1)*frame] ** 2))
            for i in range(n_frames)
        ])
        times = np.arange(n_frames) * frame_ms / 1000
        return times, 20 * np.log10(rms + 1e-9)

    freqs_o, db_o = fft_db(orig_mono)
    freqs_m, db_m = fft_db(master_mono)
    times_o, rms_o = rms_curve(orig_mono)
    times_m, rms_m = rms_curve(master_mono)

    # ── Plot
    fig = plt.figure(figsize=(14, 10), facecolor="#0d0d0d")
    fig.suptitle(f"Mastering Analysis — {stem}",
                 color="#e0e0e0", fontsize=14, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

    ORIG   = "#7ec8e3"   # blue
    MASTER = "#c084fc"   # purple
    BG     = "#1a1a1a"
    GRID   = "#2a2a2a"

    def style_ax(ax, title):
        ax.set_facecolor(BG)
        ax.tick_params(colors="#888")
        ax.set_title(title, color="#ccc", fontsize=10, pad=6)
        ax.spines[:].set_color(GRID)
        ax.grid(True, color=GRID, linewidth=0.5)
        for label in ax.get_xticklabels() + ax.get_yticklabels():
            label.set_color("#888")

    # Panel 1 — Frequency Spectrum
    ax1 = fig.add_subplot(gs[0, :])
    mask = (freqs_o >= 20) & (freqs_o <= 20000)
    ax1.semilogx(freqs_o[mask], db_o[mask], color=ORIG,   lw=1.5, label="Original",  alpha=0.85)
    ax1.semilogx(freqs_m[mask], db_m[mask], color=MASTER, lw=1.5, label="Master",    alpha=0.85)
    ax1.set_xlim(20, 20000)
    ax1.set_ylim(-90, -10)
    ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax1.set_ylabel("Level (dB)",     color="#888", fontsize=9)
    ax1.set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax1.set_xticklabels(["50","100","200","500","1k","2k","5k","10k","20k"])
    ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
    style_ax(ax1, "Frequency Spectrum")

    # Panel 2 — RMS Waveform
    ax2 = fig.add_subplot(gs[1, 0])
    ax2.plot(times_o, rms_o, color=ORIG,   lw=1.0, label="Original", alpha=0.8)
    ax2.plot(times_m, rms_m, color=MASTER, lw=1.0, label="Master",   alpha=0.8)
    ax2.set_xlabel("Time (s)",    color="#888", fontsize=9)
    ax2.set_ylabel("RMS (dB)",    color="#888", fontsize=9)
    ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
    style_ax(ax2, "RMS Loudness Over Time")

    # Panel 3 — Difference Spectrum (master - original)
    ax3 = fig.add_subplot(gs[1, 1])
    diff = db_m[mask] - db_o[mask]
    ax3.semilogx(freqs_o[mask], diff, color="#f9a825", lw=1.5, alpha=0.9)
    ax3.axhline(0, color="#555", lw=0.8, linestyle="--")
    ax3.fill_between(freqs_o[mask], 0, diff,
                     where=diff > 0, color="#c084fc", alpha=0.2)
    ax3.fill_between(freqs_o[mask], 0, diff,
                     where=diff < 0, color="#7ec8e3", alpha=0.2)
    ax3.set_xlim(20, 20000)
    ax3.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax3.set_ylabel("Delta (dB)",     color="#888", fontsize=9)
    ax3.set_xticks([50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000])
    ax3.set_xticklabels(["50","100","200","500","1k","2k","5k","10k","20k"])
    style_ax(ax3, "Spectrum Delta (Master − Original)")

    out_png = ANALYSIS_DIR / f"{stem}_analysis.png"
    plt.savefig(str(out_png), dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_png





# ─── ffmpeg loudnorm ──────────────────────────────────────────────────────────
def loudness_norm(tmp_wav: Path, out_wav: Path, meta: dict) -> bool:
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(tmp_wav),
        "-map_metadata", "-1"
    ]
    if "title" in meta: cmd.extend(["-metadata", f"title={meta['title']}"])
    if "artist" in meta: cmd.extend(["-metadata", f"artist={meta['artist']}"])
    if "album" in meta: cmd.extend(["-metadata", f"album={meta['album']}"])
    if "year" in meta: cmd.extend(["-metadata", f"year={meta['year']}"])
    if "comment" in meta: cmd.extend(["-metadata", f"comment={meta['comment']}"])
    
    cmd.extend([
        "-filter_complex",
        "afade=t=in:ss=0:d=0.01,"
        "afade=t=out:st=300:d=1.0,"
        "loudnorm=I=-14:TP=-1.0:LRA=11:linear=true",
        "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le",
        "-write_id3v2", "1",
        str(out_wav)
    ])
    return subprocess.run(cmd).returncode == 0


# ─── QA Inspector ────────────────────────────────────────────────────────────
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


def tg_report(stem: str, dur: float, metrics: list) -> str:
    """Formats a single track report for Telegram."""
    stats = "\n".join(metrics)
    return f"🎵 <b>{stem}</b>\n{stats}\n⏱ {dur:.1f}s"


def main():
    total_t0 = time.time()
    files = sorted([f for f in INPUT_DIR.glob("*") if f.suffix.lower() in (".wav", ".mp3", ".flac")])
    
    if not files:
        console.print(Panel(f"[red]No audio files found in [bold]{INPUT_DIR}[/bold]", border_style="red"))
        return

    # Load metadata
    seo_metadata = {}
    if METADATA_FILE.exists():
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                raw_meta = json.load(f)
            
            # Поддержка красивого формата массива объектов
            if isinstance(raw_meta, list):
                for item in raw_meta:
                    if "file" in item:
                        seo_metadata[item["file"]] = item
            else:
                seo_metadata = raw_meta
                
            console.print(f"[dim]Loaded SEO metadata for {len(seo_metadata)} tracks from {METADATA_FILE.name}[/dim]")
        except Exception as e:
            console.print(f"[red]❌ Error loading {METADATA_FILE.name}: {e}[/red]")

    # Notify Telegram about start
    tg(f"🎛️ <b>Mastering started</b>\n{len(files)} track(s) in queue\n"
       f"Chain: HPF · M/S EQ · Saturation · De-harsh · Dither")

    results  = []
    tg_lines = []

    console.print()
    console.print(Panel.fit(
        "[bold magenta]🎛️  SUNO PLATINUM MASTERING  v2[/bold magenta]\n"
        "[dim]HPF · M/S EQ · Saturation · De-harsh · Dither · EBU R128[/dim]",
        border_style="magenta", padding=(0, 2),
    ))
    console.print()

    progress = Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=28, style="magenta", complete_style="bright_magenta"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console, transient=False,
    )

    with progress:
        overall = progress.add_task("[cyan]Total", total=len(files))

        for idx, src in enumerate(files, 1):
            stem    = src.stem
            filename = src.name
            
            meta = {"title": stem}
            out_stem = stem
            
            if filename in seo_metadata:
                meta = seo_metadata[filename]
                if "title" in meta:
                    clean_title = re.sub(r'[^a-zA-Z0-9а-яА-ЯёЁ_]', '', meta["title"].replace(' ', '_'))
                    if clean_title:
                        out_stem = clean_title
            
            tmp_wav = OUTPUT_DIR / f"{out_stem}_tmp.wav"
            out_wav = OUTPUT_DIR / f"{out_stem}.wav"
            
            # Проверки на то, что файл уже существует (продолжение работы после остановки)
            if out_wav.exists():
                console.rule(f"[bold magenta][{idx}/{len(files)}] {stem} → {out_stem}[/bold magenta]")
                console.print("  [dim]⏭️ Уже обработан (существует в wav_output). Пропускаю...[/dim]\n")
                results.append(out_wav)
                progress.advance(overall)
                continue

            t0      = time.time()

            console.rule(f"[bold magenta][{idx}/{len(files)}] {stem} → {out_stem}[/bold magenta]")

            # ── Step 1: DSP
            task = progress.add_task(
                "[yellow]⚙️  DSP — Loading", total=DSP_STEPS, completed=0)
            try:
                process_dsp(src, tmp_wav, progress=progress, task=task)
                progress.update(task, description="[green]✅ DSP done", completed=DSP_STEPS)
            except Exception as e:
                progress.update(task, description=f"[red]❌ DSP failed: {e}")
                progress.advance(overall)
                continue

            # ── Step 2: Loudnorm
            task2 = progress.add_task("[yellow]🔊 Loudnorm  EBU R128 -14 LUFS", total=None)
            ok = loudness_norm(tmp_wav, out_wav, meta)
            if tmp_wav.exists():
                tmp_wav.unlink()
            if not ok:
                progress.update(task2, description="[red]❌ ffmpeg failed")
                progress.advance(overall)
                continue
            progress.update(task2, description="[green]✅ Loudnorm done", completed=1, total=1)

            # ── Step 3: QA
            task3 = progress.add_task("[yellow]🕵️  QA Inspector", total=None)
            report_lines = []
            metrics = {}
            try:
                metrics = inspect(out_wav)
                tbl, report_lines = render_report(out_stem, metrics)
                progress.update(task3, description="[green]✅ QA done", completed=1, total=1)
                console.print()
                console.print(tbl)
            except Exception as e:
                progress.update(task3, description=f"[red]❌ QA error: {e}")
                progress.advance(overall)
                continue

            duration = time.time() - t0
            console.print(f"  [dim]⏱  {duration:.1f}s   →   [bold]{out_wav}[/bold][/dim]\n")

            # ── Step 4: Spectrum Analysis
            task4 = progress.add_task("[yellow]📊 Spectrum Analysis", total=None)
            try:
                png = compare_spectra(src, out_wav, out_stem)
                progress.update(task4, description="[green]✅ Analysis saved", completed=1, total=1)
                console.print(f"  [dim]📊  →  [bold]{png}[/bold][/dim]\n")
            except Exception as e:
                progress.update(task4, description=f"[yellow]⚠️  Analysis skipped: {e}")

            tg_lines.append(tg_report(out_stem, duration, report_lines))
            results.append(out_wav)
            progress.advance(overall)

    total_dur = time.time() - total_t0
    console.print()
    console.print(Panel(
        f"[bold green]✅  Done![/bold green]  "
        f"[white]{len(results)}/{len(files)}[/white] tracks mastered  "
        f"[dim]in {total_dur:.0f}s[/dim]\n\n"
        + "\n".join(f"  [bright_magenta]•[/bright_magenta] [white]{p.name}[/white]"
                    for p in results),
        title="[bold magenta]📦 OUTPUT", border_style="green", padding=(0, 2),
    ))
    console.print()

    tg(
        f"✅ <b>Mastering complete</b>  —  {len(results)}/{len(files)} tracks\n"
        f"⏱ Total: {total_dur:.0f}s\n\n"
        + "\n\n".join(tg_lines)
    )


if __name__ == "__main__":
    main()