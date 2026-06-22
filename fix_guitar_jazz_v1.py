"""
fix_guitar_jazz_v1.py
=====================
Специальный мастеринг для Guitar & Jazz.
Цель: Убить "пластиковые" щетки, металлический звон струн и гулкую "коробочность" гитары.
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
OUT_WAV = ROOT / "sound" / "wav_output" / "Guitar_Jazz_v1.1_Natural_Master.wav"
OUT_MP3 = ROOT / "sound" / "mp3_output" / "Guitar_Jazz_v1.1_Natural_Master.mp3"

OUT_WAV.parent.mkdir(parents=True, exist_ok=True)
OUT_MP3.parent.mkdir(parents=True, exist_ok=True)

print(f"[{INPUT.name}] Запуск мастеринга...")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

# ══════════════════════════════════════════════════════════════
#  ФУНКЦИИ
# ══════════════════════════════════════════════════════════════
def dynamic_suppressor(ch, fs, f0, Q, threshold_db, max_reduction_db, attack_ms=5.0, release_ms=50.0):
    w0 = 2*np.pi*f0/fs; alpha = np.sin(w0)/(2.0*Q)
    b_bp = [alpha, 0, -alpha]; a_bp = [1+alpha, -2*np.cos(w0), 1-alpha]
    bp_sig = sg.lfilter(b_bp, a_bp, ch)
    frame = max(1, int(attack_ms/1000.0*fs))
    rms = np.sqrt(np.convolve(bp_sig**2, np.ones(frame)/frame, mode='same') + 1e-12)
    thr = 10**(threshold_db/20.0)
    ratio = 10.0 
    gain_db = np.where(rms > thr, -(20*np.log10(rms/thr)) * (1 - 1/ratio), 0)
    gain_db = np.maximum(gain_db, max_reduction_db)
    gain_lin = 10**(gain_db/20.0)
    
    att_c = np.exp(-1.0/(fs*attack_ms/1000.0))
    rel_c = np.exp(-1.0/(fs*release_ms/1000.0))
    gs = np.zeros_like(gain_lin); g = 1.0
    for i in range(len(gain_lin)):
        t = gain_lin[i]
        g = att_c*g + (1-att_c)*t if t < g else rel_c*g + (1-rel_c)*t
        gs[i] = g
    
    # Динамический Notch (плавающий Q/Gain) - упрощенная реализация через подмес BP
    # Суть: вычитаем отфильтрованный сигнал с нужным гейном
    return ch - bp_sig * (1.0 - gs)

def make_bell(f0, Q, gain_db, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs; alpha = np.sin(w0)/(2.0*Q)
    b = [1+alpha*A, -2*np.cos(w0), 1-alpha*A]; a = [1+alpha/A, -2*np.cos(w0), 1-alpha/A]
    return b, a

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
#  1. УБИЙСТВО "ИГЛ" И ПЛАСТИКОВЫХ ЩЕТОК
# ══════════════════════════════════════════════════════════════
print("── 1. DYNAMIC SUPPRESSION (Убираем свист и пластик) ──")
needles = [1979.0, 2357.0, 2638.0, 3959.0, 4617.0]
for c in range(2):
    for f in needles:
        # Давим каждую частоту до -12 дБ, если она вылезает
        out[:, c] = dynamic_suppressor(out[:, c], fs, f, Q=10, threshold_db=-35, max_reduction_db=-12.0)
print("  ✅ 5 резких резонансов струн подавлены")

# ══════════════════════════════════════════════════════════════
#  2. ТОНАЛЬНОСТЬ (Мягкость щеток + анти-коробка)
# ══════════════════════════════════════════════════════════════
print("── 2. TONE SHAPING ──")
# Вырез мути и коробки
b_box, a_box = make_bell(450.0, 0.4, -4.0, fs)
for c in range(2): out[:, c] = sg.lfilter(b_box, a_box, out[:, c])
print("  ✅ Яма на 450 Гц (-4 dB) — убрали гул деки гитары")

# Срезаем ультразвуковой мусор и "пластик" от AI
sos_lp = sg.butter(2, 7500.0, 'low', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_lp, out[:, c])
print("  ✅ Мягкий Roll-off верхов от 7.5 кГц — щетки стали бархатными")

# Убираем саб-грязь
sos_hp = sg.butter(2, 40.0, 'high', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])

# ══════════════════════════════════════════════════════════════
#  3. МУЛЬТИБЭНД (Склеиваем щетки)
# ══════════════════════════════════════════════════════════════
print("── 3. MULTIBAND COMPRESSION ──")
X1, X2, X3, X4 = 80.0, 250.0, 2500.0, 8000.0
sos_lp1, sos_hp1 = lr2_lp(X1,fs), lr2_hp(X1,fs)
sos_lp2, sos_hp2 = lr2_lp(X2,fs), lr2_hp(X2,fs)
sos_lp3, sos_hp3 = lr2_lp(X3,fs), lr2_hp(X3,fs)
sos_lp4, sos_hp4 = lr2_lp(X4,fs), lr2_hp(X4,fs)

BANDS = [
    (-22, 1.0, 50, 250, 0.0, "Sub 20-80"),
    (-22, 1.0, 40, 220, 0.0, "FAT 80-250"),
    (-24, 2.5, 30, 180, 0.0, "MUD 250-2500"),      # Давим остатки коробки динамически
    (-30, 3.5,  5,  50, 0.0, "PLASTIC 2500-8000"), # Жестко плющим щетки, делая их мягким фоном!
    (-30, 1.0, 10, 100, 0.0, "Air"),
]

out_mb = np.zeros_like(out)
for c in range(2):
    ch = out[:, c]
    b1 = sg.sosfiltfilt(sos_lp1, ch); rest = sg.sosfiltfilt(sos_hp1, ch)
    b2 = sg.sosfiltfilt(sos_lp2, rest); rest = sg.sosfiltfilt(sos_hp2, rest)
    b3 = sg.sosfiltfilt(sos_lp3, rest); rest = sg.sosfiltfilt(sos_hp3, rest)
    b4 = sg.sosfiltfilt(sos_lp4, rest); b5 = sg.sosfiltfilt(sos_hp4, rest)
    bc = [compress_band(b, fs, thr, rat, att, rel, mkup) for b, (thr,rat,att,rel,mkup,_) in zip([b1,b2,b3,b4,b5], BANDS)]
    out_mb[:, c] = sum(bc)

out = out_mb
print("  ✅ Пластиковые атаки щеток сплющены (Ratio 3.5, быстрая атака)")

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
