"""
fix_slow_piano_v5.py
====================
ВЕРСИЯ 5 — убираем нотчи на нотах пианино.

КРИТИЧЕСКАЯ ОШИБКА v2–v4:
  Резонанс-хантер нашёл "пики" в спектре:
    262 Hz ≈ C4 (middle C = 261.63 Hz)   → нотч -5 dB → До тихое
    662 Hz ≈ E5 (659.25 Hz)               → нотч -4 dB → Ми тихое
   1990 Hz ≈ B6 (1975.53 Hz)              → нотч -8 dB → Си тихое

  Это были НЕ резонансы. Это самые частые ноты в треке.
  В усреднённом FFT они всегда торчат выше.
  Вырезая их — сделали пианино "расстроенным" (некоторые ноты тише).

v5 ПЛАН:
  1. Нотчей НЕТ — не трогаем ноты
  2. HP @ 35 Hz (чуть выше, убираем низкий рокот)
  3. Broad low-mid tilt @ 350 Hz -1.5 dB (шире, мягче чем раньше)
  4. Low-body boost @ 130 Hz +2 dB (жир)
  5. Air shelf @ 5kHz +3 dB
  6. Multiband comp — те же 5 полос, без изменений
  7. Sustain shaper — выключен
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
import matplotlib.gridspec as gridspec
from pathlib import Path

ROOT   = Path(__file__).parent
INPUT  = ROOT / "Slow piano Jazz v 1.wav"
OUTPUT = ROOT / "sound" / "wav_output" / "Slow_Piano_Jazz_v1_Fixed_v5.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT}  (ОРИГИНАЛ)")
print(f"Output : {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  FILTERS
# ══════════════════════════════════════════════════════════════

def make_bell(f0, Q, gain_db, fs):
    A = 10**(gain_db/40.0)
    w0 = 2*np.pi*f0/fs
    alpha = np.sin(w0)/(2.0*Q)
    b = np.array([1+alpha*A, -2*np.cos(w0), 1-alpha*A])
    a = np.array([1+alpha/A, -2*np.cos(w0), 1-alpha/A])
    return b, a

def make_high_shelf(f0, gain_db, S, fs):
    A = 10**(gain_db/40.0); w0 = 2*np.pi*f0/fs
    alpha = np.sin(w0)/2.0 * np.sqrt((A+1.0/A)*(1.0/S-1.0)+2.0)
    cos_w = np.cos(w0); sq = np.sqrt(A)
    b = np.array([A*((A+1)+(A-1)*cos_w+2*sq*alpha),
                  -2*A*((A-1)+(A+1)*cos_w),
                  A*((A+1)+(A-1)*cos_w-2*sq*alpha)])
    a = np.array([(A+1)-(A-1)*cos_w+2*sq*alpha,
                  2*((A-1)-(A+1)*cos_w),
                  (A+1)-(A-1)*cos_w-2*sq*alpha])
    return b, a

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

# ══════════════════════════════════════════════════════════════
#  LOAD
# ══════════════════════════════════════════════════════════════
data, fs = sf.read(str(INPUT))
print(f"\nLoaded ORIGINAL: sr={fs}, shape={data.shape}, dur={len(data)/fs:.1f}s")
if data.ndim == 1: data = np.stack([data, data], axis=1)
data = data.astype(np.float64)
out  = data.copy()

# ══════════════════════════════════════════════════════════════
#  ШАГ 1: EQ — БЕЗ НОТЧЕЙ НА НОТАХ
# ══════════════════════════════════════════════════════════════
print("\n── [1] EQ (без нотчей на нотах пианино) ────────")

# HP чуть выше чем раньше — убираем рокот, не трогая контрабас
sos_hp = sg.butter(2, 35.0, "high", fs=fs, output="sos")
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
print("  HP @ 35 Hz  (убираем рокот)")

# НЕТ нотчей на 262, 662, 1990 Hz — это были C4, E5, B6
print("  ✗ Нотчи 262/662/1990 Hz УБРАНЫ — это были ноты C4, E5, B6!")

# Мягкий широкий тилт на общий low-mid (Q=0.35 — очень широко)
# Снижаем общий "гул" не задевая конкретные ноты
b, a = make_bell(380.0, 0.35, -2.0, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Broad low-mid tilt @ 380 Hz  Q=0.35  -2 dB  (очень широко, не режет ноты)")

# Жир — тело пианино
b, a = make_bell(130.0, 0.6, +2.0, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Low-body boost @ 130 Hz  Q=0.6  +2 dB  (жир)")

# Presence — небольшой подъём прозрачности (широко!)
b, a = make_bell(3000.0, 0.5, +1.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Presence boost @ 3 kHz  Q=0.5  +1.5 dB  (прозрачность)")

# Air
b, a = make_high_shelf(5000.0, +3.0, 0.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Air shelf @ 5 kHz  +3 dB")

# ══════════════════════════════════════════════════════════════
#  ШАГ 2: MULTIBAND COMPRESSOR (те же параметры что v4)
#  Кроссоверы: 80 / 220 / 500 / 2500 Hz
#  Buzz zone = 220-500 Hz, ratio=2.0
#  FAT zone  = 80-220 Hz, ratio=1.3
# ══════════════════════════════════════════════════════════════
print("\n── [2] Multiband Compressor (5 полос) ───────────")

X1, X2, X3, X4 = 80.0, 220.0, 500.0, 2500.0
sos_lp1=lr2_lp(X1,fs); sos_hp1=lr2_hp(X1,fs)
sos_lp2=lr2_lp(X2,fs); sos_hp2=lr2_hp(X2,fs)
sos_lp3=lr2_lp(X3,fs); sos_hp3=lr2_hp(X3,fs)
sos_lp4=lr2_lp(X4,fs); sos_hp4=lr2_hp(X4,fs)

BANDS = [
    # thr,  ratio, att, rel, makeup, label
    (-22,   1.3,  50, 250, 0.0, "Sub   20-80 Hz"),
    (-22,   1.3,  40, 220, 0.5, "FAT   80-220 Hz  (тело пиано)"),
    (-23,   2.0,  30, 180, 0.8, "BUZZ  220-500 Hz (прицельно)"),
    (-26,   1.5,  20, 150, 0.3, "Mid   500-2500 Hz"),
    (-30,   1.1,  10, 100, 0.0, "Air   2500+ Hz"),
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
    print(f"  [OK] Ch {'L' if c==0 else 'R'}")

for thr,rat,att,rel,mkup,lbl in BANDS:
    print(f"  {lbl:30s}: ratio={rat}  thr={thr}  att={att}ms")

out = out_mb

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
print("\n── Normalization ────────────────────────────────")
peak_orig = np.max(np.abs(data))
peak_out  = np.max(np.abs(out))
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
peak_final = np.max(np.abs(out))
print(f"  Original peak : {20*np.log10(peak_orig+1e-12):+.2f} dBFS")
print(f"  After proc    : {20*np.log10(peak_out+1e-12):+.2f} dBFS")
print(f"  Scale         : {20*np.log10(scale):+.2f} dB")
print(f"  Final peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
assert peak_final <= 1.0

# ══════════════════════════════════════════════════════════════
#  SAVE
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  CHART — сравнение v4 vs v5 (показываем эффект удаления нотчей)
# ══════════════════════════════════════════════════════════════
print("\n── Chart ────────────────────────────────────────")

def smooth_spec(mono, nfft=131072, sm=100):
    n = min(nfft, len(mono))
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(mono[:n]*w, n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0/fs)
    return fr, np.convolve(20*np.log10(sp+1e-9), np.ones(sm)/sm, mode="same")

mono_o  = (data[:,0]+data[:,1])/2
mono_v4 = sf.read(str(ROOT/"sound/wav_output/Slow_Piano_Jazz_v1_Fixed_v4.wav"))[0]
mono_v4 = (mono_v4[:,0]+mono_v4[:,1])/2 if mono_v4.ndim>1 else mono_v4
mono_v5 = (out[:,0]+out[:,1])/2

fr, db_o  = smooth_spec(mono_o)
_,  db_v4 = smooth_spec(mono_v4[:len(mono_o)])
_,  db_v5 = smooth_spec(mono_v5)

BG, PL, GR = "#0d0d0d", "#1a1a1a", "#2a2a2a"
C1, C2, C3 = "#7ec8e3", "#f472b6", "#34d399"

fig = plt.figure(figsize=(14,10), facecolor=BG)
fig.suptitle("v4 (расстроенное — нотчи на нотах) vs v5 (нотчи убраны)",
             color="#e0e0e0", fontsize=13, fontweight="bold")
gs = gridspec.GridSpec(2,1, hspace=0.42)

ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(PL); ax1.grid(True, color=GR, lw=0.4)
mask = (fr>=20)&(fr<=20000)
ax1.semilogx(fr[mask], db_o[mask],  color=C1,       lw=1.0, alpha=0.5, linestyle="--", label="Original")
ax1.semilogx(fr[mask], db_v4[mask], color=C2,       lw=1.2, alpha=0.8, label="v4 (notches on C4/E5/B6)")
ax1.semilogx(fr[mask], db_v5[mask], color=C3,       lw=1.5, alpha=0.9, label="v5 (no note notches)")
# Отмечаем где были нотчи (ноты)
for f0, note, col in [(262,"C4","#ef4444"),(662,"E5","#f59e0b"),(1990,"B6","#818cf8")]:
    ax1.axvline(f0, color=col, lw=0.8, linestyle=":", alpha=0.7)
    ax1.text(f0*1.03, -45, f"{note}\n{f0}Hz", color=col, fontsize=7, va="bottom")
TICKS=[20,50,100,200,400,800,1000,2000,4000,8000,16000,20000]
TLABS=["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
ax1.set_xlim(20,20000)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Пунктирные линии = ноты которые мы ОШИБОЧНО резали нотчами", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(PL); ax2.grid(True, color=GR, lw=0.4)
d4 = np.convolve(db_v4-db_o, np.ones(80)/80, mode="same")
d5 = np.convolve(db_v5-db_o, np.ones(80)/80, mode="same")
ax2.semilogx(fr[mask], d4[mask], color=C2, lw=1.2, alpha=0.8, label="v4 − Original (ямы на нотах)")
ax2.semilogx(fr[mask], d5[mask], color=C3, lw=1.5, alpha=0.9, label="v5 − Original (ровнее)")
ax2.axhline(0, color="#666", lw=0.7, linestyle="--")
for f0, note, col in [(262,"C4","#ef4444"),(662,"E5","#f59e0b"),(1990,"B6","#818cf8")]:
    ax2.axvline(f0, color=col, lw=0.8, linestyle=":", alpha=0.6)
ax2.set_xticks(TICKS); ax2.set_xticklabels(TLABS, fontsize=8)
ax2.set_xlim(20,20000); ax2.set_ylim(-12, 10)
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax2.set_ylabel("ΔdB", color="#888", fontsize=9)
ax2.set_title("EQ Correction: v4 (ямы на C4/E5/B6) vs v5 (ровная кривая без ям)", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

rms_o  = 20*np.log10(np.sqrt(np.mean(mono_o**2))+1e-9)
rms_v5 = 20*np.log10(np.sqrt(np.mean(mono_v5**2))+1e-9)
fig.text(0.5, 0.01,
    f"RMS: {rms_o:+.1f} → {rms_v5:+.1f} dBFS  |  "
    f"Нотчи на C4/E5/B6: УБРАНЫ  |  "
    f"MB Comp buzz zone 220-500 Hz ratio=2.0  |  Peak: {20*np.log10(peak_final+1e-12):+.2f} dBFS",
    ha="center", va="bottom", fontsize=8, color="#aaa",
    bbox=dict(facecolor="#111", edgecolor="#333", alpha=0.8, pad=5))

plt.savefig(str(ROOT/"analysis"/"Slow_Piano_Jazz_v1_fix_v5_comparison.png"),
            dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[CHART] saved")

rms_v5 = 20*np.log10(np.sqrt(np.mean(mono_v5**2))+1e-9)
print("\n"+"="*60)
print("  FIX v5 — REPORT")
print("="*60)
print(f"  Input  : {INPUT.name}  (ОРИГИНАЛ)")
print(f"  Output : {OUTPUT.name}")
print(f"  RMS    : {rms_o:+.2f} → {rms_v5:+.2f} dBFS")
print(f"  Peak   : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
print()
print("  КЛЮЧЕВОЕ ИЗМЕНЕНИЕ:")
print("  ✅ Нотчи на C4(262Hz)/E5(662Hz)/B6(1990Hz) — УБРАНЫ")
print("     Это были ноты, не артефакты. Пианино снова ровное.")
print("  ✅ Buzz контроль — только через MB comp (220-500 Hz)")
print("  ✅ Жир — +2 dB @ 130 Hz")
print("  ✅ Presence — +1.5 dB @ 3kHz (широко)")
print("  ✅ Air — +3 dB @ 5kHz")
print()
print("  ЕСЛИ НУЖНА ПОДСТРОЙКА:")
print("  Пианино мутит    → broad tilt: -2→-3 dB @ 380 Hz")
print("  Дребезг остался  → buzz ratio: 2.0→2.5")
print("  Жира мало        → body boost: +2→+3 dB @ 130 Hz")
print("="*60)
