"""
fix_felt_piano_v1_2_tape.py
===========================
Реставрация "Felt Piano & Jazz v 1.2.wav"
Проблема: Вшитый артефакт нейросети на 1993 Гц и 993 Гц (стеклянный звон), 
который не убирается обычным эквалайзером.

Решение:
1. Dynamic Resonance Suppressor (аналог Soothe) — вычитает звон *только* когда он превышает порог.
2. Tape Saturation (эмуляция плёнки) — насыщает гармониками, смягчает атаки.
3. Tilt/Tape-Roll-Off — аккуратный срез самых "ядовитых" цифровых верхов.
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
OUTPUT = ROOT / "sound" / "wav_output" / "Felt_Piano_Jazz_v1.2_Tape_Restored.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT.name}")
data, fs = sf.read(str(INPUT))
if data.ndim == 1: data = np.stack([data, data], axis=1)
out = data.astype(np.float64)

# ══════════════════════════════════════════════════════════════
#  1. DYNAMIC RESONANCE SUPPRESSOR (Убийца стеклянного звона)
# ══════════════════════════════════════════════════════════════
def dynamic_suppressor(ch, fs, f0, Q, threshold_db, max_reduction_db, attack_ms=5.0, release_ms=50.0):
    """
    Динамически вырезает частоту f0, только когда её уровень превышает threshold_db.
    Работает как параллельный bandpass с перевернутой фазой.
    """
    # 1. Выделяем проблемную частоту
    w0 = 2 * np.pi * f0 / fs
    bw = w0 / Q
    b, a = sg.iirpeak(f0, Q, fs)
    bandpass = sg.filtfilt(b, a, ch)
    
    # 2. Вычисляем огибающую (RMS) этой частоты
    frame = int(attack_ms / 1000.0 * fs)
    rms = np.sqrt(np.convolve(bandpass**2, np.ones(frame)/frame, mode='same') + 1e-12)
    db_env = 20 * np.log10(rms)
    
    # 3. Считаем насколько превышен порог
    over_threshold = np.clip(db_env - threshold_db, 0, None)
    
    # 4. Превращаем превышение в коэффициент вычитания
    # max_reduction_db = -6 dB означает, что мы можем вычесть до 50% сигнала (коэфф 0.5)
    max_sub_factor = 1.0 - (10 ** (max_reduction_db / 20.0))
    
    # Масштабируем превышение: каждые 10 дБ превышения дают полный max_sub_factor
    sub_factor = np.clip(over_threshold / 10.0, 0.0, 1.0) * max_sub_factor
    
    # Сглаживаем коэффициент (release)
    rel_frame = int(release_ms / 1000.0 * fs)
    sub_factor_smooth = sg.filtfilt(np.ones(rel_frame)/rel_frame, [1.0], sub_factor)
    
    # 5. Вычитаем резонанс из оригинала
    ch_out = ch - bandpass * sub_factor_smooth
    return ch_out, sub_factor_smooth

print("\n── DYNAMIC SUPPRESSION ────────────────────────")
# Давим 1993 Гц (B6) и 993 Гц (B5)
reductions = []
for c in range(2):
    # Порог -30 дБ (относительно RMS полосы)
    out[:, c], red1 = dynamic_suppressor(out[:, c], fs, 1993.0, Q=12, threshold_db=-35, max_reduction_db=-10.0)
    out[:, c], red2 = dynamic_suppressor(out[:, c], fs, 993.0,  Q=10, threshold_db=-30, max_reduction_db=-8.0)
    reductions.append(red1 + red2)
print("  ✅ Подавлен звон 1993 Гц и 993 Гц (Soothe-алгоритм)")

# ══════════════════════════════════════════════════════════════
#  2. TAPE SATURATION & WARMTH (Ленточная сатурация)
# ══════════════════════════════════════════════════════════════
print("\n── TAPE SATURATION ────────────────────────────")

def tape_saturation(ch, drive_db=4.0, asymmetry=0.1):
    """
    Асимметричная ленточная сатурация.
    drive_db: усиление перед искажением (больше = теплее/грязнее).
    asymmetry: добавляет чётные гармоники (ламповость/лента).
    """
    drive = 10 ** (drive_db / 20.0)
    
    # Pre-EQ (на ленту подаётся сигнал с поднятым верхом, чтобы потом срезать шум)
    # Здесь мы поднимаем середину, чтобы сатурировать "тело"
    b_pre, a_pre = sg.butter(1, 400.0, 'high', fs=fs)
    ch_pre = ch + 0.3 * sg.lfilter(b_pre, a_pre, ch)
    
    x = ch_pre * drive
    
    # Асимметричный софт-клиппер (модель магнитной ленты)
    # Положительная полуволна сжимается чуть иначе, чем отрицательная
    x_asym = x + asymmetry * (x ** 2)
    
    # Tanh - классическая кривая насыщения
    y = np.tanh(x_asym)
    
    # Компенсация уровня
    y = y / drive
    return y

# Применяем сатурацию
drive_level = 3.0 # дБ драйва (мягко)
for c in range(2):
    out[:, c] = tape_saturation(out[:, c], drive_db=drive_level, asymmetry=0.08)
print(f"  ✅ Применена эмуляция плёнки (Drive: +{drive_level} dB)")

# ══════════════════════════════════════════════════════════════
#  3. TONE & TAPE ROLL-OFF (Финальный EQ)
# ══════════════════════════════════════════════════════════════
print("\n── TONE & ROLL-OFF ────────────────────────────")

# 1. Возвращаем жир, который мог потеряться (Low Shelf)
def make_low_shelf(f0, gain_db, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs
    cos_w = np.cos(w0); sq_A = np.sqrt(A); alpha = np.sin(w0)/2.0
    b = [A*((A+1)-(A-1)*cos_w+2*sq_A*alpha), 2*A*((A-1)-(A+1)*cos_w), A*((A+1)-(A-1)*cos_w-2*sq_A*alpha)]
    a = [(A+1)+(A-1)*cos_w+2*sq_A*alpha, -2*((A-1)+(A+1)*cos_w), (A+1)+(A-1)*cos_w-2*sq_A*alpha]
    return b, a

b_fat, a_fat = make_low_shelf(150.0, +2.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b_fat, a_fat, out[:, c])
print("  ✅ Добавлен жир (Low Shelf +2.5 dB @ 150 Hz)")

# 2. Мягкий Tape Roll-Off на верхах (имитация старой плёнки, убивает цифровой песок)
# 2-й порядок lowpass на 11 кГц
sos_lp = sg.butter(2, 11000.0, 'low', fs=fs, output='sos')
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_lp, out[:, c])
print("  ✅ Мягкий срез верхов (Tape Roll-Off @ 11 kHz)")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
print("\n── Normalization ────────────────────────────────")
peak_orig = np.max(np.abs(data))
peak_out  = np.max(np.abs(out))
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
print(f"  Scale applied : {20*np.log10(scale):+.2f} dB")
print(f"  Final peak    : {20*np.log10(np.max(np.abs(out))):+.2f} dBFS")

# ══════════════════════════════════════════════════════════════
#  SAVE
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  ГРАФИКИ СРАВНЕНИЯ
# ══════════════════════════════════════════════════════════════
def smooth_spec(mono, nfft=65536, sm=50):
    n = min(nfft, len(mono))
    sp = np.abs(np.fft.rfft(mono[:n]*np.hanning(n), n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0/fs)
    db = 20*np.log10(sp+1e-9)
    return fr, np.convolve(db, np.ones(sm)/sm, mode="same")

fr, db_o = smooth_spec((data[:,0]+data[:,1])/2)
_,  db_f = smooth_spec((out[:,0]+out[:,1])/2)

plt.figure(figsize=(14, 8), facecolor="#111")
plt.subplot(211, facecolor="#222")
plt.grid(True, color="#444", lw=0.4)
mask = (fr > 20) & (fr < 20000)
plt.semilogx(fr[mask], db_o[mask], color="#7ec8e3", lw=1.2, alpha=0.6, linestyle="--", label="Original v1.2")
plt.semilogx(fr[mask], db_f[mask], color="#f472b6", lw=1.5, alpha=0.9, label="Tape Restored")
plt.axvspan(10, 150, color="#f59e0b", alpha=0.05, label="Fat Boost")
plt.axvspan(11000, 20000, color="#ef4444", alpha=0.05, label="Tape Roll-off")
plt.axvline(993, color="#ef4444", lw=0.8, linestyle=":"); plt.text(993, np.max(db_f), "993Hz Dynamic Cut", color="#ef4444", fontsize=8)
plt.axvline(1993, color="#ef4444", lw=0.8, linestyle=":"); plt.text(1993, np.max(db_f), "1993Hz Dynamic Cut", color="#ef4444", fontsize=8)
plt.legend(facecolor="#333", edgecolor="#555", labelcolor="#fff")
plt.title("Tape Saturation + Dynamic EQ: Spectrum", color="#fff")
[t.set_color("#ccc") for t in plt.gca().get_xticklabels() + plt.gca().get_yticklabels()]

plt.subplot(212, facecolor="#222")
plt.grid(True, color="#444", lw=0.4)
diff = np.convolve(db_f - db_o, np.ones(50)/50, mode='same')
plt.semilogx(fr[mask], diff[mask], color="#34d399", lw=1.5, label="Difference (Tape - Original)")
plt.axhline(0, color="#888", linestyle="--")
plt.fill_between(fr[mask], 0, diff[mask], where=(diff[mask]>0), color="#34d399", alpha=0.2)
plt.fill_between(fr[mask], 0, diff[mask], where=(diff[mask]<0), color="#ef4444", alpha=0.2)
plt.ylim(-10, 5)
plt.legend(facecolor="#333", edgecolor="#555", labelcolor="#fff")
plt.title("Correction Curve", color="#fff")
[t.set_color("#ccc") for t in plt.gca().get_xticklabels() + plt.gca().get_yticklabels()]

plt.tight_layout()
out_chart = ROOT / "analysis" / "Felt_Piano_Jazz_v1.2_Tape_Chart.png"
plt.savefig(str(out_chart), dpi=120, facecolor="#111")
plt.close()
print(f"[CHART] {out_chart}")
