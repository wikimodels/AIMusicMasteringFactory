"""
analyze_final_lofi.py
===============
Анализ финального файла "Felt_Piano_Jazz_v1.2_Lofi_Sleep.wav"
Проверяет:
1. Баланс частот (успешно ли работает Lofi-спад)
2. Резонансы (остались ли пики 1993 Гц и 993 Гц)
3. Динамику басов (как сработала компрессия)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "sound" / "wav_output" / "Felt_Piano_Jazz_v1.2_Lofi_Sleep.wav"
OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Анализ файла: {INPUT.name}")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
data = data.astype(np.float64)

N = len(data)
mono = (data[:, 0] + data[:, 1]) / 2.0

# ДИНАМИКА
peak_l = np.max(np.abs(data[:, 0]))
peak_r = np.max(np.abs(data[:, 1]))
rms_mono = np.sqrt(np.mean(mono**2))
def to_db(val): return 20 * np.log10(val + 1e-12)

print("\n── ДИНАМИКА ──────────────────────────────")
print(f"True Peak : L {to_db(peak_l):+.2f} dBFS | R {to_db(peak_r):+.2f} dBFS")
print(f"RMS Mono  : {to_db(rms_mono):+.2f} dBFS")
crest = to_db(max(peak_l, peak_r)) - to_db(rms_mono)
print(f"Crest Fact: {crest:.2f} dB (меньше = плотнее микс)")

# СПЕКТР И АНОМАЛИИ
print("\n── ЧАСТОТНЫЙ БАЛАНС ──────────────────────")
N_FFT = min(131072, N)
w = np.hanning(N_FFT)
sp = np.abs(np.fft.rfft(mono[:N_FFT] * w, n=N_FFT))
fr = np.fft.rfftfreq(N_FFT, 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
sm = 100
db_s = np.convolve(db, np.ones(sm)/sm, mode='same')

bands = {
    "Sub (20-60 Hz)": (20, 60),
    "Bass (60-250 Hz)": (60, 250),
    "Low Mid (250-500)": (250, 500),
    "Mid (500-2k)": (500, 2000),
    "High Mid (2k-6k)": (2000, 6000),
    "High (6k-12k)": (6000, 12000),
}
for name, (f1, f2) in bands.items():
    mask = (fr >= f1) & (fr <= f2)
    print(f"  {name:18s} : {np.mean(db_s[mask]):+.1f} dB")

# РЕЗОНАНСЫ
from scipy.ndimage import uniform_filter1d
baseline = uniform_filter1d(db_s, size=400)
peaks_diff = db_s - baseline

mask_res = (fr >= 100) & (fr <= 10000)
peaks_idx, _ = find_peaks(peaks_diff[mask_res], height=4.0, distance=100)
peaks_idx += np.where(mask_res)[0][0]

res_list = sorted([(fr[i], peaks_diff[i]) for i in peaks_idx], key=lambda x: -x[1])[:5]
print("\n── ОСТАТОЧНЫЕ РЕЗОНАНСЫ (>4 dB от фона) ──")
if not res_list:
    print("  ✅ Аномальных пиков нет. Микс ровный.")
else:
    for f0, amp in res_list:
        if f0 > 1900 and f0 < 2100:
            print(f"  ⚠ {f0:6.1f} Hz : +{amp:.1f} dB (Внимание: стеклянный звон всё ещё торчит?)")
        elif f0 > 950 and f0 < 1050:
            print(f"  ⚠ {f0:6.1f} Hz : +{amp:.1f} dB (Возможный звон на Си / B5)")
        else:
            print(f"    {f0:6.1f} Hz : +{amp:.1f} dB (Скорее всего, просто нота)")

# ГРАФИК
plt.figure(figsize=(12, 5), facecolor="#111")
ax = plt.subplot(111)
ax.set_facecolor("#222")
ax.grid(True, color="#444", lw=0.5)

ax.semilogx(fr, db_s, color="#34d399", lw=1.2, label="Lofi Sleep Spectrum")
ax.semilogx(fr, baseline, color="#f472b6", lw=1.0, linestyle="--", alpha=0.7, label="Baseline")
for f0, amp in res_list:
    ax.axvline(f0, color="#ef4444", lw=0.8, linestyle=":")
    ax.text(f0, np.interp(f0, fr, db_s) + 2, f"{f0:.0f}Hz", color="#ef4444", fontsize=8, ha='center')

ax.set_xlim(20, 20000)
ax.set_ylim(-80, np.max(db_s) + 10)
TICKS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
ax.set_xticks(TICKS)
ax.set_xticklabels([str(t) for t in TICKS])
[t.set_color("#ccc") for t in ax.get_xticklabels() + ax.get_yticklabels()]
ax.spines[:].set_color("#444")
ax.set_xlabel("Frequency (Hz)", color="#ccc")
ax.set_title(f"Final Health Analysis: {INPUT.name}", color="#fff")

out_chart = OUT_DIR / "Felt_Piano_Jazz_v1.2_Lofi_Health.png"
plt.savefig(str(out_chart), dpi=120, bbox_inches="tight", facecolor="#111")
plt.close()
print(f"\n[CHART] {out_chart}")
