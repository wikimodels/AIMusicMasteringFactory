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
file_path = ROOT / "artists" / "Springtime Jubilee Upbeat Piano Solo" / "sound" / "wav_input" / "ОК Deep B Major Pulse.wav"

if not file_path.exists():
    print(f"File not found: {file_path}")
    sys.exit(1)

data, sr = sf.read(str(file_path))
mono = data.mean(axis=1) if data.ndim > 1 else data

n = 131072
w   = np.hanning(min(n, len(mono)))
sig = mono[:len(w)] * w
sp  = np.abs(np.fft.rfft(sig, n=n))
freqs = np.fft.rfftfreq(n, 1 / sr)
db = 20 * np.log10(sp + 1e-9)

k = np.ones(200) / 200
db_s = np.convolve(db, k, mode="same")

fig, ax1 = plt.subplots(1, 1, figsize=(14, 6), facecolor="#0d0d0d")
fig.suptitle("Frequency Profile — Springtime Jubilee Pulse", color="#e0e0e0", fontsize=13, fontweight="bold")

mask = (freqs >= 20) & (freqs <= 20000)
ax1.set_facecolor("#1a1a1a")
ax1.tick_params(colors="#888")
ax1.spines[:].set_color("#2a2a2a")
ax1.grid(True, color="#2a2a2a", linewidth=0.5)
ax1.semilogx(freqs[mask], db_s[mask], color="#7ec8e3", lw=1.2, label="Original", alpha=0.8)

ax1.set_xlim(20, 20000)
ax1.set_xticks([20, 50, 100, 250, 500, 1000, 2500, 4000, 8000, 16000])
ax1.set_xticklabels(["20","50","100","250","500","1k","2.5k","4k","8k","16k"], fontsize=8)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.axvspan(260, 440, color='yellow', alpha=0.05, label='Mud / Boxiness (260-440)')
ax1.axvspan(3000, 5000, color='red', alpha=0.1, label='Ear Fatigue / Harsh (3k-5k)')
ax1.axvspan(12000, 20000, color='blue', alpha=0.05, label='Digital Hiss (>12k)')
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

out = ROOT / "analysis" / "pulse_analysis.png"
plt.tight_layout()
plt.savefig(str(out), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"Saved: {out}")
