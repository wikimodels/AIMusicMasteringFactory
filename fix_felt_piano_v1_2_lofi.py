"""
fix_felt_piano_v1_2_lofi.py
===========================
Версия "Lo-Fi / Sleep / 10 Hours" для Felt Piano & Jazz v 1.2
Цель: бесконечное прослушивание без утомления (нулевая утомляемость слуха).

ОШИБКА ПРОШЛОЙ ВЕРСИИ:
Динамическое вырезание 1993 Гц и 993 Гц "съедало" ноту Си (B).
Когда все ноты звонкие, а Си — глухая, мозг воспринимает пианино как расстроенное.

РЕШЕНИЕ:
1. Убираем хирургические вырезы частот (чтобы все ноты звучали равномерно).
2. Применяем "Lo-Fi Tilt" — плавный, широкий спад высоких частот начиная с 1.5 кГц. 
   Это естественным образом топит стеклянный звон, не ломая конкретные ноты.
3. Оставляем MB Comp на 220-500 Гц, чтобы не дребезжало.
4. Добавляем "тёплое одеяло" (широкий буст нижней середины).
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sg
import soundfile as sf
from pathlib import Path

ROOT = Path(__file__).parent
INPUT = ROOT / "Felt Piano & Jazz v 1.2.wav"
OUTPUT = ROOT / "sound" / "wav_output" / "Felt_Piano_Jazz_v1.2_Lofi_Sleep.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT.name}")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

# ══════════════════════════════════════════════════════════════
#  1. LO-FI TILT & WARMTH (Плавное "тёплое одеяло")
# ══════════════════════════════════════════════════════════════
print("\n── 1. LO-FI TONE SHAPING ──────────────────────")

def make_high_shelf(f0, gain_db, S, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs
    alpha = np.sin(w0)/2.0 * np.sqrt((A+1.0/A)*(1.0/S-1.0)+2.0)
    cos_w = np.cos(w0); sq_A = np.sqrt(A)
    b = [A*((A+1)+(A-1)*cos_w+2*sq_A*alpha), -2*A*((A-1)+(A+1)*cos_w), A*((A+1)+(A-1)*cos_w-2*sq_A*alpha)]
    a = [(A+1)-(A-1)*cos_w+2*sq_A*alpha, 2*((A-1)-(A+1)*cos_w), (A+1)-(A-1)*cos_w-2*sq_A*alpha]
    return b, a

def make_low_shelf(f0, gain_db, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs
    cos_w = np.cos(w0); sq_A = np.sqrt(A); alpha = np.sin(w0)/2.0
    b = [A*((A+1)-(A-1)*cos_w+2*sq_A*alpha), 2*A*((A-1)-(A+1)*cos_w), A*((A+1)-(A-1)*cos_w-2*sq_A*alpha)]
    a = [(A+1)+(A-1)*cos_w+2*sq_A*alpha, -2*((A-1)+(A+1)*cos_w), (A+1)+(A-1)*cos_w-2*sq_A*alpha]
    return b, a

# Широкий спад высоких (Dark Lofi). Убираем "стекло" ЕСТЕСТВЕННО.
# Спад начинается мягко от 1.5 кГц
b_tilt, a_tilt = make_high_shelf(2000.0, -8.0, 0.4, fs)
for c in range(2): out[:, c] = sg.lfilter(b_tilt, a_tilt, out[:, c])
print("  ✅ Lo-Fi Tilt: плавный спад от 2 кГц (-8 dB)")

# Отрезаем самый-самый песок (если что-то осталось)
sos_lp = sg.butter(1, 6000.0, 'low', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_lp, out[:, c])
print("  ✅ Глубокий Low-Pass @ 6 kHz (эффект старой кассеты)")

# Убираем инфразвук (он заставляет динамики дребезжать)
sos_hp = sg.butter(2, 35.0, 'high', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
print("  ✅ High-Pass @ 35 Hz (чистка саба от механического дребезга)")

# Уютный жир (тепло) - снижаем буст чтобы не гудело
b_fat, a_fat = make_low_shelf(200.0, +1.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b_fat, a_fat, out[:, c])
print("  ✅ Теплое одеяло: Low shelf +1.5 dB @ 200 Hz")

# ══════════════════════════════════════════════════════════════
#  2. MULTIBAND COMPRESSOR (Убиваем дребезг, как и раньше)
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

print("\n── 2. MULTIBAND BUZZ CONTROL ──────────────────")
X1, X2, X3, X4 = 80.0, 220.0, 500.0, 2500.0
sos_lp1, sos_hp1 = lr2_lp(X1,fs), lr2_hp(X1,fs)
sos_lp2, sos_hp2 = lr2_lp(X2,fs), lr2_hp(X2,fs)
sos_lp3, sos_hp3 = lr2_lp(X3,fs), lr2_hp(X3,fs)
sos_lp4, sos_hp4 = lr2_lp(X4,fs), lr2_hp(X4,fs)

BANDS = [
    (-22, 2.0, 50, 250, 0.0, "Sub 20-80"),     # Жмём саббас, чтобы не рвал динамики
    (-22, 2.0, 40, 220, 0.0, "FAT 80-220"),    # Жмём мид-бас
    (-24, 2.5, 30, 180, 0.0, "BUZZ 220-500"),  # Давим гул
    (-26, 2.5, 20, 150, 0.0, "Mid 500-2500"),  # Давим дребезг в середине (500-1000 Гц)
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
print("  ✅ Подавлен структурный дребезг (MB Comp 220-500 Hz, Ratio 2.5)")

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

# Сохраняем дубль в MP3
import subprocess
OUTPUT_MP3 = ROOT / "sound" / "mp3_output" / "Felt_Piano_Jazz_v1.2_Lofi_Sleep.mp3"
OUTPUT_MP3.parent.mkdir(parents=True, exist_ok=True)
print(f"\nКонвертация в MP3: {OUTPUT_MP3}")
try:
    subprocess.run([
        "ffmpeg", "-y", "-i", str(OUTPUT), 
        "-b:a", "320k", str(OUTPUT_MP3)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"✅ MP3 Saved: {OUTPUT_MP3}")
except Exception as e:
    print(f"❌ Ошибка конвертации в MP3: {e}")
