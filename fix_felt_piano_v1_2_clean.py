"""
fix_felt_piano_v1_2_clean.py
===========================
Финальный гибрид для Felt Piano & Jazz v 1.2
Берём лучшее от всех подходов:
1. Мягкость верхов (Tape Roll-off)
2. Убийца стекла (Dynamic Suppressor на 993 и 1993 Гц)
3. Убийца дребезга (Multiband Compressor 220-500 Гц из v5)
4. НИКАКОГО САТУРАТОРА (именно он вызвал дребезг)
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "Felt Piano & Jazz v 1.2.wav"
OUTPUT = ROOT / "sound" / "wav_output" / "Felt_Piano_Jazz_v1.2_Clean_Restored.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT.name}")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

# ══════════════════════════════════════════════════════════════
#  1. DYNAMIC RESONANCE SUPPRESSOR (Убиваем стекло)
# ══════════════════════════════════════════════════════════════
def dynamic_suppressor(ch, fs, f0, Q, threshold_db, max_reduction_db, attack_ms=5.0, release_ms=50.0):
    w0 = 2 * np.pi * f0 / fs
    bw = w0 / Q
    b, a = sg.iirpeak(f0, Q, fs)
    bandpass = sg.filtfilt(b, a, ch)
    
    frame = int(attack_ms / 1000.0 * fs)
    rms = np.sqrt(np.convolve(bandpass**2, np.ones(frame)/frame, mode='same') + 1e-12)
    db_env = 20 * np.log10(rms)
    
    over_threshold = np.clip(db_env - threshold_db, 0, None)
    max_sub_factor = 1.0 - (10 ** (max_reduction_db / 20.0))
    sub_factor = np.clip(over_threshold / 10.0, 0.0, 1.0) * max_sub_factor
    
    rel_frame = int(release_ms / 1000.0 * fs)
    sub_factor_smooth = sg.filtfilt(np.ones(rel_frame)/rel_frame, [1.0], sub_factor)
    
    return ch - bandpass * sub_factor_smooth

print("\n── 1. DYNAMIC SUPPRESSION ─────────────────────")
for c in range(2):
    out[:, c] = dynamic_suppressor(out[:, c], fs, 1993.0, Q=12, threshold_db=-35, max_reduction_db=-12.0)
    out[:, c] = dynamic_suppressor(out[:, c], fs, 993.0,  Q=10, threshold_db=-30, max_reduction_db=-10.0)
print("  ✅ УСИЛЕННО подавлен стеклянный звон (1993 Гц до -12dB, 993 Гц до -10dB)")

# ══════════════════════════════════════════════════════════════
#  2. MULTIBAND COMPRESSOR (Убиваем дребезг)
# ══════════════════════════════════════════════════════════════
def lr2_lp(fc, fs):
    sos = sg.butter(2, fc, 'low',  fs=fs, output='sos')
    return np.vstack([sos, sos])

def lr2_hp(fc, fs):
    sos = sg.butter(2, fc, 'high', fs=fs, output='sos')
    return np.vstack([sos, sos])

def compress_band(ch, fs, threshold_db, ratio, attack_ms, release_ms, makeup_db=0.0):
    frame = max(1, int(attack_ms/1000.0*fs))
    rms   = np.sqrt(np.convolve(ch**2, np.ones(frame)/frame, mode='same') + 1e-12)
    thr   = 10**(threshold_db/20.0)
    mkup  = 10**(makeup_db/20.0)
    gain  = np.where(rms > thr, (thr*(rms/thr)**(1.0/ratio))/(rms+1e-12), 1.0)
    att_c = np.exp(-1.0/(fs*attack_ms/1000.0))
    rel_c = np.exp(-1.0/(fs*release_ms/1000.0))
    gs = np.zeros_like(gain); g = 1.0
    for i in range(len(gain)):
        t = gain[i]
        g = att_c*g+(1-att_c)*t if t < g else rel_c*g+(1-rel_c)*t
        gs[i] = g
    return ch * gs * mkup

print("\n── 2. MULTIBAND BUZZ CONTROL ──────────────────")
X1, X2, X3, X4 = 80.0, 220.0, 500.0, 2500.0
sos_lp1=lr2_lp(X1,fs); sos_hp1=lr2_hp(X1,fs)
sos_lp2=lr2_lp(X2,fs); sos_hp2=lr2_hp(X2,fs)
sos_lp3=lr2_lp(X3,fs); sos_hp3=lr2_hp(X3,fs)
sos_lp4=lr2_lp(X4,fs); sos_hp4=lr2_hp(X4,fs)

BANDS = [
    (-22, 1.0, 50, 250, 0.0, "Sub"),           # Не трогаем
    (-22, 1.0, 40, 220, 0.0, "FAT"),           # Не трогаем жир
    (-24, 2.5, 30, 180, 0.0, "BUZZ 220-500"),  # Жёстко давим дребезг
    (-26, 1.0, 20, 150, 0.0, "Mid"),           # Не трогаем
    (-30, 1.0, 10, 100, 0.0, "Air"),           # Не трогаем
]

out_mb = np.zeros_like(out)
for c in range(2):
    ch = out[:, c]
    b1   = sg.sosfiltfilt(sos_lp1, ch)
    rest = sg.sosfiltfilt(sos_hp1, ch)
    b2   = sg.sosfiltfilt(sos_lp2, rest)
    rest = sg.sosfiltfilt(sos_hp2, rest)
    b3   = sg.sosfiltfilt(sos_lp3, rest)
    rest = sg.sosfiltfilt(sos_hp3, rest)
    b4   = sg.sosfiltfilt(sos_lp4, rest)
    b5   = sg.sosfiltfilt(sos_hp4, rest)
    
    bc = [compress_band(b, fs, thr, rat, att, rel, mkup)
          for b, (thr,rat,att,rel,mkup,_) in zip([b1,b2,b3,b4,b5], BANDS)]
    out_mb[:, c] = sum(bc)

out = out_mb
print("  ✅ Подавлен структурный дребезг (MB Comp 220-500 Hz, Ratio 2.5)")

# ══════════════════════════════════════════════════════════════
#  3. TONE & ROLL-OFF (Финальный штрих)
# ══════════════════════════════════════════════════════════════
print("\n── 3. TONE & ROLL-OFF ─────────────────────────")
def make_low_shelf(f0, gain_db, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs
    cos_w = np.cos(w0); sq_A = np.sqrt(A); alpha = np.sin(w0)/2.0
    b = [A*((A+1)-(A-1)*cos_w+2*sq_A*alpha), 2*A*((A-1)-(A+1)*cos_w), A*((A+1)-(A-1)*cos_w-2*sq_A*alpha)]
    a = [(A+1)+(A-1)*cos_w+2*sq_A*alpha, -2*((A-1)+(A+1)*cos_w), (A+1)+(A-1)*cos_w-2*sq_A*alpha]
    return b, a

b_fat, a_fat = make_low_shelf(150.0, +2.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b_fat, a_fat, out[:, c])
print("  ✅ Добавлен жир (+2.5 dB @ 150 Hz)")

sos_lp = sg.butter(2, 8500.0, 'low', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_lp, out[:, c])
print("  ✅ Глубокий срез верхов для МЯГКОСТИ (Tape Roll-Off @ 8.5 kHz)")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
peak_orig = np.max(np.abs(data))
peak_out  = np.max(np.abs(out))
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
print(f"\n  Final peak: {20*np.log10(np.max(np.abs(out))):+.2f} dBFS")

sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")
