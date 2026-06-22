"""
batch_lofi_process.py
=====================
Пакетная обработка всех WAV файлов в указанной папке.
Применяет Lofi-мастеринг (спасение от дребезга и стекла) и сохраняет в MP3.
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
INPUT_DIR = ROOT / "Felt Piano Jazz"
OUT_WAV_DIR = ROOT / "sound" / "wav_output"
OUT_MP3_DIR = ROOT / "sound" / "mp3_output"

OUT_WAV_DIR.mkdir(parents=True, exist_ok=True)
OUT_MP3_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════
#  ФУНКЦИИ АЛГОРИТМА
# ══════════════════════════════════════════════════════════════
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
#  ГЛАВНАЯ ФУНКЦИЯ ОБРАБОТКИ
# ══════════════════════════════════════════════════════════════
def process_file(input_path):
    print(f"\n[{input_path.name}] Запуск Lofi-мастеринга...")
    data, fs = sf.read(str(input_path))
    if data.ndim == 1: data = np.stack([data, data], axis=1)
    out = data.astype(np.float64)

    # 1. LO-FI EQ & ROLL-OFF
    b_tilt, a_tilt = make_high_shelf(2000.0, -8.0, 0.4, fs)
    for c in range(2): out[:, c] = sg.lfilter(b_tilt, a_tilt, out[:, c])
    
    # Lo-Fi Scoop (убираем гнусавость и коробочность на 500 Гц)
    b_scoop, a_scoop = make_bell(500.0, 0.5, -3.0, fs)
    for c in range(2): out[:, c] = sg.lfilter(b_scoop, a_scoop, out[:, c])
    
    sos_lp = sg.butter(1, 6000.0, 'low', fs=fs, output='sos')
    for c in range(2): out[:, c] = sg.sosfiltfilt(sos_lp, out[:, c])
    sos_hp = sg.butter(2, 35.0, 'high', fs=fs, output='sos')
    for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
    b_fat, a_fat = make_low_shelf(200.0, +1.5, fs)
    for c in range(2): out[:, c] = sg.lfilter(b_fat, a_fat, out[:, c])

    # 2. MULTIBAND BUZZ CONTROL
    X1, X2, X3, X4 = 80.0, 220.0, 500.0, 2500.0
    sos_lp1, sos_hp1 = lr2_lp(X1,fs), lr2_hp(X1,fs)
    sos_lp2, sos_hp2 = lr2_lp(X2,fs), lr2_hp(X2,fs)
    sos_lp3, sos_hp3 = lr2_lp(X3,fs), lr2_hp(X3,fs)
    sos_lp4, sos_hp4 = lr2_lp(X4,fs), lr2_hp(X4,fs)

    BANDS = [
        (-22, 2.0, 50, 250, 0.0, "Sub"),
        (-22, 2.0, 40, 220, 0.0, "FAT"),
        (-24, 2.5, 30, 180, 0.0, "BUZZ 220-500"),
        (-26, 2.5, 20, 150, 0.0, "Mid 500-2500"),
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

    # НОРМАЛИЗАЦИЯ
    scale = np.max(np.abs(data)) / (np.max(np.abs(out)) + 1e-12)
    out *= scale

    # СОХРАНЕНИЕ WAV
    out_wav_path = OUT_WAV_DIR / f"{input_path.stem}_Lofi_Master.wav"
    sf.write(str(out_wav_path), out.astype(np.float32), fs, subtype="PCM_24")
    
    # КОНВЕРТАЦИЯ В MP3
    out_mp3_path = OUT_MP3_DIR / f"{input_path.stem}_Lofi_Master.mp3"
    try:
        subprocess.run(["ffmpeg", "-y", "-i", str(out_wav_path), "-b:a", "320k", str(out_mp3_path)], 
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  ✅ Готово! Сохранено: {out_mp3_path.name}")
    except Exception as e:
        print(f"  ❌ Ошибка MP3: {e}")

# ══════════════════════════════════════════════════════════════
#  ИСПОЛНЕНИЕ
# ══════════════════════════════════════════════════════════════
if not INPUT_DIR.exists():
    print(f"Папка {INPUT_DIR} не найдена!")
    sys.exit(1)

files = list(INPUT_DIR.glob("*.wav"))
if not files:
    print(f"В папке {INPUT_DIR} нет WAV файлов!")
    sys.exit(0)

print(f"Найдено файлов для обработки: {len(files)}")
for f in files:
    process_file(f)

print("\nПакетная обработка завершена!")
