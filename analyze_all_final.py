import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pathlib import Path

FILES = [
    "D:\\GitHub\\AIMusicMasteringFactory\\sound\\wav_output\\Felt Piano & Jazz v 2.2 Basic_Lofi_Master.wav",
    "D:\\GitHub\\AIMusicMasteringFactory\\sound\\wav_output\\Felt Piano & Jazz v 2.2 Clarity_Lofi_Master.wav",
    "D:\\GitHub\\AIMusicMasteringFactory\\sound\\wav_output\\Felt Piano & Jazz v 2.2 Fire_Lofi_Master.wav",
    "D:\\GitHub\\AIMusicMasteringFactory\\sound\\wav_output\\Felt Piano & Jazz v 2.2_Lofi_Master.wav"
]

plt.figure(figsize=(14, 8), facecolor="#111")
ax = plt.subplot(111)
ax.set_facecolor("#222")
ax.grid(True, color="#444", lw=0.5)

colors = ["#ef4444", "#3b82f6", "#f59e0b", "#10b981"]
labels = ["Basic", "Clarity", "Fire", "Original v2.2"]

for idx, file_path in enumerate(FILES):
    path = Path(file_path)
    print(f"\n── Анализ: {path.name} ──")
    if not path.exists():
        print("Файл не найден!")
        continue
        
    data, fs = sf.read(str(path))
    if data.ndim == 1: data = np.stack([data, data], axis=1)
    mono = (data[:, 0] + data[:, 1]) / 2.0
    
    # Dynamics
    rms = np.sqrt(np.mean(mono**2))
    peak = np.max(np.abs(mono))
    def to_db(v): return 20*np.log10(v+1e-12)
    print(f"RMS: {to_db(rms):.2f} dBFS | Peak: {to_db(peak):.2f} dBFS")
    
    # Spectrum
    N_FFT = min(131072, len(mono))
    w = np.hanning(N_FFT)
    sp = np.abs(np.fft.rfft(mono[:N_FFT] * w, n=N_FFT))
    fr = np.fft.rfftfreq(N_FFT, 1.0/fs)
    db = 20 * np.log10(sp + 1e-12)
    db_s = np.convolve(db, np.ones(100)/100, mode='same')
    
    # Bands
    bands = {
        "Sub (20-60)": (20, 60),
        "Bass (60-250)": (60, 250),
        "Low Mid (250-500)": (250, 500),
        "Mid (500-2k)": (500, 2000),
        "High Mid (2k-6k)": (2000, 6000),
        "High (6k-12k)": (6000, 12000),
    }
    for name, (f1, f2) in bands.items():
        mask = (fr >= f1) & (fr <= f2)
        print(f"  {name:17s} : {np.mean(db_s[mask]):+.1f} dB")
        
    ax.semilogx(fr, db_s, color=colors[idx], lw=1.2, label=labels[idx], alpha=0.8)

ax.set_xlim(20, 20000)
# Dynamic y-limit based on last run
ax.set_ylim(-80, 50)
TICKS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
ax.set_xticks(TICKS)
ax.set_xticklabels([str(t) for t in TICKS])
[t.set_color("#ccc") for t in ax.get_xticklabels() + ax.get_yticklabels()]
ax.spines[:].set_color("#444")
ax.set_xlabel("Frequency (Hz)", color="#ccc")
ax.legend(loc="lower left", facecolor="#222", edgecolor="#444", labelcolor="#fff")
ax.set_title("Comparison of Lofi Masters (v2.2 Variations)", color="#fff")

out_chart = Path("analysis") / "Comparison_v2.2_All.png"
out_chart.parent.mkdir(exist_ok=True)
plt.savefig(str(out_chart), dpi=120, bbox_inches="tight", facecolor="#111")
print(f"\n[CHART] {out_chart}")
