import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parent

# Анализируем оба файла - Basic и обычный
files = {
    "Clean Jazz Guitar Delay Basic.wav":                              "Basic (Original)",
    "Clean Jazz Guitar Delay.wav":                                    "Delay (Original)",
    "sound/wav_output/Clean_Jazz_Guitar_Delay_Basic_Fixed_v2.wav":    "Basic Fixed v2",
    "sound/wav_output/Clean_Jazz_Guitar_Delay_Fixed_v2.wav":          "Delay Fixed v2",
}

out_path = ROOT / "analysis" / "jazz_hires_hf_v2_analysis.png"

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), facecolor="#0d0d0d")
fig.suptitle("High Frequency Detail — Jazz Guitar (2k-20k Hz)", color="#e0e0e0", fontsize=13, fontweight="bold")

COLORS = ["#7ec8e3", "#c084fc", "#f9a825", "#4ade80"]
BG, GR = "#1a1a1a", "#2a2a2a"
TICKS = [2000, 3000, 4000, 5000, 6000, 7000, 8000, 10000, 12000, 15000, 20000]
TLABELS = ["2k","3k","4k","5k","6k","7k","8k","10k","12k","15k","20k"]

for ax in (ax1, ax2):
    ax.set_facecolor(BG)
    ax.tick_params(colors="#888")
    ax.spines[:].set_color(GR)
    ax.grid(True, color=GR, linewidth=0.5)
    [l.set_color("#888") for l in ax.get_xticklabels() + ax.get_yticklabels()]

for i, (fname, label) in enumerate(files.items()):
    fpath = ROOT / fname
    if not fpath.exists():
        print(f"[SKIP] Not found: {fpath}")
        continue

    data, sr = sf.read(str(fpath))
    mono = data.mean(axis=1) if data.ndim > 1 else data

    # High-res FFT
    n = 131072
    w   = np.hanning(min(n, len(mono)))
    sig = mono[:len(w)] * w
    sp  = np.abs(np.fft.rfft(sig, n=n))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    db = 20 * np.log10(sp + 1e-9)

    # Smooth
    k = np.ones(40) / 40
    db_s = np.convolve(db, k, mode="same")

    mask_hi = (freqs >= 2000) & (freqs <= 20000)
    color = COLORS[i % len(COLORS)]

    # Ax1: оригиналы
    if i < 2:
        ax1.semilogx(freqs[mask_hi], db_s[mask_hi], color=color, lw=1.5, label=label, alpha=0.85)
    # Ax2: fixed
    else:
        ax2.semilogx(freqs[mask_hi], db_s[mask_hi], color=color, lw=1.5, label=label, alpha=0.85)
    print(f"[OK] {label}")

for ax, title in ((ax1, "Originals — high freq detail"), (ax2, "Fixed versions — high freq detail")):
    ax.set_xlim(2000, 20000)
    ax.set_xticks(TICKS); ax.set_xticklabels(TLABELS, fontsize=8)
    ax.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax.set_ylabel("Level (dB)", color="#888", fontsize=9)
    ax.set_title(title, color="#ccc", fontsize=10, pad=6)
    ax.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

out = ROOT / "analysis" / "jazz_hires_hf_v2_analysis.png"
plt.tight_layout()
plt.savefig(str(out), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[DONE] Saved: {out}")
