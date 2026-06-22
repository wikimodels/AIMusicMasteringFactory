"""
diagnose_segment.py
===================
Зум на конкретный проблемный момент (1.04-1.10 сек).
Показывает спектр в этом месте vs "чистый" соседний участок.
Помогает понять ЧТО именно там за чпок и как его поймать.
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import scipy.signal as sg
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT  = Path(__file__).parent
INPUT = ROOT / "Primitive Drone - Absolute Pure Solo.wav"
OUT   = ROOT / "analysis" / "diagnose_segment.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

# ── Что анализируем ──────────────────────────────────────────
# Меняй эти временные метки под любой подозрительный момент
CHPOK_START = 1.00   # секунда начала чпока
CHPOK_END   = 1.12   # секунда конца чпока
CLEAN_START = 0.50   # "чистый" соседний участок для сравнения
CLEAN_END   = 0.62
# ─────────────────────────────────────────────────────────────

data, fs = sf.read(str(INPUT))
if data.ndim > 1:
    mono = data.mean(axis=1)
else:
    mono = data.astype(np.float64)

print(f"Длина: {len(mono)/fs:.1f} сек | SR: {fs} Гц")

# Извлекаем сегменты
seg_chpok = mono[int(CHPOK_START*fs):int(CHPOK_END*fs)]
seg_clean = mono[int(CLEAN_START*fs):int(CLEAN_END*fs)]

# Спектры (Welch — усреднённый)
f_c, Pxx_c = sg.welch(seg_chpok, fs=fs, nperseg=1024)
f_k, Pxx_k = sg.welch(seg_clean,  fs=fs, nperseg=1024)

Pxx_c_db = 10 * np.log10(Pxx_c + 1e-12)
Pxx_k_db = 10 * np.log10(Pxx_k + 1e-12)
diff_db   = Pxx_c_db - Pxx_k_db

# Находим топ-10 частот где чпок сегмент громче чистого
top_idx = np.argsort(diff_db)[::-1][:10]

print(f"\n── Сравнение {CHPOK_START:.2f}-{CHPOK_END:.2f}s vs {CLEAN_START:.2f}-{CLEAN_END:.2f}s ──")
print(f"  Топ частоты где проблемный участок громче:")
for i in top_idx:
    bar = "█" * int(max(0, diff_db[i]) / 2)
    print(f"    {f_c[i]:7.1f} Hz  {diff_db[i]:+.1f} dB  {bar}")

# Спектральный центроид обоих сегментов
centroid_c = (f_c * Pxx_c).sum() / (Pxx_c.sum() + 1e-8)
centroid_k = (f_k * Pxx_k).sum() / (Pxx_k.sum() + 1e-8)
print(f"\n  Центроид чпока:     {centroid_c:.0f} Hz")
print(f"  Центроид чистого:   {centroid_k:.0f} Hz")
print(f"  Разница:            {centroid_c - centroid_k:+.0f} Hz")

# RMS сравнение по полосам
bands = [(0,200,"суб"), (200,800,"низ"), (800,2500,"мид"), (2500,6000,"верх"), (6000,22000,"воздух")]
print(f"\n  RMS по полосам (чпок vs чистый):")
for (lo, hi, name) in bands:
    mask = (f_c >= lo) & (f_c < hi)
    rms_c = 10 * np.log10(Pxx_c[mask].mean() + 1e-12)
    rms_k = 10 * np.log10(Pxx_k[mask].mean() + 1e-12)
    print(f"    {name:8s} ({lo:5d}-{hi:5d} Hz):  чпок {rms_c:+.1f} | чистый {rms_k:+.1f} | Δ {rms_c-rms_k:+.1f} dB")

# Waveform осцилограммы обоих сегментов
t_c = np.linspace(CHPOK_START, CHPOK_END, len(seg_chpok))
t_k = np.linspace(CLEAN_START, CLEAN_END, len(seg_clean))

# ── PLOT ──────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 9), facecolor="#0d0d0d")
fig.suptitle(f"DIAGNOSE: чпок {CHPOK_START:.2f}–{CHPOK_END:.2f}s  vs  чистый {CLEAN_START:.2f}–{CLEAN_END:.2f}s",
             color="#e0e0e0", fontsize=13)

DARK = "#0d0d0d"; GRID = "#222"; TC = "#ccc"
for ax in axes.flat:
    ax.set_facecolor(DARK)
    ax.tick_params(colors=TC, labelsize=8)
    for sp in ax.spines.values(): sp.set_color(GRID)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.title.set_color(TC); ax.xaxis.label.set_color(TC); ax.yaxis.label.set_color(TC)

# Waveform - чпок
axes[0,0].plot(t_c, seg_chpok, color="#ff4d4d", lw=0.7)
axes[0,0].set_title(f"Waveform: ЧПОК ({CHPOK_START:.2f}–{CHPOK_END:.2f}s)")
axes[0,0].set_xlabel("Время (сек)"); axes[0,0].set_ylabel("Амплитуда")

# Waveform - чистый
axes[0,1].plot(t_k, seg_clean, color="#4da6ff", lw=0.7)
axes[0,1].set_title(f"Waveform: ЧИСТЫЙ ({CLEAN_START:.2f}–{CLEAN_END:.2f}s)")
axes[0,1].set_xlabel("Время (сек)"); axes[0,1].set_ylabel("Амплитуда")

# Спектры
axes[1,0].plot(f_k, Pxx_k_db, color="#4da6ff", lw=1.2, label="Чистый", alpha=0.8)
axes[1,0].plot(f_c, Pxx_c_db, color="#ff4d4d", lw=1.2, label="Чпок", alpha=0.9)
axes[1,0].set_title("Спектры (Welch)")
axes[1,0].set_xlabel("Частота (Гц)"); axes[1,0].set_ylabel("дБ")
axes[1,0].set_xscale("log"); axes[1,0].set_xlim(20, fs//2)
axes[1,0].legend(fontsize=8, labelcolor=TC, facecolor=DARK)
axes[1,0].grid(True, color=GRID, alpha=0.5)

# Разница спектров
axes[1,1].plot(f_c, diff_db, color="#f5a623", lw=1.2)
axes[1,1].axhline(0, color="#555", lw=0.8)
axes[1,1].fill_between(f_c, 0, diff_db, where=(diff_db > 0), color="#ff4d4d", alpha=0.3, label="+дБ = чпок громче")
axes[1,1].fill_between(f_c, 0, diff_db, where=(diff_db < 0), color="#4da6ff", alpha=0.3, label="+дБ = чистый громче")
# Аннотируем топ-3
for i in top_idx[:3]:
    if diff_db[i] > 0:
        axes[1,1].annotate(f"{f_c[i]:.0f}Hz\n{diff_db[i]:+.1f}dB",
                           xy=(f_c[i], diff_db[i]),
                           xytext=(f_c[i]*1.5, diff_db[i]+2),
                           fontsize=7, color="#ff4d4d",
                           arrowprops=dict(arrowstyle="->", color="#ff4d4d", lw=0.7))
axes[1,1].set_title("Разница спектров (Чпок − Чистый)")
axes[1,1].set_xlabel("Частота (Гц)"); axes[1,1].set_ylabel("ΔдБ")
axes[1,1].set_xscale("log"); axes[1,1].set_xlim(20, fs//2)
axes[1,1].legend(fontsize=8, labelcolor=TC, facecolor=DARK)
axes[1,1].grid(True, color=GRID, alpha=0.5)

plt.tight_layout()
plt.savefig(str(OUT), dpi=150, bbox_inches="tight", facecolor=DARK)
plt.close()
print(f"\n✅ График сохранён: {OUT}")
print(f"\n   Меняй CHPOK_START/CHPOK_END под любой подозрительный момент!")
