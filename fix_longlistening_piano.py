"""
fix_longlistening_piano.py
==========================
🎧  СКРИПТ «СУТКИ НАПРОЛЁТ» v2 — Long-Listening Piano Mastering

Треки:
  • Piano Universal.wav
  • Piano_Original.wav
  Расположение: sound/wav_input/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПРИНЦИП (взят из NCM-PAD-03 — лучший результат в сессии):

  Чистая минималистичная цепочка. Ничего лишнего.
  НЕТ shelf EQ, НЕТ soft limiter, НЕТ компрессии.
  Только убрать плохое, не добавляя новых артефактов.

  КЛЮЧЕВОЙ ХОД для «сутки напролёт»:
  — убрать mud (250–440 Hz) динамически → прозрачность
  — убрать sub rumble → чистое дно
  — micro notch -0.8 dB @ 3.5 kHz → снять острую усталость без потери тела
  — HF exciter (очень лёгкий) → живость без резкости
  — Tape roll-off @ 14 kHz → убрать цифровую жёсткость
  — Peak normalize

  В v1 были: Warmth shelf +1.5dB → поднял пики → Soft Limiter
  качал на атаках → скрип. Теперь это убрано.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ЦЕПОЧКА:

  Step 1. HPF @ 36 Hz             — sub rumble, A0 рояля (27.5 Hz) цела
  Step 2. Dynamic Mud Cut         — 260–440 Hz | threshold -30 dB | max -4 dB
                                    release=100ms — не мажет piano decay
  Step 3. Micro Upper-mid Notch   — -0.8 dB @ 3.5 kHz, Q=1.0
                                    едва слышно, но убирает усталость ушей
  Step 4. HF Exciter (лёгкий)    — > 2.5 kHz | drive=5 dB | mix=7%
                                    живость, без артефактов
  Step 5. Tape Roll-Off @ 14 kHz  — цифровую жёсткость долой
  Step 6. Peak Normalize

Выходные файлы:
  sound/wav_output/Piano_Universal_LL.wav
  sound/wav_output/Piano_Original_LL.wav

Графики:
  analysis/ll_Piano_Universal_spectrum.png
  analysis/ll_Piano_Original_spectrum.png
  analysis/ll_comparison.png
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

# ──────────────────────────────────────────────────────────────
ROOT    = Path(__file__).parent
IN_DIR  = ROOT / "sound" / "wav_input"
OUT_DIR = ROOT / "sound" / "wav_output"
ANA_DIR = ROOT / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ANA_DIR.mkdir(exist_ok=True)

TRACKS = [
    ("Piano Universal.wav",  "Piano_Universal_LL.wav"),
    ("Piano_Original.wav",   "Piano_Original_LL.wav"),
]

BG    = "#0d0d0d"
PANEL = "#141414"
GRID  = "#252525"
FREQ_TICKS  = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
FREQ_LABELS = ["31","63","125","250","500","1k","2k","4k","8k","16k"]


# ══════════════════════════════════════════════════════════════
#  DSP
# ══════════════════════════════════════════════════════════════

def apply_hpf(ch, fs, freq=36.0, order=3):
    """Sub rumble. A0 рояля (27.5 Hz) остаётся."""
    sos = sg.butter(order, freq, btype="high", fs=fs, output="sos")
    return sg.sosfiltfilt(sos, ch)


def apply_dynamic_mud(ch, fs, f_lo=260, f_hi=440,
                      threshold_db=-30.0, max_cut_db=-4.0,
                      attack_ms=10.0, release_ms=100.0):
    """
    Динамический mud cut — только когда уровень полосы превышает порог.
    release=100ms: не смазывает piano decay.
    max_cut_db=-4.0: мягче чем для пэда (-5 dB) — piano нежнее.
    """
    sos_bp = sg.butter(3, [f_lo, f_hi], btype="band", fs=fs, output="sos")
    mud = sg.sosfiltfilt(sos_bp, ch)

    frame = max(1, int(attack_ms / 1000.0 * fs))
    rms = np.sqrt(np.convolve(mud**2, np.ones(frame)/frame, mode="same") + 1e-12)
    db_env = 20.0 * np.log10(rms + 1e-12)

    over = np.clip(db_env - threshold_db, 0.0, None)
    max_lin = 1.0 - 10.0 ** (max_cut_db / 20.0)
    cut = np.clip(over / 18.0, 0.0, 1.0) * max_lin

    rel = max(1, int(release_ms / 1000.0 * fs))
    cut_s = sg.filtfilt(np.ones(rel)/rel, [1.0], cut)
    return ch - mud * cut_s


def apply_micro_notch(ch, fs, f0=3500.0, gain_db=-0.8, Q=1.0):
    """
    Micro notch -0.8 dB @ 3.5 kHz.
    Едва слышимо, но снимает пиковую чувствительность уха.
    НЕ режет presence — только сглаживает острый пик усталости.
    """
    A  = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / fs
    al = np.sin(w0) / (2.0 * Q)
    b = [1.0 + al*A,  -2.0*np.cos(w0),  1.0 - al*A]
    a = [1.0 + al/A,  -2.0*np.cos(w0),  1.0 - al/A]
    return sg.lfilter(b, a, ch)


def apply_hf_exciter(ch, fs, crossover_hz=2500.0, drive_db=5.0, mix=0.07):
    """
    Лёгкий HF exciter — нечётные гармоники выше 2.5 kHz.
    drive=5 dB (было 7 у пэда), mix=7% (было 10%) — мягче для piano.
    Добавляет живость без агрессии.
    """
    sos_hp = sg.butter(3, crossover_hz, btype="high", fs=fs, output="sos")
    hf = sg.sosfiltfilt(sos_hp, ch)
    drive = 10.0 ** (drive_db / 20.0)
    hf_sat = np.tanh(hf * drive) / drive
    excite = hf_sat - hf
    return ch + excite * mix


def apply_tape_rolloff(ch, fs, freq=14000.0, order=2):
    """Tape roll-off @ 14 kHz. 2-й порядок = очень плавный."""
    sos = sg.butter(order, freq, btype="low", fs=fs, output="sos")
    return sg.sosfiltfilt(sos, ch)


# ══════════════════════════════════════════════════════════════
#  PROCESS ONE TRACK
# ══════════════════════════════════════════════════════════════
def process_track(input_path: Path, output_path: Path):
    print(f"\n{'─'*58}")
    print(f"  Трек  : {input_path.name}")
    print(f"  Выход : {output_path.name}")
    print(f"{'─'*58}")

    data, fs = sf.read(str(input_path))
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    out = data.astype(np.float64).copy()
    print(f"  SR={fs} Hz | Duration={len(data)/fs:.1f}s")

    # Step 1
    for c in range(2):
        out[:, c] = apply_hpf(out[:, c], fs)
    print("  ✅ Step 1: HPF @ 36 Hz  (sub rumble убран, A0 рояля цела)")

    # Step 2
    for c in range(2):
        out[:, c] = apply_dynamic_mud(out[:, c], fs)
    print("  ✅ Step 2: Dynamic mud cut 260–440 Hz | −30 dB thr | max −4 dB | rel 100ms")

    # Step 3
    for c in range(2):
        out[:, c] = apply_micro_notch(out[:, c], fs)
    print("  ✅ Step 3: Micro notch −0.8 dB @ 3.5 kHz  (снимает усталость ушей)")

    # Step 4
    for c in range(2):
        out[:, c] = apply_hf_exciter(out[:, c], fs)
    print("  ✅ Step 4: HF Exciter > 2.5 kHz | drive=5 dB | mix=7%  (живость)")

    # Step 5
    for c in range(2):
        out[:, c] = apply_tape_rolloff(out[:, c], fs)
    print("  ✅ Step 5: Tape roll-off @ 14 kHz  (цифровая жёсткость долой)")

    # Step 6 — normalize
    peak_orig = float(np.max(np.abs(data)))
    peak_out  = float(np.max(np.abs(out)))
    scale = peak_orig / (peak_out + 1e-12)
    out  *= scale
    print(f"  ✅ Step 6: Normalize  {20*np.log10(peak_out+1e-12):+.2f} → "
          f"{20*np.log10(np.max(np.abs(out))+1e-12):+.2f} dBFS "
          f"(gain {20*np.log10(scale):+.2f} dB)")

    sf.write(str(output_path), out.astype(np.float32), fs, subtype="PCM_24")
    print(f"  💾 Сохранено: {output_path}")
    return data, out, fs


# ══════════════════════════════════════════════════════════════
#  CHARTS
# ══════════════════════════════════════════════════════════════
def smooth_spec(mono, fs, nfft=65536, sm=70):
    n = min(nfft, len(mono))
    sp = np.abs(np.fft.rfft(mono[:n] * np.hanning(n), n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0/fs)
    db = 20.0 * np.log10(sp + 1e-9)
    return fr, np.convolve(db, np.ones(sm)/sm, mode="same")

def ax_style(ax, title=""):
    ax.set_facecolor(PANEL)
    if title:
        ax.set_title(title, color="#bbb", fontsize=9, pad=5, fontweight="bold")
    ax.tick_params(colors="#555", labelsize=8)
    ax.spines[:].set_color(GRID)
    ax.grid(True, color=GRID, lw=0.4, linestyle="--")
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#555")

def plot_before_after(orig, fixed, fs, title, out_path):
    om = (orig[:,0]+orig[:,1])/2
    fm = (fixed[:,0]+fixed[:,1])/2
    fr, db_o = smooth_spec(om, fs)
    _,  db_f = smooth_spec(fm, fs)
    mask = (fr >= 20) & (fr <= 20000)

    fig, axes = plt.subplots(2, 1, figsize=(15, 9), facecolor=BG)
    fig.suptitle(f"Long-Listening Master v2 — {title}\nBefore / After",
                 color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99)

    ax1 = axes[0]
    ax1.set_facecolor(PANEL)
    ax1.semilogx(fr[mask], db_o[mask], color="#7ec8e3", lw=1.3,
                 alpha=0.6, linestyle="--", label="Original")
    ax1.semilogx(fr[mask], db_f[mask], color="#f472b6", lw=1.6,
                 alpha=0.95, label="Long-Listening v2")

    zones = [
        (20,   40,   "#60a5fa", "HPF"),
        (260,  440,  "#f97316", "Dynamic mud cut"),
        (2500, 7000, "#4ade80", "HF Exciter (light)"),
        (3000, 4000, "#ef4444", "Micro notch −0.8dB"),
    ]
    for x0, x1, col, lbl in zones:
        ax1.axvspan(x0, x1, color=col, alpha=0.07)
        ax1.text(np.sqrt(x0*x1), ax1.get_ylim()[1] if ax1.get_ylim()[1] > 0 else 30,
                 lbl, color=col, fontsize=6.5, ha="center", va="top", alpha=0.7)

    ax1.set_xlim(20, 20000)
    ax1.set_xticks(FREQ_TICKS); ax1.set_xticklabels(FREQ_LABELS)
    ax1.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
    ax1.set_ylabel("Level (dB)", color="#666", fontsize=9)
    ax1.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc",
               fontsize=8, loc="lower left")
    ax_style(ax1, "Spectrum Overlay")

    ax2 = axes[1]
    ax2.set_facecolor(PANEL)
    diff = np.convolve(db_f - db_o, np.ones(80)/80, mode="same")
    ax2.semilogx(fr[mask], diff[mask], color="#34d399", lw=1.5,
                 label="Difference (Fixed − Original)")
    ax2.axhline(0, color="#555", linestyle="--", lw=0.8)
    ax2.fill_between(fr[mask], 0, diff[mask],
                     where=(diff[mask]>0), color="#34d399", alpha=0.2)
    ax2.fill_between(fr[mask], 0, diff[mask],
                     where=(diff[mask]<0), color="#ef4444", alpha=0.2)

    for x, lbl, col in [(28,"HPF↓","#60a5fa"), (340,"Mud↓","#f97316"),
                          (3500,"3.5k↓","#ef4444"), (5000,"HF+","#4ade80"),
                          (14000,"Roll↓","#facc15")]:
        if mask.any():
            ypos = float(np.interp(np.log10(x),
                                   np.log10(fr[mask]+1e-9), diff[mask]))
            ax2.text(x, ypos + (0.15 if ypos >= 0 else -0.15),
                     lbl, color=col, fontsize=7.5, ha="center", va="center")

    ax2.set_xlim(20, 20000)
    ax2.set_xticks(FREQ_TICKS); ax2.set_xticklabels(FREQ_LABELS)
    ax2.set_ylim(-5, 3)
    ax2.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
    ax2.set_ylabel("ΔdB", color="#666", fontsize=9)
    ax2.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
    ax_style(ax2, "Correction Curve — minimal & clean (v2: no shelf EQ, no limiter)")

    plt.tight_layout(rect=[0,0,1,0.96])
    plt.savefig(str(out_path), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"  [PNG] {out_path.name}")


def plot_comparison(entries, out_path):
    fig, axes = plt.subplots(2, 1, figsize=(15, 9), facecolor=BG)
    fig.suptitle("Long-Listening v2 — Сравнение FIXED треков\n"
                 "Piano Universal  vs  Piano Original",
                 color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99)

    colors_orig = ["#7ec8e3", "#a78bfa"]
    colors_fix  = ["#f472b6", "#34d399"]
    ax1, ax2 = axes

    for i, (label, orig, fixed, fs) in enumerate(entries):
        om = (orig[:,0]+orig[:,1])/2
        fm = (fixed[:,0]+fixed[:,1])/2
        fr, db_o = smooth_spec(om, fs)
        _,  db_f = smooth_spec(fm, fs)
        mask = (fr >= 20) & (fr <= 20000)

        ax1.set_facecolor(PANEL)
        ax1.semilogx(fr[mask], db_o[mask], color=colors_orig[i], lw=1.0,
                     alpha=0.4, linestyle="--", label=f"{label} Original")
        ax1.semilogx(fr[mask], db_f[mask], color=colors_fix[i], lw=1.5,
                     alpha=0.9, label=f"{label} Fixed (LL v2)")

        diff = np.convolve(db_f - db_o, np.ones(80)/80, mode="same")
        ax2.set_facecolor(PANEL)
        ax2.semilogx(fr[mask], diff[mask], color=colors_fix[i], lw=1.4,
                     alpha=0.85, label=f"{label} correction")
        ax2.fill_between(fr[mask], 0, diff[mask],
                         where=(diff[mask]>0), color=colors_fix[i], alpha=0.12)
        ax2.fill_between(fr[mask], 0, diff[mask],
                         where=(diff[mask]<0), color=colors_orig[i], alpha=0.10)

    ax2.axhline(0, color="#555", linestyle="--", lw=0.8)
    for x0, x1, col in [(20,40,"#60a5fa"),(260,440,"#f97316"),
                          (3000,4000,"#ef4444"),(2500,7000,"#4ade80")]:
        ax1.axvspan(x0, x1, color=col, alpha=0.04)
        ax2.axvspan(x0, x1, color=col, alpha=0.04)

    for ax in [ax1, ax2]:
        ax.set_xlim(20, 20000)
        ax.set_xticks(FREQ_TICKS); ax.set_xticklabels(FREQ_LABELS)
        ax.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
        ax.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc",
                  fontsize=8, loc="lower left")

    ax1.set_ylabel("Level (dB)", color="#666", fontsize=9)
    ax2.set_ylabel("ΔdB", color="#666", fontsize=9)
    ax2.set_ylim(-5, 3)
    ax_style(ax1, "Spectrum: Original (dashed) vs Long-Listening v2 Fixed (solid)")
    ax_style(ax2, "Correction Curves comparison")

    plt.tight_layout(rect=[0,0,1,0.96])
    plt.savefig(str(out_path), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ══════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("  Long-Listening Piano Mastering  v2")
print("  «Чисто. Без артефактов. Сутки напролёт.»")
print("="*60)

processed = []
for in_name, out_name in TRACKS:
    in_path  = IN_DIR  / in_name
    out_path = OUT_DIR / out_name

    if not in_path.exists():
        print(f"\n  ⚠️  Не найден: {in_path}")
        continue

    orig, fixed, fs = process_track(in_path, out_path)

    label = in_name.replace(".wav","")
    chart = ANA_DIR / f"ll_{label.replace(' ','_')}_spectrum.png"
    print(f"\n  График Before/After…")
    plot_before_after(orig, fixed, fs, label, chart)

    processed.append((label, orig, fixed, fs))

if len(processed) >= 2:
    print("\n  Сравнительный график…")
    plot_comparison(processed, ANA_DIR / "ll_comparison.png")

print("\n" + "="*60)
print("  DONE!")
for _, out_name in TRACKS:
    p = OUT_DIR / out_name
    if p.exists():
        print(f"    ✅ {out_name}")
print("="*60 + "\n")
