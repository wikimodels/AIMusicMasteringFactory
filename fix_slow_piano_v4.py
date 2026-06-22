"""
fix_slow_piano_v4.py
====================
ВЕРСИЯ 4 — "дребезг меньше, но потерял жир" — баланс.

ФИДБЕК v3:
  ✓ Дребезжание стало меньше
  ✗ Сухо — пианино потеряло жир/тело

ПРИЧИНЫ СУХОСТИ В v3:
  • Sustain shaper -2.5 dB убивал именно ТЕЛО ноты (жир = хвост резонанса)
  • MB comp band 2 (120-500 Hz) ratio=2.5 слишком зажал — там живёт тепло пианино
  • Жир пианино: 80-200 Hz (тело) + sustain tail
  • Buzz: 200-500 Hz (верхняя половина той же полосы)

РЕШЕНИЕ v4:
  1. Sustain shaper — ВЫКЛЮЧЁН (он убивал жир)
  2. MB comp: уточняем кроссовер — 80 / 220 / 500 / 2500 Hz
     • Band 2 (80-220 Hz)  : ratio=1.3  — ЖИР, почти не трогаем
     • Band 3 (220-500 Hz) : ratio=2.0  — BUZZ ZONE, давим прицельно
     • Band 4 (500-2500 Hz): ratio=1.5  — mid, чуть мягче чем v3
  3. Low-body boost @ 120 Hz +2 dB — прямо возвращаем жир
  4. Те же 3 нотча + воздух @ 5kHz
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
OUTPUT = ROOT / "sound" / "wav_output" / "Slow_Piano_Jazz_v1_Fixed_v4.wav"
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
    """
    Векторизованный RMS-компрессор с gain smoothing.
    attack_ms медленный = пропускаем трансиент, давим тело/buzz.
    """
    frame = max(1, int(attack_ms/1000.0*fs))
    sq    = ch**2
    rms   = np.sqrt(np.convolve(sq, np.ones(frame)/frame, mode='same') + 1e-12)

    thr_lin = 10**(threshold_db/20.0)
    makeup  = 10**(makeup_db/20.0)

    gain = np.where(
        rms > thr_lin,
        (thr_lin * (rms/thr_lin)**(1.0/ratio)) / (rms + 1e-12),
        1.0
    )

    # Smooth gain
    att_c = np.exp(-1.0/(fs * attack_ms/1000.0))
    rel_c = np.exp(-1.0/(fs * release_ms/1000.0))
    gs = np.zeros_like(gain); g = 1.0
    for i in range(len(gain)):
        t = gain[i]
        g = att_c*g + (1-att_c)*t if t < g else rel_c*g + (1-rel_c)*t
        gs[i] = g

    return ch * gs * makeup


# ══════════════════════════════════════════════════════════════
#  LOAD
# ══════════════════════════════════════════════════════════════
data, fs = sf.read(str(INPUT))
print(f"\nLoaded: sr={fs}, shape={data.shape}, dur={len(data)/fs:.1f}s")
if data.ndim == 1: data = np.stack([data, data], axis=1)
data = data.astype(np.float64)
out  = data.copy()

# ══════════════════════════════════════════════════════════════
#  ШАГ 1: SURGICAL EQ
# ══════════════════════════════════════════════════════════════
print("\n── [1] Surgical EQ ──────────────────────────────")

sos_hp = sg.butter(2, 25.0, "high", fs=fs, output="sos")
for c in range(2): out[:, c] = sg.sosfiltfilt(sos_hp, out[:, c])
print("  HP @ 25 Hz")

# 3 нотча (те же что v2/v3)
for f0, Q, gain, desc in [
    (1990, 10, -8.0, "Presence sting"),
    (262,   8, -5.0, "Low-mid mud"),
    (662,   8, -4.0, "Nasal box"),
]:
    b, a = make_bell(f0, Q, gain, fs)
    for c in range(2): out[:, c] = sg.filtfilt(b, a, out[:, c])
    print(f"  Notch {f0:.0f} Hz  Q={Q}  {gain:+.0f} dB  [{desc}]")

# Low-mid tilt
b, a = make_bell(350.0, 0.4, -2.0, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Low-mid tilt @ 350 Hz  -2 dB")

# ── ВОЗВРАЩАЕМ ЖИР: low-body boost ──────────────────────────
# 80-200 Hz — тело пиано. Поднимаем мягко (+2 dB, Q=0.6)
b, a = make_bell(130.0, 0.6, +2.0, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Low-body boost @ 130 Hz  Q=0.6  +2 dB  ← ЖИР ВОЗВРАЩЁН")

# Air shelf
b, a = make_high_shelf(5000.0, +3.0, 0.5, fs)
for c in range(2): out[:, c] = sg.lfilter(b, a, out[:, c])
print("  Air shelf @ 5 kHz  +3 dB")

# ══════════════════════════════════════════════════════════════
#  ШАГ 2: MULTIBAND COMPRESSOR — уточнённые полосы
#
#  НОВЫЕ кроссоверы: 80 / 220 / 500 / 2500 Hz
#  Теперь зона ЖИРА (80-220 Hz) и BUZZ (220-500 Hz) разделены
# ══════════════════════════════════════════════════════════════
print("\n── [2] Multiband Compressor (v4 — жир отделён от buzz) ─")

X1, X2, X3, X4 = 80.0, 220.0, 500.0, 2500.0

sos_lp1 = lr2_lp(X1,  fs); sos_hp1 = lr2_hp(X1,  fs)
sos_lp2 = lr2_lp(X2,  fs); sos_hp2 = lr2_hp(X2,  fs)
sos_lp3 = lr2_lp(X3,  fs); sos_hp3 = lr2_hp(X3,  fs)
sos_lp4 = lr2_lp(X4,  fs); sos_hp4 = lr2_hp(X4,  fs)

# Параметры:
#  band1 (sub 20-80)    : почти не трогаем
#  band2 (fat 80-220)   : ratio=1.3 — лёгкое глэю, ЖИР НЕ ДАВИМ
#  band3 (buzz 220-500) : ratio=2.0 — ПРИЦЕЛЬНЫЙ buzz control
#  band4 (mid 500-2500) : ratio=1.5 — мягко
#  band5 (air 2500+)    : ratio=1.1 — почти прозрачно
BANDS = [
    # (thr_db, ratio, att_ms, rel_ms, makeup_db, label)
    (-22, 1.3,  50, 250, 0.0, "Sub   20-80 Hz"),
    (-22, 1.3,  40, 220, 0.5, "FAT   80-220 Hz  ← тело пиано"),
    (-23, 2.0,  30, 180, 0.8, "BUZZ  220-500 Hz ← прицельный"),
    (-26, 1.5,  20, 150, 0.3, "Mid   500-2500 Hz"),
    (-30, 1.1,  10, 100, 0.0, "Air   2500+ Hz"),
]

out_mb = np.zeros_like(out)

for c in range(2):
    ch = out[:, c]

    # Разделяем на 5 полос
    b1   = sg.sosfiltfilt(sos_lp1, ch)
    rest = sg.sosfiltfilt(sos_hp1, ch)
    b2   = sg.sosfiltfilt(sos_lp2, rest)
    rest = sg.sosfiltfilt(sos_hp2, rest)
    b3   = sg.sosfiltfilt(sos_lp3, rest)
    rest = sg.sosfiltfilt(sos_hp3, rest)
    b4   = sg.sosfiltfilt(sos_lp4, rest)
    b5   = sg.sosfiltfilt(sos_hp4, rest)

    bands_raw = [b1, b2, b3, b4, b5]
    bands_out = []
    for bi, (thr, rat, att, rel, mkup, _) in zip(bands_raw, BANDS):
        bands_out.append(compress_band(bi, fs, thr, rat, att, rel, mkup))

    out_mb[:, c] = sum(bands_out)
    print(f"  [OK] Ch {'L' if c==0 else 'R'}")

for thr, rat, att, rel, mkup, lbl in BANDS:
    print(f"  {lbl:28s}: ratio={rat}  thr={thr} dB  att={att}ms  makeup={mkup:+.1f}dB")

out = out_mb

# ══════════════════════════════════════════════════════════════
#  SUSTAIN SHAPER: ВЫКЛЮЧЁН
#  Тот самый "жир" = хвост резонанса пианино.
#  Убирать нельзя. Buzz контролируем через MB comp.
# ══════════════════════════════════════════════════════════════
print("\n── [3] Sustain Shaper: ВЫКЛЮЧЁН (жир = хвост, не трогаем) ─")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ
# ══════════════════════════════════════════════════════════════
print("\n── Normalization ────────────────────────────────")
peak_orig = np.max(np.abs(data))
peak_out  = np.max(np.abs(out))
print(f"  Original peak : {20*np.log10(peak_orig+1e-12):+.2f} dBFS")
print(f"  After proc    : {20*np.log10(peak_out+1e-12):+.2f} dBFS")
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
peak_final = np.max(np.abs(out))
print(f"  Scale         : {20*np.log10(scale):+.2f} dB")
print(f"  Final peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
assert peak_final <= 1.0

# ══════════════════════════════════════════════════════════════
#  SAVE
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  CHART
# ══════════════════════════════════════════════════════════════
print("\n── Chart ────────────────────────────────────────")

def smooth_spec(mono, nfft=131072, sm=100):
    n = min(nfft, len(mono))
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(mono[:n]*w, n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0/fs)
    db = 20*np.log10(sp+1e-9)
    return fr, np.convolve(db, np.ones(sm)/sm, mode="same")

mono_o  = (data[:,0]+data[:,1])/2
mono_v3 = sf.read(str(ROOT/"sound/wav_output/Slow_Piano_Jazz_v1_Fixed_v3.wav"))[0]
mono_v3 = (mono_v3[:,0]+mono_v3[:,1])/2 if mono_v3.ndim>1 else mono_v3
mono_v4 = (out[:,0]+out[:,1])/2

fr, db_o  = smooth_spec(mono_o)
_,  db_v3 = smooth_spec(mono_v3[:len(mono_o)])
_,  db_v4 = smooth_spec(mono_v4)

BG, PL, GR = "#0d0d0d", "#1a1a1a", "#2a2a2a"
C1, C2, C3 = "#7ec8e3", "#f472b6", "#34d399"

fig = plt.figure(figsize=(14, 10), facecolor=BG)
fig.suptitle("Slow Piano Jazz v1 — v3 (dry) vs v4 (fat restored)",
             color="#e0e0e0", fontsize=13, fontweight="bold")
gs = gridspec.GridSpec(2,1, hspace=0.42)

ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(PL); ax1.grid(True, color=GR, lw=0.4)
mask = (fr>=20)&(fr<=20000)
ax1.semilogx(fr[mask], db_o[mask],  color=C1, lw=1.0, alpha=0.6, linestyle="--", label="Original")
ax1.semilogx(fr[mask], db_v3[mask], color=C2, lw=1.2, alpha=0.8, label="v3 (dry)")
ax1.semilogx(fr[mask], db_v4[mask], color=C3, lw=1.5, alpha=0.9, label="v4 (fat restored)")
# Highlight fat zone and buzz zone
ax1.axvspan(80,  220,  color=C3,       alpha=0.07, label="FAT zone (80-220 Hz)")
ax1.axvspan(220, 500,  color="#ef4444",alpha=0.06, label="BUZZ zone (220-500 Hz)")
TICKS=[20,50,100,200,400,800,1000,2000,4000,8000,16000,20000]
TLABS=["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
ax1.set_xlim(20,20000)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Spectrum: зелёная зона = жир, красная = buzz", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(PL); ax2.grid(True, color=GR, lw=0.4)
d3 = np.convolve(db_v3-db_o, np.ones(80)/80, mode="same")
d4 = np.convolve(db_v4-db_o, np.ones(80)/80, mode="same")
ax2.semilogx(fr[mask], d3[mask], color=C2, lw=1.2, alpha=0.8, label="v3 − Original (dry)")
ax2.semilogx(fr[mask], d4[mask], color=C3, lw=1.5, alpha=0.9, label="v4 − Original (fat)")
ax2.axhline(0, color="#666", lw=0.7, linestyle="--")
ax2.fill_between(fr[mask], 0, d4[mask], where=(d4[mask]>0), color=C3, alpha=0.12)
ax2.fill_between(fr[mask], 0, d4[mask], where=(d4[mask]<0), color="#ef4444", alpha=0.10)
ax2.axvspan(80, 220, color=C3, alpha=0.06)
ax2.axvspan(220, 500, color="#ef4444", alpha=0.05)
ax2.set_xticks(TICKS); ax2.set_xticklabels(TLABS, fontsize=8)
ax2.set_xlim(20,20000); ax2.set_ylim(-10, 10)
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax2.set_ylabel("ΔdB", color="#888", fontsize=9)
ax2.set_title("EQ Correction: v3 vs v4  (зелёная зона = жир поднят, красная = buzz подавлен)", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

rms_v4 = 20*np.log10(np.sqrt(np.mean(mono_v4**2))+1e-9)
rms_o  = 20*np.log10(np.sqrt(np.mean(mono_o**2))+1e-9)
fig.text(0.5, 0.01,
    f"RMS: {rms_o:+.1f} → {rms_v4:+.1f} dBFS  |  "
    f"5-band MB Comp (80/220/500/2500 Hz)  |  "
    f"FAT boost +2dB @ 130Hz  |  Sustain shaper: ВЫКЛЮЧЕН  |  Peak: {20*np.log10(peak_final+1e-12):+.2f} dBFS",
    ha="center", va="bottom", fontsize=8, color="#aaa",
    bbox=dict(facecolor="#111", edgecolor="#333", alpha=0.8, pad=5))

out_chart = ROOT/"analysis"/"Slow_Piano_Jazz_v1_fix_v4_comparison.png"
plt.savefig(str(out_chart), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[CHART] {out_chart}")

rms_v4 = 20*np.log10(np.sqrt(np.mean(mono_v4**2))+1e-9)
print("\n" + "="*60)
print("  FIX v4 — REPORT")
print("="*60)
print(f"  Input   : {INPUT.name}  (ОРИГИНАЛ)")
print(f"  Output  : {OUTPUT.name}")
print(f"  RMS     : {rms_o:+.2f} → {rms_v4:+.2f} dBFS")
print(f"  Peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
print(f"  Low-body boost  : +2 dB @ 130 Hz  ← ЖИР")
print(f"  BUZZ comp band  : 220-500 Hz, ratio=2.0")
print(f"  FAT comp band   : 80-220 Hz, ratio=1.3  (почти не зажато)")
print(f"  Sustain shaper  : ВЫКЛЮЧЁН")
print("="*60)
print()
print("ЕСЛИ НУЖНА ПОДСТРОЙКА:")
print("  Ещё жирнее    → low-body boost: +2→+3 dB @ 130 Hz")
print("  Buzz вернулся → buzz band ratio: 2.0→2.5, thr: -23→-21 dB")
print("  Слипаются ноты→ включить sustain shaper -1.0 dB (строка в коде)")
print("  Бас мутный    → HP @ 25→40 Hz или band1 ratio: 1.3→1.5")
