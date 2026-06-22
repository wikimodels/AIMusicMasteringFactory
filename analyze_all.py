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
IN_DIR = ROOT / "sound" / "wav_input"
OUT_DIR = ROOT / "analysis"

files_to_analyze = [
    "Clean Jazz Guitar Delay Basic.wav",
    "Muted Felt Piano Coldness Basic.wav",
    "Springtime Jubilee v 1.1 (Remastered).wav",
    "Stained Concrete.wav"
]

def analyze_file(filename):
    fpath = IN_DIR / filename
    if not fpath.exists():
        print(f"[SKIP] Not found: {filename}")
        return

    data, sr = sf.read(str(fpath))
    mono = data.mean(axis=1) if data.ndim > 1 else data

    n = 131072
    w = np.hanning(min(n, len(mono)))
    sig = mono[:len(w)] * w
    sp = np.abs(np.fft.rfft(sig, n=n))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    db = 20 * np.log10(sp + 1e-9)

    # Smooth the curve
    k = np.ones(100) / 100
    db_s = np.convolve(db, k, mode="same")
    
    mask = (freqs >= 20) & (freqs <= 20000)

    fig, ax1 = plt.subplots(1, 1, figsize=(14, 6), facecolor="#0d0d0d")
    fig.suptitle(f"Full Resonance Profile — {filename}", color="#e0e0e0", fontsize=13, fontweight="bold")

    BG, GR = "#1a1a1a", "#2a2a2a"
    ax1.set_facecolor(BG)
    ax1.tick_params(colors="#888")
    ax1.spines[:].set_color(GR)
    ax1.grid(True, color=GR, linewidth=0.5)
    [l.set_color("#888") for l in ax1.get_xticklabels() + ax1.get_yticklabels()]

    ax1.semilogx(freqs[mask], db_s[mask], color="#7ec8e3", lw=1.2, label="Original Spectrum", alpha=0.9)

    ax1.set_xlim(20, 20000)
    TICKS = [20, 50, 100, 200, 400, 800, 1000, 2000, 4000, 8000, 16000, 20000]
    TLABELS = ["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
    ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABELS, fontsize=8)
    ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
    ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)

    # Highlights
    ax1.axvspan(200, 300, color='brown', alpha=0.1, label='Boxy (200-300Hz)')
    ax1.axvspan(300, 600, color='yellow', alpha=0.05, label='Mud/Honk (300-600Hz)')
    ax1.axvspan(800, 2500, color='red', alpha=0.1, label='Plastic/Nasal (800-2.5kHz)')
    ax1.axvspan(3000, 5000, color='magenta', alpha=0.1, label='Harshness/Buzz (3k-5kHz)')
    ax1.axvspan(7000, 15000, color='white', alpha=0.05, label='Digital Sand (7k-15kHz)')

    ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9, loc="lower left")

    out_png = OUT_DIR / f"{Path(filename).stem}_full_profile.png"
    plt.tight_layout()
    plt.savefig(str(out_png), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close()
    print(f"[DONE] Saved: {out_png.name}")

if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    for f in files_to_analyze:
        analyze_file(f)
