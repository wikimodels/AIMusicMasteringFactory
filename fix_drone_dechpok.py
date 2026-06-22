"""
fix_drone_dechpok.py
====================
Удаляем суновские перкуссионные "чпоки" из дрон-трека.

📊 Параметры получены из analyze_drone_chpoks.py:
  - Найдено 54 события (delta=0.5)
  - Контраст чпок/дрон: +4.6 дБ (слабый → нужен HPSS margin=4)
  - Мусорные частоты: 1430 Hz | 3375-3422 Hz | 5390-5461 Hz

Стратегия (тройной удар):
  1. HPSS (librosa) — делит сигнал на гармоническую и транзиентную составляющие.
     Гармоника = дрон, гитара, воздух. Транзиенты = чпоки сифилиса Суно.
     Смешиваем обратно с атенюацией транзиентной части (0 = полное убийство, 0.05 = чуть оставляем).

  2. Multiband Suppressor — хирургически давим конкретные частотные кластеры
     где чпок громче дрона на +25 дБ: 1430 Hz, 3375-3422 Hz, 5390-5461 Hz.
     Работает через быстрый компрессор только внутри этих полос.

  3. Transient Gate — добивалка: ловим оставшиеся резкие импульсы и давим gain reduction.

Параметры тюнинга — в блоке НАСТРОЙКИ.
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
ROOT  = Path(__file__).parent
INPUT = ROOT / "Primitive Drone - Absolute Pure Solo.wav"
OUT_WAV = ROOT / "sound" / "wav_output" / "Primitive_Drone_DeChpok.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Primitive_Drone_DeChpok.mp3"

OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
#  НАСТРОЙКИ (крутим здесь)
# ══════════════════════════════════════════════════════════════

# ── Автоматически найдено analyze_drone_chpoks.py ──────────────────

# HPSS — ширина окон (контраст +4.6 дБ → нужен агрессивный margin)
HPSS_MARGIN = 4.0          # auto: слабый контраст требует 4+

# Сколько ОСТАВИТЬ от транзиентной составляющей
PERC_KEEP   = 0.03         # auto: 3% — чуть воздуха чтоб не убить атмосферу

# Multiband Suppressor — хирургические частоты где чпок +25 dB над дроном
MULTIBAND_ENABLED = True
# Кластеры: (центр_Гц, ширина_Гц, threshold_dB, ratio, attack_ms, release_ms)
MULTIBAND_CLUSTERS = [
    (1430,  200,  -32, 6.0, 1.0, 30.0),   # 1430 Hz  +26 dB над дроном
    (3398,  300,  -32, 6.0, 1.0, 30.0),   # 3375-3422 Hz кластер  +25 dB
    (5420,  200,  -32, 6.0, 1.0, 30.0),   # 5390-5461 Hz кластер  +25 dB
]

# Transient Gate
GATE_ENABLED = True
GATE_THRESH_DB = -13.8     # auto: уровень дрона -19.8 + 6 дБ запас
GATE_ONSET_SENSITIVITY = 0.55  # auto: delta=0.5 + небольшой запас
GATE_REDUCTION_DB = -12.0  # auto: мягко, т.к. контраст слабый
GATE_HOLD_MS = 30.0        # сколько мс держать gain reduction

# Финальный HP-фильтр (убираем инфразвук/сдвиги DC)
HP_CUTOFF_HZ = 25.0

# Внутренняя константа STFT
HOP_LENGTH = 512

# ══════════════════════════════════════════════════════════════
#  ЗАГРУЗКА
# ══════════════════════════════════════════════════════════════
print(f"[{INPUT.name}]  Загружаем...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1:
    data = np.stack([data, data], axis=1)
stereo = data.astype(np.float64)
print(f"  Длина: {stereo.shape[0]/fs:.1f} сек | SR: {fs} Гц | Каналов: {stereo.shape[1]}")

# ══════════════════════════════════════════════════════════════
#  ШАГ 1 — HPSS (Harmonic-Percussive Source Separation)
# ══════════════════════════════════════════════════════════════
print("\n── ШАГ 1: HPSS ──")
out = np.zeros_like(stereo)

for c in range(2):
    ch = stereo[:, c].astype(np.float32)

    # librosa.effects.hpss работает с float32 mono
    harmonic, percussive = librosa.effects.hpss(ch, margin=HPSS_MARGIN)

    # Собираем: гармоника на 100%, транзиенты на PERC_KEEP%
    out[:, c] = harmonic.astype(np.float64) + percussive.astype(np.float64) * PERC_KEEP

print(f"  ✅ HPSS: транзиенты подавлены (оставлено {PERC_KEEP*100:.0f}%)")
print(f"  ✅ Гармоника: {100}% (дрон, тянучки, воздух — целые)")

# ══════════════════════════════════════════════════════════════
#  ШАГ 2 — MULTIBAND SUPPRESSOR (хирургические частоты)
# ══════════════════════════════════════════════════════════════
if MULTIBAND_ENABLED:
    print("\n── ШАГ 2: MULTIBAND SUPPRESSOR ──")

    def compress_band(ch, fs, threshold_db, ratio, attack_ms, release_ms):
        """Быстрый одноканальный компрессор для полосы."""
        frame = max(1, int(attack_ms / 1000.0 * fs))
        rms = np.sqrt(np.convolve(ch**2, np.ones(frame) / frame, mode='same') + 1e-12)
        thr = 10 ** (threshold_db / 20.0)
        gain = np.where(rms > thr, (thr * (rms / thr) ** (1.0 / ratio)) / (rms + 1e-12), 1.0)
        att_c = np.exp(-1.0 / (fs * attack_ms / 1000.0))
        rel_c = np.exp(-1.0 / (fs * release_ms / 1000.0))
        gs = np.zeros_like(gain)
        g = 1.0
        for i in range(len(gain)):
            t = gain[i]
            g = att_c * g + (1 - att_c) * t if t < g else rel_c * g + (1 - rel_c) * t
            gs[i] = g
        return ch * gs

    out_mb = out.copy()
    for (center_hz, width_hz, thr_db, ratio, atk, rel) in MULTIBAND_CLUSTERS:
        lo = max(20.0, center_hz - width_hz / 2)
        hi = min(fs / 2 - 100, center_hz + width_hz / 2)
        sos_lp = sg.butter(4, hi, 'low',  fs=fs, output='sos')
        sos_hp = sg.butter(4, lo, 'high', fs=fs, output='sos')
        for c in range(2):
            full = out[:, c]
            # Выделяем только нужную полосу
            band = sg.sosfiltfilt(sos_lp, sg.sosfiltfilt(sos_hp, full))
            rest = full - band
            # Давим только внутри полосы
            band_fixed = compress_band(band, fs, thr_db, ratio, atk, rel)
            out_mb[:, c] = rest + band_fixed
        print(f"  ✅ {center_hz} Hz ±{width_hz//2} Hz: компрессия {ratio}:1 @ {thr_db} дБ")
    out = out_mb
else:
    print("\n── ШАГ 2: MULTIBAND — отключён ──")

# ══════════════════════════════════════════════════════════════
#  ШАГ 3 — TRANSIENT GATE (добивалка для упрямых чпоков)
# ══════════════════════════════════════════════════════════════
if GATE_ENABLED:
    print("\n── ШАГ 3: TRANSIENT GATE ──")

    # Mono mix для детектора
    mono = out.mean(axis=1).astype(np.float32)

    # Onset strength — насколько резко меняется спектр
    onset_env = librosa.onset.onset_strength(
        y=mono, sr=fs, hop_length=512, aggregate=np.median
    )

    # Нормализуем и находим "выбросы" выше порога чувствительности
    onset_norm = onset_env / (onset_env.max() + 1e-8)
    onset_peaks = librosa.util.peak_pick(
        onset_norm,
        pre_max=3, post_max=3, pre_avg=10, post_avg=10,
        delta=GATE_ONSET_SENSITIVITY, wait=10
    )

    print(f"  Найдено событий: {len(onset_peaks)}")

    # Строим gain envelope (в линейных единицах, размер = число фреймов onset)
    gain_env = np.ones(len(onset_env))
    reduction_linear = 10 ** (GATE_REDUCTION_DB / 20.0)
    hold_samples = int(GATE_HOLD_MS / 1000.0 * fs / HOP_LENGTH)  # в фреймах

    for peak_frame in onset_peaks:
        start_f = max(0, peak_frame - 1)
        end_f   = min(len(gain_env), peak_frame + hold_samples + 1)
        gain_env[start_f:end_f] = reduction_linear

    # Апсэмплим gain envelope к полному сэмплрейту
    # xp = позиции фреймов в сэмплах, fp = значения gain на этих позициях
    frame_centers = np.arange(len(onset_env)) * HOP_LENGTH
    gain_full = np.interp(
        np.arange(len(mono)),   # x: каждый сэмпл
        frame_centers,           # xp: позиции фреймов
        gain_env                 # fp: значения gain (должны совпадать по длине с frame_centers)
    )
    # Мягкое сглаживание gain (избегаем кликов от резкого gain change)
    smooth_frames = int(0.005 * fs)  # 5 мс
    if smooth_frames > 1:
        kernel = np.ones(smooth_frames) / smooth_frames
        gain_full = np.convolve(gain_full, kernel, mode='same')

    # Применяем к стерео
    for c in range(2):
        out[:, c] *= gain_full

    print(f"  ✅ Transient Gate: {len(onset_peaks)} событий подавлено на {abs(GATE_REDUCTION_DB):.0f} дБ")
else:
    print("\n── ШАГ 3: TRANSIENT GATE — отключён ──")

# ══════════════════════════════════════════════════════════════
#  ШАГ 4 — ВЫСОКОЧАСТОТНЫЙ ФИЛЬТР (DC / инфразвук)
# ══════════════════════════════════════════════════════════════
print(f"\n── ШАГ 4: HP фильтр {HP_CUTOFF_HZ} Гц ──")
sos_hp = sg.butter(2, HP_CUTOFF_HZ, 'high', fs=fs, output='sos')
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
print(f"  ✅ Инфразвук убран")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ (сохраняем оригинальный уровень)
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
    print("  ⚠️  ffmpeg не найден — MP3 пропущен. WAV сохранён.")

print("\n✅ ГОТОВО. Слушай и сравнивай с оригиналом.")
print(f"   Если чпоки ещё слышны — подними HPSS_MARGIN до 4–5 или снизь GATE_ONSET_SENSITIVITY.")
print(f"   Если пропал воздух/атмосфера — подними PERC_KEEP до 0.05–0.1.")
