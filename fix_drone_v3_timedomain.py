"""
fix_drone_v3_timedomain.py
==========================
Версия 3 — ВРЕМЕННОЙ ДОМЕН. Никакого STFT, никакого эха.

Проблемы v1/v2:
  v1: HPSS убил атаки гитары (унитаз)
  v2: STFT-замена = фазовый артефакт = приглушённое эхо

Новая логика:
  1. Разделяем сигнал на НЧ (<SPLIT_HZ) и ВЧ (>SPLIT_HZ) через butter-фильтр
  2. В ВЧ-канале ищем всплески RMS — это и есть чпоки
     (гитара на высоких частотах почти тихая, чпок — шумный)
  3. На найденных позициях применяем косинусный gate прямо к ОРИГИНАЛЬНОМУ сигналу
  4. Косинус — плавный, без щелчков, без фазовых проблем

Результат: гитара не тронута, чпоки задавлены без артефактов.
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
import subprocess
from pathlib import Path

# ══════════════════════════════════════════════════════════════
#  ПУТИ
# ══════════════════════════════════════════════════════════════
ROOT    = Path(__file__).parent
INPUT   = ROOT / "Primitive Drone - Absolute Pure Solo.wav"
OUT_WAV = ROOT / "sound" / "wav_output" / "Primitive_Drone_v3_TimeDomain.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Primitive_Drone_v3_TimeDomain.mp3"
OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ
# ══════════════════════════════════════════════════════════════

# Частота раздела: выше этого — ВЧ-канал для детектора чпоков
# Гитарные атаки щипка тихие выше 2000 Гц, чпоки — широкополосные
SPLIT_HZ = 3500.0

# Окно RMS для детектора (мс)
RMS_WINDOW_MS = 8.0

# Порог: чпок = ВЧ-RMS превышает фоновое значение в N раз
# (чем меньше — тем чувствительнее, тем больше ловим)
RMS_THRESHOLD_MULT = 5.0

# Ширина cosine-gate вокруг чпока (мс с каждой стороны)
# = половина длины окна подавления
GATE_HALF_MS = 35.0

# Минимальный интервал между двумя чпоками (мс) — чтобы не склеивать
MIN_GAP_MS = 50.0

# Максимальная длительность чпока (мс) — всё длиннее = гитара/дрон, пропускаем
MAX_EVENT_MS = 150.0

# Насколько давим чпок (0.0 = тишина, 1.0 = не трогаем)
# 0.05 = -26 дБ. Не до нуля — чтобы не было "дыры" в дроне
GATE_FLOOR = 0.05

# Финальный HP-фильтр
HP_CUTOFF_HZ = 25.0

# ══════════════════════════════════════════════════════════════
#  ЗАГРУЗКА
# ══════════════════════════════════════════════════════════════
print(f"[{INPUT.name}]  Загружаем...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1:
    data = np.stack([data, data], axis=1)
stereo = data.astype(np.float64)
n_samples = stereo.shape[0]
print(f"  Длина: {n_samples/fs:.1f} сек | SR: {fs} Гц | Каналов: {stereo.shape[1]}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 1 — ВЧ-КАНАЛ ДЛЯ ДЕТЕКТОРА
# ══════════════════════════════════════════════════════════════
print(f"\n── ШАГ 1: Выделение ВЧ-канала (>{SPLIT_HZ} Гц) ──")
sos_hp = sg.butter(4, SPLIT_HZ, 'high', fs=fs, output='sos')
mono = stereo.mean(axis=1)
hf_mono = sg.sosfiltfilt(sos_hp, mono)

# ══════════════════════════════════════════════════════════════
#  ШАГ 2 — RMS-ДЕТЕКТОР ЧПОКОВ
# ══════════════════════════════════════════════════════════════
print(f"\n── ШАГ 2: RMS-детектор чпоков ──")
rms_win = max(1, int(RMS_WINDOW_MS / 1000.0 * fs))

# Скользящее RMS по ВЧ-каналу
hf_sq = hf_mono ** 2
rms_env = np.sqrt(np.convolve(hf_sq, np.ones(rms_win) / rms_win, mode='same') + 1e-12)

# Фоновый уровень ВЧ = медиана (не mean, чтобы чпоки не задирали фон)
hf_floor = np.median(rms_env)
print(f"  ВЧ-фон (медиана): {20*np.log10(hf_floor):.1f} дБ")

threshold = hf_floor * RMS_THRESHOLD_MULT
print(f"  Порог (x{RMS_THRESHOLD_MULT}):     {20*np.log10(threshold):.1f} дБ")

# Бинарная маска: где ВЧ-энергия превышает порог
over_thresh = (rms_env > threshold).astype(np.float64)

# Находим границы событий (переходы 0→1 и 1→0)
min_gap = int(MIN_GAP_MS / 1000.0 * fs)
events = []
in_event = False
evt_start = 0
silence_count = 0

for i in range(n_samples):
    if not in_event:
        if over_thresh[i]:
            in_event = True
            evt_start = i
            silence_count = 0
    else:
        if not over_thresh[i]:
            silence_count += 1
            if silence_count >= min_gap:
                events.append((evt_start, i - silence_count))
                in_event = False
                silence_count = 0
        else:
            silence_count = 0

if in_event:
    events.append((evt_start, n_samples - 1))

# Фильтр по длительности: события > MAX_EVENT_MS — это гитара/дрон, не чпок
max_evt_samples = int(MAX_EVENT_MS / 1000.0 * fs)
events_raw = events
events = [(s, e) for (s, e) in events_raw if (e - s) <= max_evt_samples]
print(f"  Всего найдено: {len(events_raw)} | После фильтра <{MAX_EVENT_MS:.0f}мс: {len(events)}")
for s, e in events[:15]:
    print(f"    {s/fs:.3f}s – {e/fs:.3f}s  ({(e-s)/fs*1000:.0f} мс)")
if len(events) > 15:
    print(f"    ... и ещё {len(events)-15}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 3 — COSINE GATE
# ══════════════════════════════════════════════════════════════
print(f"\n── ШАГ 3: Cosine Gate ──")

gate_half = int(GATE_HALF_MS / 1000.0 * fs)
gain_env = np.ones(n_samples)

suppressed = 0
for (s, e) in events:
    # Расширяем окно с запасом
    gs = max(0, s - gate_half)
    ge = min(n_samples, e + gate_half)
    win_len = ge - gs

    # Косинусное окно: плавно опускаемся до GATE_FLOOR и обратно
    # 1.0 → GATE_FLOOR → 1.0
    cos_win = np.ones(win_len)
    fade_len = min(gate_half, win_len // 2)
    if fade_len > 1:
        fade_up   = 0.5 * (1 - np.cos(np.linspace(0, np.pi, fade_len)))  # 0→1
        fade_down = 0.5 * (1 - np.cos(np.linspace(np.pi, 2*np.pi, fade_len)))  # 1→0

        # fade_down: уходим к GATE_FLOOR
        fade_down_scaled = 1.0 - (1.0 - GATE_FLOOR) * fade_down
        # средняя часть: держим на GATE_FLOOR
        # fade_up: возвращаемся к 1.0
        fade_up_scaled   = GATE_FLOOR + (1.0 - GATE_FLOOR) * fade_up

        cos_win[:fade_len] = fade_down_scaled
        cos_win[fade_len:-fade_len] = GATE_FLOOR
        cos_win[-fade_len:] = fade_up_scaled

    gain_env[gs:ge] = np.minimum(gain_env[gs:ge], cos_win)
    suppressed += 1

print(f"  ✅ Подавлено событий: {suppressed}")
print(f"  ✅ GATE_FLOOR: {20*np.log10(GATE_FLOOR):.1f} дБ ({GATE_FLOOR*100:.0f}% амплитуды)")

# ══════════════════════════════════════════════════════════════
#  ШАГ 4 — ПРИМЕНЯЕМ GAIN
# ══════════════════════════════════════════════════════════════
out = stereo.copy()
for c in range(2):
    out[:, c] *= gain_env

# ══════════════════════════════════════════════════════════════
#  ШАГ 5 — HP-ФИЛЬТР
# ══════════════════════════════════════════════════════════════
sos_hp_final = sg.butter(2, HP_CUTOFF_HZ, 'high', fs=fs, output='sos')
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_hp_final, out[:, c])

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
orig_peak = np.max(np.abs(stereo))
curr_peak = np.max(np.abs(out))
if curr_peak > 1e-8:
    out *= (orig_peak / curr_peak)
print(f"\n  ✅ Нормализация: пик {20*np.log10(orig_peak):.1f} дБFS")

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
    print("  ⚠️  ffmpeg не найден — WAV сохранён.")

print(f"\n✅ ГОТОВО. Проверь {OUT_WAV.name}")
print(f"\n   Если чпок ещё слышен:")
print(f"     → снизь RMS_THRESHOLD_MULT до 3.0–4.0")
print(f"   Если гитарные ноты гасятся (провалы):")
print(f"     → подними RMS_THRESHOLD_MULT до 7.0–10.0")
print(f"     → или подними SPLIT_HZ до 4000–5000")
print(f"   Если событий >50: подними MAX_EVENT_MS или SPLIT_HZ")
