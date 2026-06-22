"""
fix_guitar_jazz_v2_clean.py
===========================
Оставляем гитару в оригинальном (чистом) виде.
Смягчаем ТОЛЬКО пластиковые щетки с помощью De-Esser (быстрой многополосной компрессии на высоких частотах).
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "Guitar Jazz" / "Guitar & Jazz v 1.1.wav"
OUT_WAV = ROOT / "sound" / "wav_output" / "Guitar_Jazz_v1.1_Clean_BrushesFixed.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Guitar_Jazz_v1.1_Clean_BrushesFixed.mp3"

OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

print(f"[{INPUT.name}] Запуск прозрачного мастеринга...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

# ══════════════════════════════════════════════════════════════
#  ФУНКЦИИ
# ══════════════════════════════════════════════════════════════
def lr2_lp(fc, fs): return np.vstack([sg.butter(2, fc, 'low', fs=fs, output='sos')] * 2)
def lr2_hp(fc, fs): return np.vstack([sg.butter(2, fc, 'high', fs=fs, output='sos')] * 2)

def compress_band(ch, fs, threshold_db, ratio, attack_ms, release_ms, makeup_db=0.0):
    frame = max(1, int(attack_ms/1000.0*fs))
    rms = np.sqrt(np.convolve(ch**2, np.ones(frame)/frame, mode='same') + 1e-12)
    thr, mkup = 10**(threshold_db/20.0), 10**(makeup_db/20.0)
    gain = np.where(rms > thr, (thr*(rms/thr)**(1.0/ratio))/(rms+1e-12), 1.0)
    att_c, rel_c = np.exp(-1.0/(fs*attack_ms/1000.0)), np.exp(-1.0/(fs*release_ms/1000.0))
    gs = np.zeros_like(gain); g = 1.0
    for i in range(len(gain)):
        t = gain[i]
        g = att_c*g+(1-att_c)*t if t < g else rel_c*g+(1-rel_c)*t
        gs[i] = g
    return ch * gs * mkup

# ══════════════════════════════════════════════════════════════
#  АЛГОРИТМ
# ══════════════════════════════════════════════════════════════
# 1. Убираем саб-грязь (только инфразвук, никак не влияет на гитару)
sos_hp = sg.butter(2, 30.0, 'high', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
print("  ✅ Оригинальный эквалайзер сохранён полностью (чистота оригинала оставлена).")

# 2. МЯГКИЕ ЩЕТКИ (High-Frequency De-Esser)
print("── MULTIBAND BRUSH SOFTENER ──")
# Разделяем сигнал на две полосы: ниже 3500 Гц (Сама гитара) и выше 3500 Гц (Щетки и "пластик")
X1 = 3500.0
sos_lp1, sos_hp1 = lr2_lp(X1,fs), lr2_hp(X1,fs)

out_mb = np.zeros_like(out)
for c in range(2):
    ch = out[:, c]
    low_band = sg.sosfiltfilt(sos_lp1, ch)  # Тело гитары
    high_band = sg.sosfiltfilt(sos_hp1, ch) # Верха, где "пластик"
    
    # Жестко и быстро сжимаем ТОЛЬКО ВЕРХА. 
    # Когда щетка делает резкий пластиковый "чшшш", компрессор мгновенно его плющит.
    high_compressed = compress_band(high_band, fs, threshold_db=-28, ratio=4.0, attack_ms=1.5, release_ms=40.0)
    
    # Склеиваем обратно
    out_mb[:, c] = low_band + high_compressed

out = out_mb
print("  ✅ Пластик на высоких частотах смят (Fast Attack Compression). Гитара не тронута.")

# НОРМАЛИЗАЦИЯ И СОХРАНЕНИЕ
scale = np.max(np.abs(data)) / (np.max(np.abs(out)) + 1e-12)
out *= scale

sf.write(str(OUT_WAV), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Сохранено: {OUT_WAV.name}")

try:
    subprocess.run(["ffmpeg", "-y", "-i", str(OUT_WAV), "-b:a", "320k", str(OUT_MP3)], 
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✅ Сохранено: {OUT_MP3.name}")
except Exception as e:
    pass
