import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

ROOT        = Path(__file__).parent
orig_path   = ROOT / "Clean Jazz Guitar Delay Basic.wav"
master_path = ROOT / "sound" / "wav_output" / "Clean_Jazz_Guitar_Delay_Fixed.wav"
out_path    = ROOT / "analysis" / "Clean_Jazz_Guitar_Delay_analysis.png"
stem        = "Clean Jazz Guitar Delay — Fix Analysis"

print(f"Original : {orig_path.exists()} -> {orig_path}")
print(f"Fixed    : {master_path.exists()} -> {master_path}")

orig_data, sr  = sf.read(str(orig_path))
master_data, _ = sf.read(str(master_path))

om = orig_data.mean(axis=1)   if orig_data.ndim > 1 else orig_data
mm = master_data.mean(axis=1) if master_data.ndim > 1 else master_data
n  = min(len(om), len(mm)); om, mm = om[:n], mm[:n]
print(f"Samples: {n}  sr={sr}")

def fft_db(s, n=65536):
    w   = np.hanning(min(n, len(s)))
    sig = s[:len(w)] * w
    sp  = np.abs(np.fft.rfft(sig, n=n))
    f   = np.fft.rfftfreq(n, 1 / sr)
    db  = 20 * np.log10(sp + 1e-9)
    k   = np.ones(80) / 80
    return f, np.convolve(db, k, mode="same")

def rms_c(s, ms=10):
    fr  = int(sr * ms / 1000)
    nf  = len(s) // fr
    r   = np.array([np.sqrt(np.mean(s[i*fr:(i+1)*fr]**2)) for i in range(nf)])
    return np.arange(nf) * ms / 1000, 20 * np.log10(r + 1e-9)

fo, do = fft_db(om);  fm, dm = fft_db(mm)
to, ro = rms_c(om);   tm, rm = rms_c(mm)
mask   = (fo >= 20) & (fo <= 20000)

BG, GR, ORIG, MASTER = "#1a1a1a", "#2a2a2a", "#7ec8e3", "#c084fc"
TICKS   = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
TLABELS = ["50", "100", "200", "500", "1k", "2k", "5k", "10k", "20k"]

fig = plt.figure(figsize=(14, 10), facecolor="#0d0d0d")
fig.suptitle(stem, color="#e0e0e0", fontsize=13, fontweight="bold", y=0.98)
gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.45, wspace=0.35)

def sa(ax, t):
    ax.set_facecolor(BG); ax.tick_params(colors="#888")
    ax.set_title(t, color="#ccc", fontsize=10, pad=6)
    ax.spines[:].set_color(GR); ax.grid(True, color=GR, linewidth=0.5)
    [l.set_color("#888") for l in ax.get_xticklabels() + ax.get_yticklabels()]

ax1 = fig.add_subplot(gs[0, :])
ax1.semilogx(fo[mask], do[mask], color=ORIG,   lw=1.5, label="Original", alpha=0.85)
ax1.semilogx(fm[mask], dm[mask], color=MASTER, lw=1.5, label="Fixed",    alpha=0.85)
ax1.set_xlim(20, 20000); ax1.set_ylim(-90, -10)
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABELS)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
sa(ax1, "Frequency Spectrum")

ax2 = fig.add_subplot(gs[1, 0])
ax2.plot(to, ro, color=ORIG,   lw=1.0, label="Original", alpha=0.8)
ax2.plot(tm, rm, color=MASTER, lw=1.0, label="Fixed",    alpha=0.8)
ax2.set_xlabel("Time (s)", color="#888", fontsize=9)
ax2.set_ylabel("RMS (dB)", color="#888", fontsize=9)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)
sa(ax2, "RMS Loudness Over Time")

ax3 = fig.add_subplot(gs[1, 1])
diff = dm[mask] - do[mask]
ax3.semilogx(fo[mask], diff, color="#f9a825", lw=1.5, alpha=0.9)
ax3.axhline(0, color="#555", lw=0.8, linestyle="--")
ax3.fill_between(fo[mask], 0, diff, where=diff > 0, color=MASTER, alpha=0.2)
ax3.fill_between(fo[mask], 0, diff, where=diff < 0, color=ORIG,   alpha=0.2)
ax3.set_xlim(20, 20000); ax3.set_xticks(TICKS); ax3.set_xticklabels(TLABELS)
ax3.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax3.set_ylabel("Delta (dB)", color="#888", fontsize=9)
sa(ax3, "Spectrum Delta (Fixed - Original)")

plt.savefig(str(out_path), dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[DONE] Saved: {out_path}")
