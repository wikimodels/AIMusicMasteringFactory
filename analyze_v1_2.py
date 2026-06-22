"""
analyze_v1_2.py
===============
Глубокий анализ файла "Felt Piano & Jazz v 1.2.wav"
Проверяет:
1. Спектральный баланс (наличие "песка", ямы)
2. Резонансы (узкие торчащие пики)
3. Динамику (RMS, True Peak, Crest Factor)
4. Стерео-корреляцию (моно-совместимость, перекосы фазы)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import find_peaks
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "Felt Piano & Jazz v 1.2.wav"
OUT_DIR = ROOT / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Анализ файла: {INPUT.name}")
try:
    data, fs = sf.read(str(INPUT))
except Exception as e:
    print(f"Ошибка чтения файла: {e}")
    sys.exit(1)

if data.ndim == 1:
    data = np.stack([data, data], axis=1)
data = data.astype(np.float64)

N = len(data)
mono = (data[:, 0] + data[:, 1]) / 2.0
print(f"Sample rate: {fs} Hz")
print(f"Duration   : {N/fs:.2f} s")

# ══════════════════════════════════════════════════════════════
#  ДИНАМИКА И УРОВНИ
# ══════════════════════════════════════════════════════════════
peak_l = np.max(np.abs(data[:, 0]))
peak_r = np.max(np.abs(data[:, 1]))
rms_l  = np.sqrt(np.mean(data[:, 0]**2))
rms_r  = np.sqrt(np.mean(data[:, 1]**2))
rms_mono = np.sqrt(np.mean(mono**2))

def to_db(val): return 20 * np.log10(val + 1e-12)

print("\n── ДИНАМИКА ──────────────────────────────")
print(f"True Peak : L {to_db(peak_l):+.2f} dBFS | R {to_db(peak_r):+.2f} dBFS")
print(f"RMS       : L {to_db(rms_l):+.2f} dBFS | R {to_db(rms_r):+.2f} dBFS | Mono {to_db(rms_mono):+.2f} dBFS")
crest = to_db(max(peak_l, peak_r)) - to_db(rms_mono)
print(f"Crest Fact: {crest:.2f} dB")

# ══════════════════════════════════════════════════════════════
#  СТЕРЕО ФАЗА
# ══════════════════════════════════════════════════════════════
W = fs // 2  # 500ms
n_w = N // W
corrs = []
for i in range(n_w):
    l_seg = data[i*W:(i+1)*W, 0]
    r_seg = data[i*W:(i+1)*W, 1]
    if np.std(l_seg) > 1e-5 and np.std(r_seg) > 1e-5:
        c = np.corrcoef(l_seg, r_seg)[0, 1]
        corrs.append(c)

mean_corr = np.mean(corrs) if corrs else 1.0
print("\n── СТЕРЕО ────────────────────────────────")
print(f"Mean Correlation: {mean_corr:+.2f} (-1=out_of_phase, 0=wide, +1=mono)")
if mean_corr < 0.2: print("  ⚠ ВНИМАНИЕ: Стерео слишком широкое, возможны проблемы в моно.")
elif mean_corr > 0.9: print("  ⚠ ВНИМАНИЕ: Трек почти моно.")
else: print("  ✅ Здоровая ширина стерео.")

# ══════════════════════════════════════════════════════════════
#  СПЕКТР
# ══════════════════════════════════════════════════════════════
print("\n── ЧАСТОТНЫЙ БАЛАНС ──────────────────────")
N_FFT = min(131072, N)
w = np.hanning(N_FFT)
sp = np.abs(np.fft.rfft(mono[:N_FFT] * w, n=N_FFT))
fr = np.fft.rfftfreq(N_FFT, 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
sm = 100
db_s = np.convolve(db, np.ones(sm)/sm, mode='same')

# Анализ диапазонов
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
    lvl = np.mean(db_s[mask])
    print(f"  {name:18s} : {lvl:+.1f} dB")

hf_level = np.mean(db_s[(fr >= 6000) & (fr <= 12000)])
if hf_level < -40:
    print("  ⚠ ВНИМАНИЕ: Сильный завал высоких частот (кастрация верха).")
elif hf_level > -25:
    print("  ⚠ ВНИМАНИЕ: Очень яркий верх (возможен песок/резкость).")
else:
    print("  ✅ Высокие частоты в норме.")

# ══════════════════════════════════════════════════════════════
#  ПОИСК РЕЗОНАНСОВ
# ══════════════════════════════════════════════════════════════
from scipy.ndimage import uniform_filter1d
baseline = uniform_filter1d(db_s, size=400)
peaks_diff = db_s - baseline

mask_res = (fr >= 100) & (fr <= 10000)
peaks_idx, _ = find_peaks(peaks_diff[mask_res], height=5.0, distance=100)
peaks_idx += np.where(mask_res)[0][0]

res_list = sorted([(fr[i], peaks_diff[i]) for i in peaks_idx], key=lambda x: -x[1])[:5]
print("\n── ПОДОЗРИТЕЛЬНЫЕ РЕЗОНАНСЫ (>5 dB от фона) ─")
if not res_list:
    print("  ✅ Резких резонансов не обнаружено.")
else:
    for f0, amp in res_list:
        print(f"  {f0:6.1f} Hz : +{amp:.1f} dB торчит")

# ══════════════════════════════════════════════════════════════
#  ГРАФИК
# ══════════════════════════════════════════════════════════════
plt.figure(figsize=(12, 6), facecolor="#111")
ax = plt.subplot(111)
ax.set_facecolor("#222")
ax.grid(True, color="#444", lw=0.5)

ax.semilogx(fr, db_s, color="#7ec8e3", lw=1.2, label="Spectrum")
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
ax.set_ylabel("dB", color="#ccc")
ax.set_title(f"Health Analysis: {INPUT.name}", color="#fff")
ax.legend(facecolor="#333", edgecolor="#555", labelcolor="#fff")

out_chart = OUT_DIR / "Felt_Piano_Jazz_v1.2_Health.png"
plt.savefig(str(out_chart), dpi=120, bbox_inches="tight", facecolor="#111")
plt.close()
print(f"\n[CHART] {out_chart}")
