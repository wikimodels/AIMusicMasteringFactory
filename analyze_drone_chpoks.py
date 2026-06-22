"""
analyze_drone_chpoks.py
=======================
Автоматический анализатор суновских чпоков.
Находит события, измеряет их частоты, амплитуды и характеристики —
и выдаёт готовые рекомендованные параметры для fix_drone_dechpok.py.

Вывод:
  - Список всех обнаруженных транзиентных событий (время, амплитуда)
  - Спектральный портрет чпока (в каких частотах живёт дрянь)
  - Спектр фоновой тишины (дрон) для сравнения
  - Рекомендованные значения HPSS_MARGIN, GATE_THRESH_DB, GATE_ONSET_SENSITIVITY, GATE_REDUCTION_DB
  - PNG с картинками для визуального контроля
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import librosa
import librosa.display
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

# ══════════════════════════════════════════════════════════════
#  ПУТИ
# ══════════════════════════════════════════════════════════════
ROOT  = Path(__file__).parent
INPUT = ROOT / "Primitive Drone - Absolute Pure Solo.wav"
OUT_REPORT = ROOT / "analysis" / "drone_chpok_report.png"
OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
#  ПАРАМЕТРЫ АНАЛИЗА
# ══════════════════════════════════════════════════════════════
HOP_LENGTH   = 512       # шаг STFT
N_FFT        = 2048      # окно STFT
# Диапазон порога детектора (будем перебирать, чтобы найти оптимум)
ONSET_DELTA_RANGE = [0.15, 0.2, 0.3, 0.4, 0.5]

# ══════════════════════════════════════════════════════════════
#  ЗАГРУЗКА
# ══════════════════════════════════════════════════════════════
print(f"[{INPUT.name}]  Загружаем...")
data, fs = sf.read(str(INPUT))
if data.ndim > 1:
    mono = data.mean(axis=1).astype(np.float32)
else:
    mono = data.astype(np.float32)
duration = len(mono) / fs
print(f"  Длина: {duration:.1f} сек | SR: {fs} Гц")

# ══════════════════════════════════════════════════════════════
#  ШАГ 1 — ONSET STRENGTH + ПОИСК ЧПОКОВ
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 1: Onset Strength ──")
onset_env = librosa.onset.onset_strength(
    y=mono, sr=fs, hop_length=HOP_LENGTH,
    aggregate=np.median, fmax=8000
)
times_frames = librosa.frames_to_time(np.arange(len(onset_env)), sr=fs, hop_length=HOP_LENGTH)

# Статистика onset среды
onset_mean  = onset_env.mean()
onset_std   = onset_env.std()
onset_max   = onset_env.max()
onset_norm  = onset_env / (onset_max + 1e-8)

print(f"  Onset mean: {onset_mean:.3f} | std: {onset_std:.3f} | max: {onset_max:.3f}")

# Перебираем delta и считаем сколько событий находит каждый порог
print("\n── ШАГ 2: Перебор порогов чувствительности ──")
results = {}
for delta in ONSET_DELTA_RANGE:
    peaks = librosa.util.peak_pick(
        onset_norm,
        pre_max=3, post_max=3, pre_avg=10, post_avg=10,
        delta=delta, wait=10
    )
    count = len(peaks)
    results[delta] = peaks
    peak_times = librosa.frames_to_time(peaks, sr=fs, hop_length=HOP_LENGTH)
    print(f"  delta={delta:.2f} → {count:3d} событий", end="")
    if count > 0:
        print(f"  | первые 5: {peak_times[:5].round(2).tolist()}")
    else:
        print()

# Автовыбор оптимального delta — хотим 5–50 событий (не шум, не пропуски)
best_delta = None
best_peaks = None
for delta in ONSET_DELTA_RANGE:
    peaks = results[delta]
    if 3 <= len(peaks) <= 60:
        best_delta = delta
        best_peaks = peaks
        break
if best_peaks is None:
    # Берём минимум событий из всех вариантов
    best_delta = max(ONSET_DELTA_RANGE)
    best_peaks = results[best_delta]

best_times = librosa.frames_to_time(best_peaks, sr=fs, hop_length=HOP_LENGTH)
print(f"\n  ✅ Автовыбор delta = {best_delta} → {len(best_peaks)} событий")

# ══════════════════════════════════════════════════════════════
#  ШАГ 3 — СПЕКТРАЛЬНЫЙ ПОРТРЕТ ЧПОКА vs ДРОНА
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 3: Спектральный анализ ──")

# STFT всего файла
D = librosa.stft(mono, n_fft=N_FFT, hop_length=HOP_LENGTH)
S_db = librosa.amplitude_to_db(np.abs(D), ref=np.max)
freqs = librosa.fft_frequencies(sr=fs, n_fft=N_FFT)

# Усредняем спектр в моменты чпоков
if len(best_peaks) > 0:
    chpok_spectra = []
    for pf in best_peaks:
        # берём ±2 фрейма вокруг пика
        start = max(0, pf - 2)
        end   = min(D.shape[1], pf + 3)
        chpok_spectra.append(np.abs(D[:, start:end]).mean(axis=1))
    chpok_avg_spectrum = np.array(chpok_spectra).mean(axis=0)
    chpok_avg_db = librosa.amplitude_to_db(chpok_avg_spectrum, ref=np.max(np.abs(D)))
else:
    chpok_avg_db = np.full(len(freqs), -80.0)

# Усредняем спектр в "тихих" фреймах (фоновый дрон)
# Тихие фреймы = там где onset_norm < 0.1
quiet_mask = onset_norm < 0.1
quiet_frames = np.where(quiet_mask)[0]
if len(quiet_frames) > 0:
    drone_spectra = np.abs(D[:, quiet_frames]).mean(axis=1)
    drone_avg_db  = librosa.amplitude_to_db(drone_spectra, ref=np.max(np.abs(D)))
else:
    drone_avg_db = np.full(len(freqs), -80.0)

# Разница: где чпок громче дрона
diff_db = chpok_avg_db - drone_avg_db

# Топ-5 частот где чпок лезет сильнее всего
top_freq_idx = np.argsort(diff_db)[::-1][:10]
top_freqs = freqs[top_freq_idx]
top_diffs = diff_db[top_freq_idx]

print("  Частоты где чпок громче дрона (топ-10):")
for f, d in zip(top_freqs, top_diffs):
    bar = "█" * int(max(0, d) / 2)
    print(f"    {f:7.1f} Hz  +{d:.1f} dB  {bar}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 4 — АМПЛИТУДНЫЙ АНАЛИЗ ЧПОКОВ
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 4: Амплитуды ──")

# RMS всего файла (в дБ)
frame_len = HOP_LENGTH
rms_frames = librosa.feature.rms(y=mono, frame_length=N_FFT, hop_length=HOP_LENGTH)[0]
rms_db_all = librosa.amplitude_to_db(rms_frames + 1e-8, ref=1.0)

# RMS в тихих фреймах (дрон)
drone_rms_db = rms_db_all[quiet_frames].mean() if len(quiet_frames) > 0 else -60.0

# RMS в пиках чпоков
if len(best_peaks) > 0:
    chpok_rms = [rms_db_all[min(p, len(rms_db_all)-1)] for p in best_peaks]
    chpok_rms_mean = np.mean(chpok_rms)
    chpok_rms_max  = np.max(chpok_rms)
else:
    chpok_rms_mean = drone_rms_db
    chpok_rms_max  = drone_rms_db

contrast_db = chpok_rms_mean - drone_rms_db
print(f"  Дрон (фон):      {drone_rms_db:.1f} дБ")
print(f"  Чпок (среднее):  {chpok_rms_mean:.1f} дБ")
print(f"  Чпок (макс):     {chpok_rms_max:.1f} дБ")
print(f"  Контраст:        {contrast_db:+.1f} дБ")

# ══════════════════════════════════════════════════════════════
#  ШАГ 5 — РЕКОМЕНДАЦИИ
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("  РЕКОМЕНДОВАННЫЕ ПАРАМЕТРЫ ДЛЯ fix_drone_dechpok.py")
print("="*60)

# HPSS_MARGIN: если контраст > 12 дБ — HPSS справится с margin=2,
# если слабый контраст — нужен margin повыше
if contrast_db > 15:
    rec_margin = 2.0
elif contrast_db > 8:
    rec_margin = 3.0
else:
    rec_margin = 4.0

# PERC_KEEP: если чпоков много или контраст слабый — ноль
rec_perc_keep = 0.0 if contrast_db > 6 else 0.03

# GATE_THRESHOLD: немного выше уровня дрона
rec_gate_thresh = round(drone_rms_db + 6.0, 1)

# GATE_ONSET_SENSITIVITY: если много событий — поднять порог
rec_sensitivity = round(min(0.7, best_delta + 0.05), 2)

# GATE_REDUCTION: зависит от контраста
rec_reduction = round(min(-12.0, -(contrast_db * 1.5)), 1)

print(f"""
  HPSS_MARGIN              = {rec_margin}
  PERC_KEEP                = {rec_perc_keep}
  GATE_THRESH_DB           = {rec_gate_thresh}
  GATE_ONSET_SENSITIVITY   = {rec_sensitivity}
  GATE_REDUCTION_DB        = {rec_reduction}

  Контраст чпок/дрон       = {contrast_db:+.1f} дБ
  Найдено событий          = {len(best_peaks)}
  Пиковые частоты мусора   = {', '.join(f'{f:.0f}Hz' for f in top_freqs[:5])}
""")

# ══════════════════════════════════════════════════════════════
#  ШАГ 6 — ВИЗУАЛЬНЫЙ ОТЧЁТ (PNG)
# ══════════════════════════════════════════════════════════════
print("── ШАГ 6: Рисуем отчёт ──")

fig = plt.figure(figsize=(18, 12), facecolor="#0d0d0d")
fig.suptitle(f"CHPOK ANALYSIS — {INPUT.name}", fontsize=14, color="#e0e0e0", y=0.98)
gs  = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.3)

ax_wave  = fig.add_subplot(gs[0, :])   # Waveform + события
ax_onset = fig.add_subplot(gs[1, 0])   # Onset envelope
ax_spec  = fig.add_subplot(gs[1, 1])   # Спектрограмма
ax_freq  = fig.add_subplot(gs[2, 0])   # Частотный портрет
ax_rms   = fig.add_subplot(gs[2, 1])   # RMS во времени

DARK_BG = "#0d0d0d"
GRID_C  = "#2a2a2a"
ACCENT  = "#ff4d4d"
DRONE_C = "#4da6ff"
TEXT_C  = "#cccccc"

for ax in [ax_wave, ax_onset, ax_spec, ax_freq, ax_rms]:
    ax.set_facecolor(DARK_BG)
    ax.tick_params(colors=TEXT_C, labelsize=8)
    ax.spines["bottom"].set_color(GRID_C)
    ax.spines["left"].set_color(GRID_C)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.label.set_color(TEXT_C)
    ax.xaxis.label.set_color(TEXT_C)
    ax.title.set_color(TEXT_C)

# --- Waveform ---
t_wave = np.linspace(0, duration, len(mono))
ax_wave.plot(t_wave, mono, color="#3a7bd5", lw=0.3, alpha=0.7)
for bt in best_times:
    ax_wave.axvline(x=bt, color=ACCENT, lw=0.8, alpha=0.8)
ax_wave.set_title(f"Waveform + Обнаруженные события ({len(best_peaks)} чпоков, delta={best_delta})")
ax_wave.set_xlabel("Время (сек)")
ax_wave.set_ylabel("Амплитуда")
ax_wave.set_xlim(0, duration)

# --- Onset Envelope ---
ax_onset.plot(times_frames, onset_norm, color="#f5a623", lw=0.8)
ax_onset.axhline(y=best_delta, color=ACCENT, lw=1.0, linestyle="--", label=f"threshold={best_delta}")
for bt in best_times:
    ax_onset.axvline(x=bt, color=ACCENT, lw=0.6, alpha=0.5)
ax_onset.set_title("Onset Strength (нормализованный)")
ax_onset.set_xlabel("Время (сек)")
ax_onset.set_ylabel("Сила атаки")
ax_onset.legend(fontsize=8, labelcolor=TEXT_C, facecolor=DARK_BG)
ax_onset.set_xlim(0, duration)

# --- Спектрограмма ---
img = librosa.display.specshow(
    S_db, sr=fs, hop_length=HOP_LENGTH, x_axis="time", y_axis="hz",
    cmap="magma", ax=ax_spec, fmax=8000
)
for bt in best_times:
    ax_spec.axvline(x=bt, color=ACCENT, lw=0.6, alpha=0.7)
ax_spec.set_title("Спектрограмма (0–8 kHz)")
ax_spec.set_ylim(0, 8000)
fig.colorbar(img, ax=ax_spec, format="%+2.0f dB")

# --- Частотный портрет ---
ax_freq.plot(freqs, drone_avg_db,  color=DRONE_C, lw=1.2, label="Дрон (фон)")
ax_freq.plot(freqs, chpok_avg_db,  color=ACCENT,  lw=1.2, label="Чпок (среднее)")
ax_freq.fill_between(freqs, drone_avg_db, chpok_avg_db,
                     where=(chpok_avg_db > drone_avg_db),
                     color=ACCENT, alpha=0.25, label="Мусор (превышение)")
ax_freq.set_title("Спектральный портрет: Чпок vs Дрон")
ax_freq.set_xlabel("Частота (Гц)")
ax_freq.set_ylabel("дБ")
ax_freq.set_xlim(20, fs // 2)
ax_freq.set_xscale("log")
ax_freq.legend(fontsize=8, labelcolor=TEXT_C, facecolor=DARK_BG)
ax_freq.grid(True, color=GRID_C, alpha=0.5)
# Аннотируем топ-3 частоты мусора
for i in range(min(3, len(top_freqs))):
    f, d = top_freqs[i], top_diffs[i]
    if d > 0:
        ax_freq.annotate(f"{f:.0f}Hz\n+{d:.1f}dB",
                         xy=(f, chpok_avg_db[top_freq_idx[i]]),
                         xytext=(f * 1.4, chpok_avg_db[top_freq_idx[i]] + 5),
                         fontsize=7, color=ACCENT,
                         arrowprops=dict(arrowstyle="->", color=ACCENT, lw=0.8))

# --- RMS во времени ---
rms_times = librosa.frames_to_time(np.arange(len(rms_db_all)), sr=fs, hop_length=HOP_LENGTH)
ax_rms.plot(rms_times, rms_db_all, color="#7ed321", lw=0.8)
ax_rms.axhline(y=drone_rms_db, color=DRONE_C, lw=1.0, linestyle="--", label=f"Дрон: {drone_rms_db:.1f} дБ")
ax_rms.axhline(y=rec_gate_thresh, color="#f5a623", lw=1.0, linestyle=":", label=f"Gate thresh: {rec_gate_thresh:.1f} дБ")
for bt in best_times:
    ax_rms.axvline(x=bt, color=ACCENT, lw=0.6, alpha=0.5)
ax_rms.set_title("RMS уровень во времени")
ax_rms.set_xlabel("Время (сек)")
ax_rms.set_ylabel("дБ")
ax_rms.legend(fontsize=8, labelcolor=TEXT_C, facecolor=DARK_BG)
ax_rms.set_xlim(0, duration)

# Рекомендации текстом на рисунке
rec_text = (
    f"РЕКОМЕНДАЦИИ:\n"
    f"  HPSS_MARGIN={rec_margin}  PERC_KEEP={rec_perc_keep}\n"
    f"  GATE_THRESH={rec_gate_thresh} дБ\n"
    f"  SENSITIVITY={rec_sensitivity}  REDUCTION={rec_reduction} дБ\n"
    f"  Событий: {len(best_peaks)}  Контраст: {contrast_db:+.1f} дБ"
)
fig.text(0.01, 0.01, rec_text, fontsize=9, color="#aaffaa",
         fontfamily="monospace", verticalalignment="bottom",
         bbox=dict(boxstyle="round,pad=0.4", facecolor="#1a1a1a", edgecolor="#444"))

plt.savefig(str(OUT_REPORT), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
print(f"  ✅ Отчёт сохранён: {OUT_REPORT}")
plt.close()

print("\n✅ АНАЛИЗ ЗАВЕРШЁН.")
print(f"   Скопируй параметры выше в НАСТРОЙКИ fix_drone_dechpok.py и запускай!")
