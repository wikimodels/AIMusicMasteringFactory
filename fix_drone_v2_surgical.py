"""
fix_drone_v2_surgical.py
========================
Версия 2 — ХИРУРГИЧЕСКАЯ. Без HPSS.

Проблема v1: HPSS не различает "атаку щипка гитары" и "чпок Суно" —
оба выглядят как транзиенты. Результат — унитаз.

Новая логика:
  1. Находим все onset-события (атаки)
  2. Для каждого события смотрим СПЕКТРАЛЬНЫЙ ЦЕНТРОИД:
       - Гитарный щипок → центроид НИЗКИЙ (фундаментал + 2-3 гармоники, 200-1500 Hz)
       - Суновский чпок → центроид ВЫСОКИЙ (широкополосный шум, 2000+ Hz)
  3. Классифицированные как "чпок" кадры заменяем МЕДИАНОЙ соседних кадров
     (спектральная интерполяция — берём "как было бы без чпока")
  4. Гитарные щипки — не трогаем вообще!

Параметры в блоке НАСТРОЙКИ.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import librosa
import soundfile as sf
import scipy.signal as sg
import subprocess
from pathlib import Path

# ══════════════════════════════════════════════════════════════
#  ПУТИ
# ══════════════════════════════════════════════════════════════
ROOT    = Path(__file__).parent
INPUT   = ROOT / "Primitive Drone - Absolute Pure Solo.wav"
OUT_WAV = ROOT / "sound" / "wav_output" / "Primitive_Drone_v2_Surgical.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Primitive_Drone_v2_Surgical.mp3"
OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════

# Детектор событий
ONSET_DELTA         = 0.5    # из анализатора: 54 события
ONSET_WAIT          = 10     # минимальный интервал между пиками (фреймы)

# Классификатор: граница центроида гитара/чпок
# Гитарный щипок дрона — ожидаем центроид < 1800 Hz
# Суновский чпок — ожидаем центроид > 1800 Hz
CENTROID_THRESH_HZ  = 1800.0

# Ширина окна для спектральной замены (кадры вокруг чпока)
REPAIR_HALF_WIDTH   = 3      # ±3 фрейма (~32 мс при hop=512/48kHz)
# Сколько соседних кадров брать для медианы (с каждой стороны)
MEDIAN_CONTEXT      = 15

# Мягкое смешивание: 0.0 = полная замена медианой, 1.0 = не трогать
# 0.05 = 95% медианы + 5% оригинала (убирает "резкий шов")
BLEND_ORIGINAL      = 0.05

# HP-фильтр финальный
HP_CUTOFF_HZ        = 30.0

# STFT параметры
N_FFT               = 2048
HOP_LENGTH          = 512

# ══════════════════════════════════════════════════════════════
#  ЗАГРУЗКА
# ══════════════════════════════════════════════════════════════
print(f"[{INPUT.name}]  Загружаем...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1:
    data = np.stack([data, data], axis=1)
stereo = data.astype(np.float64)
print(f"  Длина: {stereo.shape[0]/fs:.1f} сек | SR: {fs} Гц | Каналов: {stereo.shape[1]}")

# Mono для анализа
mono = stereo.mean(axis=1).astype(np.float32)

# ══════════════════════════════════════════════════════════════
#  ШАГ 1 — STFT
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 1: STFT ──")
# Считаем STFT для обоих каналов
D_L = librosa.stft(stereo[:, 0].astype(np.float32), n_fft=N_FFT, hop_length=HOP_LENGTH)
D_R = librosa.stft(stereo[:, 1].astype(np.float32), n_fft=N_FFT, hop_length=HOP_LENGTH)
D_mono = librosa.stft(mono, n_fft=N_FFT, hop_length=HOP_LENGTH)

freqs = librosa.fft_frequencies(sr=fs, n_fft=N_FFT)
n_frames = D_L.shape[1]
print(f"  Фреймов: {n_frames} | Бины: {len(freqs)}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 2 — ONSET DETECTION
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 2: Onset Detection ──")
onset_env = librosa.onset.onset_strength(
    y=mono, sr=fs, hop_length=HOP_LENGTH, aggregate=np.median, fmax=8000
)
onset_norm = onset_env / (onset_env.max() + 1e-8)
onset_peaks = librosa.util.peak_pick(
    onset_norm,
    pre_max=3, post_max=3, pre_avg=10, post_avg=10,
    delta=ONSET_DELTA, wait=ONSET_WAIT
)
print(f"  Найдено событий: {len(onset_peaks)}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 3 — КЛАССИФИКАЦИЯ: гитара vs чпок
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 3: Классификация событий ──")

# Спектральный центроид для каждого фрейма
mag_mono = np.abs(D_mono)
# centroid[f] = sum(freq * mag) / sum(mag)  для каждого фрейма
centroid = (freqs[:, np.newaxis] * mag_mono).sum(axis=0) / (mag_mono.sum(axis=0) + 1e-8)

guitar_events = []
chpok_events  = []

for peak_f in onset_peaks:
    c = centroid[peak_f]
    if c < CENTROID_THRESH_HZ:
        guitar_events.append(peak_f)
    else:
        chpok_events.append(peak_f)

print(f"  🎸 Гитарных щипков:     {len(guitar_events)}")
print(f"  💩 Суновских чпоков:    {len(chpok_events)}")
if chpok_events:
    chpok_times = librosa.frames_to_time(chpok_events, sr=fs, hop_length=HOP_LENGTH)
    print(f"  Чпоки на: {chpok_times.round(2).tolist()}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 4 — СПЕКТРАЛЬНЫЙ РЕМОНТ ЧПОКОВ
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 4: Спектральный ремонт ──")

D_L_fixed = D_L.copy()
D_R_fixed = D_R.copy()

repaired = 0
for peak_f in chpok_events:
    # Диапазон кадров под замену
    f_start = max(0, peak_f - REPAIR_HALF_WIDTH)
    f_end   = min(n_frames, peak_f + REPAIR_HALF_WIDTH + 1)

    # Контекстные кадры для медианы (не включаем сам чпок)
    ctx_left_start  = max(0, f_start - MEDIAN_CONTEXT)
    ctx_left_end    = f_start
    ctx_right_start = f_end
    ctx_right_end   = min(n_frames, f_end + MEDIAN_CONTEXT)

    ctx_frames_L = []
    ctx_frames_R = []

    if ctx_left_end > ctx_left_start:
        ctx_frames_L.append(D_L[:, ctx_left_start:ctx_left_end])
        ctx_frames_R.append(D_R[:, ctx_left_start:ctx_left_end])
    if ctx_right_end > ctx_right_start:
        ctx_frames_L.append(D_L[:, ctx_right_start:ctx_right_end])
        ctx_frames_R.append(D_R[:, ctx_right_start:ctx_right_end])

    if not ctx_frames_L:
        continue  # нет контекста — пропускаем

    ctx_L = np.concatenate(ctx_frames_L, axis=1)
    ctx_R = np.concatenate(ctx_frames_R, axis=1)

    # Медиана по амплитуде + средняя фаза контекста
    median_mag_L = np.median(np.abs(ctx_L), axis=1, keepdims=True)
    median_mag_R = np.median(np.abs(ctx_R), axis=1, keepdims=True)
    mean_phase_L = np.angle(ctx_L.mean(axis=1, keepdims=True))
    mean_phase_R = np.angle(ctx_R.mean(axis=1, keepdims=True))

    # Реконструируем "чистый" кадр
    repair_L = median_mag_L * np.exp(1j * mean_phase_L)
    repair_R = median_mag_R * np.exp(1j * mean_phase_R)

    # Вставляем с мягким смешиванием
    for f in range(f_start, f_end):
        D_L_fixed[:, f] = BLEND_ORIGINAL * D_L[:, f] + (1 - BLEND_ORIGINAL) * repair_L[:, 0]
        D_R_fixed[:, f] = BLEND_ORIGINAL * D_R[:, f] + (1 - BLEND_ORIGINAL) * repair_R[:, 0]
    repaired += 1

print(f"  ✅ Отремонтировано {repaired} чпоков (спектральная интерполяция)")
print(f"  ✅ Гитарных щипков не тронуто: {len(guitar_events)}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 5 — ISTFT (обратное преобразование)
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 5: ISTFT ──")
out_L = librosa.istft(D_L_fixed, hop_length=HOP_LENGTH, length=stereo.shape[0])
out_R = librosa.istft(D_R_fixed, hop_length=HOP_LENGTH, length=stereo.shape[0])
out = np.stack([out_L, out_R], axis=1).astype(np.float64)
print(f"  Длина восстановлена: {out.shape[0]/fs:.1f} сек")

# ══════════════════════════════════════════════════════════════
#  ШАГ 6 — HP-ФИЛЬТР (DC)
# ══════════════════════════════════════════════════════════════
sos_hp = sg.butter(2, HP_CUTOFF_HZ, 'high', fs=fs, output='sos')
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
orig_peak = np.max(np.abs(stereo))
curr_peak = np.max(np.abs(out))
if curr_peak > 1e-8:
    out *= (orig_peak / curr_peak)
print(f"\n  ✅ Нормализация: пик {20*np.log10(orig_peak):.1f} дБFS сохранён")

# ══════════════════════════════════════════════════════════════
#  СОХРАНЕНИЕ
# ══════════════════════════════════════════════════════════════
print(f"\n── СОХРАНЕНИЕ ──")
sf.write(str(OUT_WAV), out.astype(np.float32), fs, subtype="PCM_24")
print(f"  ✅ WAV: {OUT_WAV}")

try:
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(OUT_WAV), "-b:a", "320k", str(OUT_MP3)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print(f"  ✅ MP3: {OUT_MP3}")
except Exception:
    print("  ⚠️  ffmpeg не найден — MP3 пропущен.")

print("\n✅ ГОТОВО.")
print(f"   Гитарных щипков сохранено:  {len(guitar_events)}")
print(f"   Чпоков отремонтировано:     {repaired}")
print(f"\n   Если чпоки ещё слышны — снизь CENTROID_THRESH_HZ до 1400-1500")
print(f"   Если гитара стала 'пластиковой' — подними BLEND_ORIGINAL до 0.1-0.2")
