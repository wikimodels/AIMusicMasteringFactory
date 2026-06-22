import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "Guitar Jazz" / "Guitar & Jazz v 1.1.wav"
OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"── ГЛУБОКИЙ АНАЛИЗ ГИТАРЫ: {INPUT.name} ──")
if not INPUT.exists():
    print(f"ОШИБКА: Файл не найден по пути {INPUT}")
    sys.exit(1)

data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
data = data.astype(np.float64)

N = len(data)
mono = (data[:, 0] + data[:, 1]) / 2.0
side = (data[:, 0] - data[:, 1]) / 2.0

def to_db(v): return 20*np.log10(v+1e-12)

# ДИНАМИКА
peak_l = np.max(np.abs(data[:, 0]))
peak_r = np.max(np.abs(data[:, 1]))
rms_mono = np.sqrt(np.mean(mono**2))
crest = to_db(max(peak_l, peak_r)) - to_db(rms_mono)

print("\n1. ДИНАМИКА")
print(f"True Peak : L {to_db(peak_l):+.2f} dBFS | R {to_db(peak_r):+.2f} dBFS")
print(f"RMS Mono  : {to_db(rms_mono):+.2f} dBFS")
print(f"Crest Fact: {crest:.2f} dB")

# СТЕРЕО БАЗА
corr = np.mean(data[:,0] * data[:,1]) / (np.sqrt(np.mean(data[:,0]**2) * np.mean(data[:,1]**2)) + 1e-12)
print("\n2. СТЕРЕОПОЛЕ")
print(f"Correlation: {corr:+.2f} (1.0 = моно, 0.0 = широкое, <0 = противофаза)")

# ЧАСТОТЫ
N_FFT = min(131072, N)
w = np.hanning(N_FFT)
sp = np.abs(np.fft.rfft(mono[:N_FFT] * w, n=N_FFT))
fr = np.fft.rfftfreq(N_FFT, 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
sm = 100
db_s = np.convolve(db, np.ones(sm)/sm, mode='same')

print("\n3. ЧАСТОТНЫЙ БАЛАНС")
bands = {
    "Sub (20-60 Hz)": (20, 60),
    "Bass (60-250 Hz)": (60, 250),
    "Low Mid (250-500)": (250, 500),
    "Mid (500-2k)": (500, 2000),
    "High Mid (2k-6k)": (2000, 6000),
    "High (6k-12k)": (6000, 12000),
    "Air (12k-20k)": (12000, 20000),
}
for name, (f1, f2) in bands.items():
    mask = (fr >= f1) & (fr <= f2)
    print(f"  {name:18s} : {np.mean(db_s[mask]):+.1f} dB")

# РЕЗОНАНСЫ
baseline = uniform_filter1d(db_s, size=400)
peaks_diff = db_s - baseline
mask_res = (fr >= 100) & (fr <= 8000)
peaks_idx, _ = find_peaks(peaks_diff[mask_res], height=5.0, distance=100)
peaks_idx += np.where(mask_res)[0][0]
res_list = sorted([(fr[i], peaks_diff[i]) for i in peaks_idx], key=lambda x: -x[1])[:8]

print("\n4. ТОП РЕЗОНАНСОВ (потенциальные проблемы)")
if not res_list:
    print("  ✅ Аномальных пиков нет.")
else:
    for f0, amp in res_list:
        note = f"{f0:6.1f} Hz : +{amp:.1f} dB"
        if 2000 < f0 < 5000: print(f"  ⚠ {note} (Резкий 'свист' гитарных струн?)")
        elif 200 < f0 < 600: print(f"  ⚠ {note} (Коробочность / Муть деки?)")
        else: print(f"  ⚠ {note}")

# ГРАФИК
plt.figure(figsize=(14, 6), facecolor="#111")
ax = plt.subplot(111); ax.set_facecolor("#222"); ax.grid(True, color="#444", lw=0.5)
ax.semilogx(fr, db_s, color="#f59e0b", lw=1.2, label="Spectrum")
ax.semilogx(fr, baseline, color="#ec4899", lw=1.0, linestyle="--", alpha=0.7, label="Baseline")
for f0, amp in res_list:
    ax.axvline(f0, color="#ef4444", lw=0.8, linestyle=":")
    ax.text(f0, np.interp(f0, fr, db_s) + 5, f"{f0:.0f}", color="#ef4444", fontsize=8, ha='center')

ax.set_xlim(20, 20000); ax.set_ylim(-80, np.max(db_s) + 10)
TICKS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
ax.set_xticks(TICKS); ax.set_xticklabels([str(t) for t in TICKS])
[t.set_color("#ccc") for t in ax.get_xticklabels() + ax.get_yticklabels()]
ax.spines[:].set_color("#444"); ax.set_xlabel("Frequency (Hz)", color="#ccc")
ax.legend(facecolor="#222", labelcolor="#fff")
ax.set_title(f"Deep Analysis: {INPUT.name}", color="#fff")

out_chart = OUT_DIR / "Guitar_Jazz_v1.1_Analysis.png"
plt.savefig(str(out_chart), dpi=120, bbox_inches="tight", facecolor="#111")
plt.close()
print(f"\n[CHART] {out_chart}")
