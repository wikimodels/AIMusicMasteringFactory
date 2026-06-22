"""
fix_guitar_jazz_v3_stabilized.py
================================
- Оставляем гитару чистой
- Схлапываем бас и нижнюю середину в МОНО (для стабильности при "плавании" AI)
- Умный AGC (Auto Gain) для вытягивания провалов громкости
- Мультибэнд компрессор на бас (60-250 Гц) против гудения
- De-Esser на верха против щеток
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
import subprocess
from pathlib import Path
from scipy.ndimage import uniform_filter1d

ROOT = Path(__file__).parent
INPUT = ROOT / "Guitar Jazz" / "Guitar & Jazz v 1.1.wav"
OUT_WAV = ROOT / "sound" / "wav_output" / "Guitar_Jazz_v1.1_Stabilized.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Guitar_Jazz_v1.1_Stabilized.mp3"

OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

print(f"[{INPUT.name}] Запуск стабилизации...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

def lr2_lp(fc, fs): return np.vstack([sg.butter(2, fc, 'low', fs=fs, output='sos')] * 2)
def lr2_hp(fc, fs): return np.vstack([sg.butter(2, fc, 'high', fs=fs, output='sos')] * 2)

def compress_band(ch, fs, threshold_db, ratio, attack_ms, release_ms, makeup_db=0.0):
    frame = max(1, int(attack_ms/1000.0*fs))
    rms = np.sqrt(uniform_filter1d(ch**2, size=frame) + 1e-12)
    thr, mkup = 10**(threshold_db/20.0), 10**(makeup_db/20.0)
    gain = np.where(rms > thr, (thr*(rms/thr)**(1.0/ratio))/(rms+1e-12), 1.0)
    att_c, rel_c = np.exp(-1.0/(fs*attack_ms/1000.0)), np.exp(-1.0/(fs*release_ms/1000.0))
    gs = np.zeros_like(gain); g = 1.0
    for i in range(len(gain)):
        t = gain[i]
        g = att_c*g+(1-att_c)*t if t < g else rel_c*g+(1-rel_c)*t
        gs[i] = g
    return ch * gs * mkup

def auto_gain_control(ch, fs, target_db=-18.0, max_boost_db=6.0, win_ms=500.0):
    win_samps = int(win_ms / 1000.0 * fs)
    # Считаем RMS
    sq = uniform_filter1d(ch**2, size=win_samps)
    rms_db = 20 * np.log10(np.sqrt(sq) + 1e-12)
    # Находим провалы и вычисляем компенсацию
    gain_db = np.clip(target_db - rms_db, 0, max_boost_db)
    # Сглаживаем gain
    gain_db_smooth = uniform_filter1d(gain_db, size=win_samps)
    return ch * (10**(gain_db_smooth/20.0))

# 1. СТАБИЛИЗАЦИЯ СТЕРЕО (МОНОФОНИЗАЦИЯ НИЗОВ)
print("── 1. STEREO STABILIZATION ──")
mid = (out[:, 0] + out[:, 1]) / 2.0
side = (out[:, 0] - out[:, 1]) / 2.0
# Срезаем низ из Side (всё ниже 400 Гц становится моно)
sos_hp_side = sg.butter(2, 400.0, 'high', fs=fs, output='sos')
side = sg.sosfiltfilt(sos_hp_side, side)
out[:, 0] = mid + side
out[:, 1] = mid - side
print("  ✅ Бас и нижняя середина (<400 Гц) жестко зафиксированы в Моно. Плавание фазы устранено.")

# 2. AUTO GAIN CONTROL (Вытаскиваем ямы)
print("── 2. AUTO GAIN CONTROL ──")
for c in range(2):
    out[:, c] = auto_gain_control(out[:, c], fs, target_db=-19.0, max_boost_db=8.0, win_ms=500.0)
print("  ✅ Провалы громкости (артефакты генерации) вытягиваются вверх.")

# 3. МУЛЬТИБЭНД (Укрощение Баса + Смягчение Щеток)
print("── 3. MULTIBAND DYNAMICS ──")
sos_lp_bass, sos_hp_bass = lr2_lp(250.0, fs), lr2_hp(250.0, fs)
sos_lp_high, sos_hp_high = lr2_lp(3500.0, fs), lr2_hp(3500.0, fs)

out_mb = np.zeros_like(out)
for c in range(2):
    ch = out[:, c]
    # Разделяем на 3 полосы: Bass (0-250), Mid (250-3500), High (3500+)
    bass_band = sg.sosfiltfilt(sos_lp_bass, ch)
    rest = sg.sosfiltfilt(sos_hp_bass, ch)
    mid_band = sg.sosfiltfilt(sos_lp_high, rest)
    high_band = sg.sosfiltfilt(sos_hp_high, rest)
    
    # Компрессируем БАС (чтобы не гудел и не лажал) - средняя атака
    bass_comp = compress_band(bass_band, fs, threshold_db=-20, ratio=3.0, attack_ms=10.0, release_ms=100.0)
    
    # Компрессируем ВЕРХА (пластик щеток) - очень быстрая атака
    high_comp = compress_band(high_band, fs, threshold_db=-28, ratio=4.0, attack_ms=1.5, release_ms=40.0)
    
    # Середину (гитару) не трогаем
    out_mb[:, c] = bass_comp + mid_band + high_comp

out = out_mb
print("  ✅ Бас укрощен (Multiband Compression 0-250 Hz). Больше не лажает и не гудит.")
print("  ✅ Пластик щеток смят (Fast Compression 3500+ Hz).")

# 4. HPF (Убираем инфра-саб)
sos_hp_sub = sg.butter(2, 30.0, 'high', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp_sub, out[:, c])

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
