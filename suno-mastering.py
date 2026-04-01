# =============================================================================
# SUNO AI -> PLATINUM MASTERING  (local version)
# DSP: 30Hz HPF + Stereo Widen + EBU R128 loudnorm
# QA : Integrated Loudness, Phase & Peak Analysis
# TG : Telegram notifications on completion
# =============================================================================
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import shutil
import subprocess
import time
from pathlib import Path

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
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from rich.text import Text
from scipy.signal import butter, sosfiltfilt

# ─── Init ─────────────────────────────────────────────────────────────────────
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

INPUT_DIR  = Path("input_wav")
OUTPUT_DIR = Path("output_wav")

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

console = Console(legacy_windows=False)


# ─── Telegram ─────────────────────────────────────────────────────────────────
def tg(text: str) -> None:
    """Отправляет сообщение в Telegram. Молча падает если нет токена."""
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


# ─── DSP ──────────────────────────────────────────────────────────────────────
def enhance_stereo_image(y: np.ndarray, sr: int, width: float = 1.15) -> np.ndarray:
    """Mid/Side stereo widening с моно-басом ниже 120 Hz."""
    if y.ndim < 2:
        return y
    mid  = (y[0] + y[1]) * 0.5
    side = (y[0] - y[1]) * 0.5
    sos_side   = butter(4, 120, "hp", fs=sr, output="sos")
    side       = sosfiltfilt(sos_side, side)
    side      *= width
    return np.stack([mid + side, mid - side])


DSP_STEPS = 4  # Load, HPF, Widen/Mono, Save


def process_dsp(input_path: Path, tmp_wav: Path, progress=None, task=None) -> None:
    """HPF 30 Hz → Stereo Widen → Peak normalize → сохраняем temp WAV.
    Тикает progress[task] после каждого из DSP_STEPS шагов."""

    def tick(label: str):
        if progress and task is not None:
            progress.advance(task)
            progress.update(task, description=f"[yellow]⚙️  DSP — {label}")

    # 1. Load
    y, sr = librosa.load(str(input_path), sr=44100, mono=False)
    tick("HPF 30 Hz")

    # 2. HPF
    sos = butter(4, 30, "hp", fs=sr, output="sos")
    if y.ndim > 1:
        y[0] = sosfiltfilt(sos, y[0] - np.mean(y[0]))
        y[1] = sosfiltfilt(sos, y[1] - np.mean(y[1]))
        tick("Stereo Widen")
        # 3. Widen
        y = enhance_stereo_image(y, sr)
    else:
        y = sosfiltfilt(sos, y - np.mean(y))
        tick("Mono normalize")

    # 4. Peak normalize & save
    tick("Saving")
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y / peak * 0.9
    sf.write(str(tmp_wav), y.T, sr)


def loudness_norm(tmp_wav: Path, out_wav: Path) -> bool:
    """ffmpeg EBU R128  −14 LUFS / TP −1.0 dBTP."""
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(tmp_wav),
        "-filter_complex",
        "afade=t=in:ss=0:d=0.01,"
        "afade=t=out:st=300:d=1.0,"
        "loudnorm=I=-14:TP=-1.0:LRA=11:linear=true",
        "-ar", "44100", "-ac", "2", "-acodec", "pcm_s16le",
        str(out_wav),
    ]
    return subprocess.run(cmd).returncode == 0


# ─── QA ───────────────────────────────────────────────────────────────────────
def inspect(file_path: Path) -> dict:
    """Анализирует готовый мастер. Возвращает словарь с метриками."""
    data, rate = sf.read(str(file_path))
    meter    = pyln.Meter(rate)
    loudness = meter.integrated_loudness(data)
    peak     = np.max(np.abs(data))
    peak_db  = 20 * np.log10(peak + 1e-9)
    rms      = np.sqrt(np.mean(data ** 2))
    crest    = 20 * np.log10(peak / (rms + 1e-9))
    corr     = float(np.corrcoef(data[:, 0], data[:, 1])[0, 1]) if data.ndim > 1 else 1.0
    return dict(loudness=loudness, peak_db=peak_db, crest=crest, corr=corr)


def render_report(stem: str, m: dict) -> Table:
    """Рисует таблицу Report Card через Rich."""
    tbl = Table(
        title=f"📊  {stem}",
        box=box.ROUNDED,
        border_style="bright_black",
        show_header=True,
        header_style="bold cyan",
        min_width=54,
    )
    tbl.add_column("Метрика", style="bold white", width=24)
    tbl.add_column("Значение", justify="right", width=14)
    tbl.add_column("Цель", justify="center", width=16)

    def row(label, value_str, ok: bool, note: str, warn_msg: str = ""):
        icon   = "✅" if ok else ("❌ " + warn_msg if warn_msg else "⚠️")
        color  = "green" if ok else ("red" if warn_msg else "yellow")
        tbl.add_row(
            label,
            Text(value_str, style=color),
            Text(note, style="bright_black"),
        )
        return f"{'✅' if ok else '⚠️'}  {label}: {value_str}"

    lines = []
    lines.append(row("Loudness",    f"{m['loudness']:.2f} LUFS",  -15.0 <= m['loudness'] <= -13.0, "−14 LUFS"))
    clip = m['peak_db'] > -0.9
    lines.append(row("True Peak",  f"{m['peak_db']:.2f} dBFS",  not clip and m['peak_db'] >= -2.0, "−1.0 dBTP", "CLIPPING" if clip else ""))
    lines.append(row("Dynamics",   f"{m['crest']:.1f} dB",      m['crest'] > 6,  "> 6 dB crest", "FLAT" if m['crest'] <= 6 else ""))
    lines.append(row("Stereo Phase", f"{m['corr']:.2f}",        m['corr'] > 0,   "> 0.0", "PHASE !" if m['corr'] <= 0 else ""))
    return tbl, lines


def tg_report(stem: str, duration: float, lines: list[str]) -> str:
    return (
        f"💿 <b>{stem}</b>  —  мастер готов за {duration:.1f}s\n\n"
        + "\n".join(lines)
    )


# ─── Main pipeline ─────────────────────────────────────────────────────────────
def main():
    console.print()
    console.print(Panel.fit(
        "[bold magenta]🎛️  SUNO PLATINUM MASTERING[/bold magenta]\n"
        "[dim]HPF 30Hz · M/S Widen · EBU R128 · QA Inspector[/dim]",
        border_style="magenta",
        padding=(0, 4),
    ))
    console.print()

    files = sorted(INPUT_DIR.glob("*.wav")) + sorted(INPUT_DIR.glob("*.mp3"))

    if not files:
        console.print(f"[red]❌  Нет аудиофайлов в [bold]{INPUT_DIR}/[/bold][/red]")
        console.print(f"[dim]Положи WAV/MP3 в папку [bold]{INPUT_DIR}/[/bold] и запусти снова.[/dim]\n")
        return

    console.print(f"[bold cyan]📂  Очередь:[/bold cyan] [white]{len(files)} трек(а/ов)[/white]  →  [dim]{OUTPUT_DIR}/[/dim]\n")
    tg(f"🎛️ <b>Mastering started</b>\n{len(files)} track(s) in queue")

    results   = []
    tg_lines  = []
    total_t0  = time.time()

    progress = Progress(
        SpinnerColumn(spinner_name="dots", style="magenta"),
        TextColumn("[bold white]{task.description}"),
        BarColumn(bar_width=30, style="magenta", complete_style="bright_magenta"),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    )

    with progress:
        overall = progress.add_task("[cyan]Всего", total=len(files))

        for idx, src in enumerate(files, 1):
            stem    = src.stem
            tmp_wav = OUTPUT_DIR / f"{stem}_tmp.wav"
            out_wav = OUTPUT_DIR / f"{stem}_MASTER.wav"
            t0      = time.time()

            console.rule(f"[bold magenta][{idx}/{len(files)}] {stem}[/bold magenta]")

            # ── Step 1: DSP  (4 sub-steps with real progress)
            task = progress.add_task(
                "[yellow]⚙️  DSP — Loading",
                total=DSP_STEPS,
                completed=0,
            )
            try:
                process_dsp(src, tmp_wav, progress=progress, task=task)
                progress.update(task, description="[green]✅ DSP done", completed=DSP_STEPS)
            except Exception as e:
                progress.update(task, description=f"[red]❌ DSP failed: {e}")
                progress.advance(overall)
                continue

            # ── Step 2: Loudnorm (ffmpeg — показываем спиннер, длина неизвестна)
            task2 = progress.add_task("[yellow]🔊 Loudnorm  (EBU R128 −14 LUFS)", total=None)
            ok = loudness_norm(tmp_wav, out_wav)
            if tmp_wav.exists():
                tmp_wav.unlink()
            if not ok:
                progress.update(task2, description="[red]❌ ffmpeg failed")
                progress.advance(overall)
                continue
            progress.update(task2, description="[green]✅ Loudnorm done", completed=1, total=1)

            # ── Step 3: QA
            task3 = progress.add_task("[yellow]🕵️  QA Inspector", total=None)
            try:
                metrics = inspect(out_wav)
                progress.update(task3, description="[green]✅ QA done", completed=1, total=1)
            except Exception as e:
                progress.update(task3, description=f"[red]❌ QA error: {e}")
                progress.advance(overall)
                continue

            duration = time.time() - t0
            tbl, report_lines = render_report(stem, metrics)
            console.print()
            console.print(tbl)
            console.print(f"  [dim]⏱  {duration:.1f}s   →   [bold]{out_wav}[/bold][/dim]\n")

            tg_lines.append(tg_report(stem, duration, report_lines))
            results.append(out_wav)
            progress.advance(overall)

    # ── Final summary
    total_dur = time.time() - total_t0
    console.print()
    console.print(Panel(
        f"[bold green]✅  Готово![/bold green]  "
        f"[white]{len(results)}/{len(files)}[/white] треков смастеровано  "
        f"[dim]за {total_dur:.0f}s[/dim]\n\n"
        + "\n".join(f"  [bright_magenta]•[/bright_magenta] [white]{p.name}[/white]" for p in results),
        title="[bold magenta]📦 OUTPUT",
        border_style="green",
        padding=(0, 2),
    ))
    console.print()

    # ── Telegram final
    tg_body = "\n\n".join(tg_lines)
    tg(
        f"✅ <b>Mastering complete</b>  —  {len(results)}/{len(files)} tracks\n"
        f"⏱ Total: {total_dur:.0f}s\n\n"
        + tg_body
    )


if __name__ == "__main__":
    main()