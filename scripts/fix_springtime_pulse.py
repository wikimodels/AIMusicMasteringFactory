"""
fix_springtime_pulse.py
==========================
🎧 СКРИПТ «СУТКИ НАПРОЛЁТ» v2 — Long-Listening Piano Mastering
Специально для трека "ОК Deep B Major Pulse.wav"

Принцип:
  — HPF @ 36 Hz (убрать rumble)
  — Dynamic Mud Cut @ 260-440 Hz (убрать коробку)
  — Micro Notch @ 3.5 kHz (убрать усталость/боль)
  — Легкий Exciter (живость)
  — Tape Roll-off @ 14 kHz (убрать цифровую пыль)
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
ROOT = Path(__file__).parent.parent
ARTIST_DIR = ROOT / "artists" / "Springtime Jubilee Upbeat Piano Solo"
IN_DIR  = ARTIST_DIR / "sound" / "wav_input"
OUT_DIR = ARTIST_DIR / "sound" / "wav_output"
ANA_DIR = ROOT / "analysis"

OUT_DIR.mkdir(parents=True, exist_ok=True)
ANA_DIR.mkdir(exist_ok=True)

TRACK_IN = "ОК Deep B Major Pulse.wav"
TRACK_OUT = "ОК Deep B Major Pulse_Fixed.wav"

BG    = "#0d0d0d"
PANEL = "#141414"
GRID  = "#252525"
FREQ_TICKS  = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
FREQ_LABELS = ["31","63","125","250","500","1k","2k","4k","8k","16k"]

# ══════════════════════════════════════════════════════════════
#  DSP FUNCTIONS
# ══════════════════════════════════════════════════════════════

def apply_hpf(ch, fs, freq=36.0, order=3):
    sos = sg.butter(order, freq, btype="high", fs=fs, output="sos")
    return sg.sosfiltfilt(sos, ch)

def apply_dynamic_mud(ch, fs, f_lo=260, f_hi=440,
                      threshold_db=-30.0, max_cut_db=-4.0,
                      attack_ms=10.0, release_ms=100.0):
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

def apply_dynamic_derattle(ch, fs, f_lo=3000, f_hi=8000,
                           threshold_db=-25.0, max_cut_db=-4.5,
                           attack_ms=5.0, release_ms=40.0):
    """Смягчение стеклянного дребезжания на атаках молоточков (De-Rattle)"""
    sos_bp = sg.butter(3, [f_lo, f_hi], btype="band", fs=fs, output="sos")
    harsh = sg.sosfiltfilt(sos_bp, ch)

    frame = max(1, int(attack_ms / 1000.0 * fs))
    rms = np.sqrt(np.convolve(harsh**2, np.ones(frame)/frame, mode="same") + 1e-12)
    db_env = 20.0 * np.log10(rms + 1e-12)

    over = np.clip(db_env - threshold_db, 0.0, None)
    max_lin = 1.0 - 10.0 ** (max_cut_db / 20.0)
    cut = np.clip(over / 12.0, 0.0, 1.0) * max_lin

    rel = max(1, int(release_ms / 1000.0 * fs))
    cut_s = sg.filtfilt(np.ones(rel)/rel, [1.0], cut)
    return ch - harsh * cut_s

def apply_micro_notch(ch, fs, f0=3500.0, gain_db=-0.8, Q=1.0):
    A  = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * np.pi * f0 / fs
    al = np.sin(w0) / (2.0 * Q)
    b = [1.0 + al*A,  -2.0*np.cos(w0),  1.0 - al*A]
    a = [1.0 + al/A,  -2.0*np.cos(w0),  1.0 - al/A]
    return sg.lfilter(b, a, ch)

def apply_hf_exciter(ch, fs, crossover_hz=2500.0, drive_db=5.0, mix=0.07):
    sos_hp = sg.butter(3, crossover_hz, btype="high", fs=fs, output="sos")
    hf = sg.sosfiltfilt(sos_hp, ch)
    drive = 10.0 ** (drive_db / 20.0)
    hf_sat = np.tanh(hf * drive) / drive
    excite = hf_sat - hf
    return ch + excite * mix

def apply_tape_rolloff(ch, fs, freq=14000.0, order=2):
    sos = sg.butter(order, freq, btype="low", fs=fs, output="sos")
    return sg.sosfiltfilt(sos, ch)

def apply_ms_eq(y, fs):
    """
    Разделяет стерео на Mid/Side.
    Side: Срезает бас ниже 180 Hz (делает бас моно), убирает гул и фазовые проблемы.
    Mid: Мягкий срез ниже 200 Hz для расчистки плотного микса.
    """
    if y.ndim < 2: return y
    mid  = (y[:, 0] + y[:, 1]) * 0.5
    side = (y[:, 0] - y[:, 1]) * 0.5

    # Side HPF (убираем гул по бокам)
    sos_side = sg.butter(2, 180.0, "hp", fs=fs, output="sos")
    side = sg.sosfiltfilt(sos_side, side)

    # Mid HPF (чуть разгружаем центр от коробочного гула)
    sos_mid = sg.butter(2, 200.0, "hp", fs=fs, output="sos")
    # подмешиваем обработанный mid к оригиналу, чтобы не потерять тело
    mid = mid * 0.5 + sg.sosfiltfilt(sos_mid, mid) * 0.5

    return np.stack([mid + side, mid - side], axis=1)

# ══════════════════════════════════════════════════════════════
#  PROCESS
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

    for c in range(2): out[:, c] = apply_hpf(out[:, c], fs)
    print("  ✅ Step 1: HPF @ 36 Hz")

    out = apply_ms_eq(out, fs)
    print("  ✅ Step 1.5: Mid/Side EQ (Side HPF 180 Hz, бас теперь в моно)")

    for c in range(2): out[:, c] = apply_dynamic_mud(out[:, c], fs)
    print("  ✅ Step 2: Dynamic mud cut (260-440 Hz)")

    for c in range(2): out[:, c] = apply_micro_notch(out[:, c], fs)
    print("  ✅ Step 3: Micro notch −0.8 dB @ 3.5 kHz (убирает усталость)")

    for c in range(2): out[:, c] = apply_dynamic_derattle(out[:, c], fs)
    print("  ✅ Step 3.5: Dynamic De-Rattle (смягчение атак молоточков)")

    for c in range(2): out[:, c] = apply_hf_exciter(out[:, c], fs)
    print("  ✅ Step 4: HF Exciter > 2.5 kHz")

    for c in range(2): out[:, c] = apply_tape_rolloff(out[:, c], fs)
    print("  ✅ Step 5: Tape roll-off @ 14 kHz")

    peak_orig = float(np.max(np.abs(data)))
    peak_out  = float(np.max(np.abs(out)))
    scale = peak_orig / (peak_out + 1e-12)
    out  *= scale
    print(f"  ✅ Step 6: Peak Normalize (gain {20*np.log10(scale):+.2f} dB)")

    sf.write(str(output_path), out.astype(np.float32), fs, subtype="PCM_24")
    print(f"  💾 Сохранено: {output_path}")
    return data, out, fs

# ══════════════════════════════════════════════════════════════
#  CHARTING
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
    fig.suptitle(f"Long-Listening Fix — {title}", color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99)

    ax1 = axes[0]
    ax1.set_facecolor(PANEL)
    ax1.semilogx(fr[mask], db_o[mask], color="#7ec8e3", lw=1.3, alpha=0.6, linestyle="--", label="Original (Suno AI)")
    ax1.semilogx(fr[mask], db_f[mask], color="#f472b6", lw=1.6, alpha=0.95, label="Fixed (Long-Listening)")

    zones = [
        (20,   40,   "#60a5fa", "HPF (Rumble)"),
        (260,  440,  "#f97316", "Mud Cut (Boxy)"),
        (2500, 7000, "#4ade80", "Exciter"),
        (3000, 4000, "#ef4444", "Notch 3.5k (Pain)"),
    ]
    for x0, x1, col, lbl in zones:
        ax1.axvspan(x0, x1, color=col, alpha=0.07)
        ax1.text(np.sqrt(x0*x1), ax1.get_ylim()[1] if ax1.get_ylim()[1] > 0 else 30, lbl, color=col, fontsize=6.5, ha="center", va="top", alpha=0.7)

    ax1.set_xlim(20, 20000)
    ax1.set_xticks(FREQ_TICKS); ax1.set_xticklabels(FREQ_LABELS)
    ax1.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8, loc="lower left")
    ax_style(ax1, "Spectrum Overlay")

    ax2 = axes[1]
    ax2.set_facecolor(PANEL)
    diff = np.convolve(db_f - db_o, np.ones(80)/80, mode="same")
    ax2.semilogx(fr[mask], diff[mask], color="#34d399", lw=1.5, label="Difference (Fixed - Original)")
    ax2.axhline(0, color="#555", linestyle="--", lw=0.8)
    ax2.fill_between(fr[mask], 0, diff[mask], where=(diff[mask]>0), color="#34d399", alpha=0.2)
    ax2.fill_between(fr[mask], 0, diff[mask], where=(diff[mask]<0), color="#ef4444", alpha=0.2)

    ax2.set_xlim(20, 20000)
    ax2.set_xticks(FREQ_TICKS); ax2.set_xticklabels(FREQ_LABELS)
    ax2.set_ylim(-5, 3)
    ax2.set_ylabel("ΔdB", color="#666", fontsize=9)
    ax2.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
    ax_style(ax2, "Correction Curve")

    plt.tight_layout(rect=[0,0,1,0.96])
    plt.savefig(str(out_path), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"  [PNG] {out_path.name}")

if __name__ == "__main__":
    in_path  = IN_DIR  / TRACK_IN
    out_path = OUT_DIR / TRACK_OUT

    if not in_path.exists():
        print(f"\n  ⚠️  Файл не найден: {in_path}")
        sys.exit(1)

    print("\n============================================================")
    print("  CLEANING: Springtime Jubilee Pulse")
    print("============================================================")
    
    orig, fixed, fs = process_track(in_path, out_path)
    
    chart_path = ANA_DIR / "ll_pulse_spectrum.png"
    print("\n  Создание графика Before/After...")
    plot_before_after(orig, fixed, fs, "Springtime Jubilee Pulse", chart_path)
    
    print("\n============================================================")
    print("  ГОТОВО!")
    print("============================================================")
