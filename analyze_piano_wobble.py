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

ROOT = Path(__file__).parent

orig_path = ROOT / "sound/wav_input/Muted Felt Piano Coldness Basic.wav"
master_path = ROOT / "sound/wav_output/Muted Felt Piano Coldness Basic_DarkJazz_Master.wav"

if not orig_path.exists() or not master_path.exists():
    print("Files not found!")
    sys.exit(1)

data_o, sr = sf.read(str(orig_path))
data_m, _ = sf.read(str(master_path))

# Ensure stereo
if data_o.ndim == 1: data_o = np.stack([data_o, data_o], axis=1)
if data_m.ndim == 1: data_m = np.stack([data_m, data_m], axis=1)

# Shorten to first 30 seconds for detailed temporal analysis
max_len = min(len(data_o), len(data_m), int(30 * sr))
data_o = data_o[:max_len]
data_m = data_m[:max_len]

# 1. Calculate Stereo Correlation (Phase) over time
frame_ms = 500
frame_len = int(sr * frame_ms / 1000)
n_frames = len(data_o) // frame_len

times = np.arange(n_frames) * frame_ms / 1000
corr_o = np.zeros(n_frames)
corr_m = np.zeros(n_frames)

for i in range(n_frames):
    start = i * frame_len
    end = start + frame_len
    
    L_o, R_o = data_o[start:end, 0], data_o[start:end, 1]
    L_m, R_m = data_m[start:end, 0], data_m[start:end, 1]
    
    # Correlation coefficient
    c_o = np.corrcoef(L_o, R_o)[0, 1] if np.std(L_o) > 1e-6 and np.std(R_o) > 1e-6 else 0
    c_m = np.corrcoef(L_m, R_m)[0, 1] if np.std(L_m) > 1e-6 and np.std(R_m) > 1e-6 else 0
    
    corr_o[i] = c_o
    corr_m[i] = c_m

# 2. Spectrum comparison
mono_o = data_o.mean(axis=1)
mono_m = data_m.mean(axis=1)

n = 65536
w = np.hanning(min(n, len(mono_o)))
sp_o = np.abs(np.fft.rfft(mono_o[:len(w)] * w, n=n))
sp_m = np.abs(np.fft.rfft(mono_m[:len(w)] * w, n=n))
freqs = np.fft.rfftfreq(n, 1 / sr)

db_o = 20 * np.log10(sp_o + 1e-9)
db_m = 20 * np.log10(sp_m + 1e-9)

k = np.ones(80) / 80
db_o = np.convolve(db_o, k, mode="same")
db_m = np.convolve(db_m, k, mode="same")

# Plot
fig = plt.figure(figsize=(14, 10), facecolor="#0d0d0d")
gs = gridspec.GridSpec(2, 1, height_ratios=[1.5, 1], hspace=0.3)
fig.suptitle("Felt Piano Wobble & Resonance Analysis", color="#e0e0e0", fontsize=14, fontweight="bold")
BG, GR = "#1a1a1a", "#2a2a2a"

# Top: Spectrum
ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(BG)
ax1.grid(True, color=GR)
mask = (freqs >= 20) & (freqs <= 20000)
ax1.semilogx(freqs[mask], db_o[mask], color="#7ec8e3", label="Original", alpha=0.8)
ax1.semilogx(freqs[mask], db_m[mask], color="#c084fc", label="DarkJazz Master", alpha=0.8)
ax1.set_xlim(20, 20000)
ax1.set_xticks([20, 50, 100, 200, 400, 800, 2000, 5000, 10000, 20000])
ax1.set_xticklabels(["20","50","100","200","400","800","2k","5k","10k","20k"])
[l.set_color("#888") for l in ax1.get_xticklabels() + ax1.get_yticklabels()]
ax1.set_xlabel("Frequency (Hz)", color="#888")
ax1.set_ylabel("Level (dB)", color="#888")
ax1.set_title("Frequency Spectrum Comparison", color="#ccc")
ax1.axvspan(350, 550, color='red', alpha=0.1, label='Target Plastic Cut (400 & 520Hz)')
ax1.legend(facecolor="#222", labelcolor="#ccc")

# Bottom: Stereo Correlation
ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(BG)
ax2.grid(True, color=GR)
ax2.plot(times, corr_o, color="#7ec8e3", label="Original Phase Correlation", alpha=0.8, lw=1.5)
ax2.plot(times, corr_m, color="#c084fc", label="Mastered Phase Correlation", alpha=0.8, lw=1.5)
ax2.set_ylim(-0.2, 1.0)
ax2.set_xlim(0, 30)
ax2.axhline(0.5, color='red', linestyle='--', alpha=0.3, label='Phase Danger Zone (<0.5)')
[l.set_color("#888") for l in ax2.get_xticklabels() + ax2.get_yticklabels()]
ax2.set_xlabel("Time (seconds)", color="#888")
ax2.set_ylabel("Correlation (-1 to 1)", color="#888")
ax2.set_title("Stereo Phase Stability over Time (Wobble Check)", color="#ccc")
ax2.legend(facecolor="#222", labelcolor="#ccc", loc="lower right")

out = ROOT / "analysis/piano_wobble_analysis.png"
plt.savefig(str(out), dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"Saved: {out}")
