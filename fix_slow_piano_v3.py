"""
fix_slow_piano_v3.py
====================
ВЕРСИЯ 3 — multiband compressor + sustain shaper.

ЧТО ПОКАЗАЛ АНАЛИЗ (analyze_piano_buzz.py):
  • Дребезжание — НЕ резонанс, НЕ intermod с контрабасом (corr=0.00)
  • Это ШИРОКОПОЛОСНЫЙ ПОДЪЁМ при forte: Suno симулирует
    "sympathetic string resonance" слишком агрессивно.
    На forte активируется весь спектр 30Hz–3kHz разом.
  • Sustain decay длинный — ноты "сливаются" (AI-реверб)
  • Атаки чёткие (P90=0.055) — трогать не нужно

ПЛАН v3:
  1. Те же 3 нотча что в v2 (1990, 262, 662 Hz)
  2. Air shelf +3 dB @ 5kHz (как v2)
  3. MULTIBAND COMPRESSOR — 4 полосы через Linkwitz-Riley кроссовер
     • Давим именно динамический рост тела пиано на forte
     • Мягко (ratio 2:1..2.5:1), slow attack — трансиент не трогаем
  4. SUSTAIN SHAPER — укорачиваем AI-реверб хвост без touch атаки
  5. Честная нормализация

INPUT:  Slow piano Jazz v 1.wav  (ОРИГИНАЛ)
OUTPUT: Slow_Piano_Jazz_v1_Fixed_v3.wav
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
OUTPUT = ROOT / "sound" / "wav_output" / "Slow_Piano_Jazz_v1_Fixed_v3.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT}")
print(f"Output : {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  FILTER UTILITIES
# ══════════════════════════════════════════════════════════════

def make_bell(f0, Q, gain_db, fs):
    A     = 10 ** (gain_db / 40.0)
    w0    = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2.0 * Q)
    b = np.array([1+alpha*A, -2*np.cos(w0), 1-alpha*A])
    a = np.array([1+alpha/A, -2*np.cos(w0), 1-alpha/A])
    return b, a

def make_high_shelf(f0, gain_db, S, fs):
    A     = 10 ** (gain_db / 40.0)
    w0    = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / 2.0 * np.sqrt((A + 1.0/A)*(1.0/S - 1.0) + 2.0)
    cos_w = np.cos(w0); sq = np.sqrt(A)
    b = np.array([A*((A+1)+(A-1)*cos_w+2*sq*alpha),
                  -2*A*((A-1)+(A+1)*cos_w),
                  A*((A+1)+(A-1)*cos_w-2*sq*alpha)])
    a = np.array([(A+1)-(A-1)*cos_w+2*sq*alpha,
                  2*((A-1)-(A+1)*cos_w),
                  (A+1)-(A-1)*cos_w-2*sq*alpha])
    return b, a

def lr2_lowpass(fc, fs):
    """Linkwitz-Riley LP (2-й порядок × 2 = 4-й порядок, flat sum с HP)."""
    sos = sg.butter(2, fc, 'low',  fs=fs, output='sos')
    return np.vstack([sos, sos])   # cascade

def lr2_highpass(fc, fs):
    sos = sg.butter(2, fc, 'high', fs=fs, output='sos')
    return np.vstack([sos, sos])

# ══════════════════════════════════════════════════════════════
#  COMPRESSOR ENGINE
#  (sample-by-sample gain computer с attack/release smoothing)
# ══════════════════════════════════════════════════════════════

def compress_channel(ch: np.ndarray,
                     fs: int,
                     threshold_db: float,
                     ratio: float,
                     attack_ms: float,
                     release_ms: float,
                     makeup_db: float = 0.0) -> np.ndarray:
    """
    Классический feed-forward peak compressor.
    attack_ms  — время нарастания огибающей (быстро = давим трансиент, медленно = пропускаем)
    release_ms — время спада  (медленно = плавно отпускаем хвост)
    """
    N       = len(ch)
    att     = np.exp(-1.0 / (fs * attack_ms  / 1000.0))
    rel     = np.exp(-1.0 / (fs * release_ms / 1000.0))
    thr_lin = 10 ** (threshold_db / 20.0)
    makeup  = 10 ** (makeup_db / 20.0)

    env = 0.0
    gain_arr = np.ones(N)
    abs_ch = np.abs(ch)

    for i in range(N):
        x = abs_ch[i]
        # Envelope follower
        if x > env:
            env = att * env + (1.0 - att) * x
        else:
            env = rel * env + (1.0 - rel) * x

        # Gain computer
        if env > thr_lin:
            gain_reduction = (thr_lin * (env / thr_lin) ** (1.0 / ratio)) / env
        else:
            gain_reduction = 1.0

        gain_arr[i] = gain_reduction * makeup

    return ch * gain_arr


def compress_channel_fast(ch: np.ndarray,
                           fs: int,
                           threshold_db: float,
                           ratio: float,
                           attack_ms: float,
                           release_ms: float,
                           makeup_db: float = 0.0) -> np.ndarray:
    """
    Векторизованная версия через RMS-огибающую (быстрее, чуть мягче).
    Используем для медленных band (>20ms attack) где sample-accurate не нужен.
    """
    # RMS envelope через скользящий фильтр
    frame = max(1, int(attack_ms / 1000.0 * fs))
    sq = ch ** 2
    kernel = np.ones(frame) / frame
    rms_env = np.sqrt(np.convolve(sq, kernel, mode='same') + 1e-12)

    thr_lin = 10 ** (threshold_db / 20.0)
    makeup  = 10 ** (makeup_db / 20.0)

    # Gain computer (vectorized)
    gain = np.where(
        rms_env > thr_lin,
        (thr_lin * (rms_env / thr_lin) ** (1.0 / ratio)) / rms_env,
        1.0
    )

    # Smooth gain с attack/release
    att = np.exp(-1.0 / (fs * attack_ms  / 1000.0))
    rel = np.exp(-1.0 / (fs * release_ms / 1000.0))

    gain_smooth = np.zeros_like(gain)
    g = 1.0
    for i in range(len(gain)):
        target = gain[i]
        if target < g:
            g = att * g + (1.0 - att) * target
        else:
            g = rel * g + (1.0 - rel) * target
        gain_smooth[i] = g

    return ch * gain_smooth * makeup


# ══════════════════════════════════════════════════════════════
#  SUSTAIN SHAPER
#  Укорачиваем AI-хвост без касания атаки
# ══════════════════════════════════════════════════════════════

def sustain_shaper(ch: np.ndarray, fs: int,
                   attack_ms: float = 8.0,
                   release_ms: float = 300.0,
                   sustain_reduction_db: float = -2.5) -> np.ndarray:
    """
    Двойная огибающая: быстрая (peak) и медленная (sustain).
    Когда slow_env значительно выше fast_peak — мы в sustain-зоне.
    Там применяем мягкое gain reduction.

    attack_ms  — скорость быстрой огибающей (детектирует атаку)
    release_ms — скорость медленной огибающей (отслеживает хвост)
    sustain_reduction_db — максимальное ослабление хвоста
    """
    att_fast = np.exp(-1.0 / (fs * attack_ms  / 1000.0))
    rel_slow = np.exp(-1.0 / (fs * release_ms / 1000.0))
    reduction = 10 ** (sustain_reduction_db / 20.0)

    abs_ch = np.abs(ch)
    env_fast = 0.0
    env_slow = 0.0
    gain_arr = np.ones(len(ch))

    for i in range(len(ch)):
        x = abs_ch[i]
        # Быстрая огибающая — ловит атаку
        if x > env_fast:
            env_fast = x  # instant attack
        else:
            env_fast *= att_fast

        # Медленная огибающая — ловит хвост
        if x > env_slow:
            env_slow = x
        else:
            env_slow = rel_slow * env_slow + (1.0 - rel_slow) * x

        # Если медленная >> быстрой: мы в хвосте
        # ratio > 1 => fast_env collapsed, slow_env still up => sustain
        if env_fast > 1e-7 and env_slow > 1e-7:
            tail_ratio = env_slow / (env_fast + 1e-7)
            if tail_ratio > 2.0:  # в хвосте (fast упал в 2+ раза)
                # Плавное применение ослабления
                strength = min(1.0, (tail_ratio - 2.0) / 3.0)
                gain_arr[i] = 1.0 - strength * (1.0 - reduction)

    return ch * gain_arr


# ══════════════════════════════════════════════════════════════
#  LOAD ORIGINAL
# ══════════════════════════════════════════════════════════════
data, fs = sf.read(str(INPUT))
print(f"\nLoaded ORIGINAL: sr={fs} Hz, shape={data.shape}, dur={len(data)/fs:.1f}s")

if data.ndim == 1:
    data = np.stack([data, data], axis=1)
data = data.astype(np.float64)
out = data.copy()

# ══════════════════════════════════════════════════════════════
#  ШАГ 1: SURGICAL EQ (те же 3 нотча + воздух, как v2)
# ══════════════════════════════════════════════════════════════
print("\n── [1] Surgical EQ ──────────────────────────────")

sos_hp = sg.butter(2, 25.0, "high", fs=fs, output="sos")
for ch in range(2):
    out[:, ch] = sg.sosfiltfilt(sos_hp, out[:, ch])
print("  HP @ 25 Hz")

surgical = [
    (1990, 10, -8.0, "Presence sting"),
    (262,   8, -5.0, "Low-mid mud"),
    (662,   8, -4.0, "Nasal box"),
]
for f0, Q, gain, desc in surgical:
    b, a = make_bell(f0, Q, gain, fs)
    for ch in range(2):
        out[:, ch] = sg.filtfilt(b, a, out[:, ch])
    print(f"  Notch {f0:.0f} Hz  Q={Q}  {gain:+.0f} dB  [{desc}]")

b_lm, a_lm = make_bell(350.0, 0.4, -2.0, fs)
for ch in range(2):
    out[:, ch] = sg.lfilter(b_lm, a_lm, out[:, ch])
print("  Low-mid tilt @ 350 Hz  -2 dB")

b_air, a_air = make_high_shelf(5000.0, +3.0, 0.5, fs)
for ch in range(2):
    out[:, ch] = sg.lfilter(b_air, a_air, out[:, ch])
print("  Air shelf @ 5 kHz  +3 dB")

# ══════════════════════════════════════════════════════════════
#  ШАГ 2: MULTIBAND COMPRESSOR
#  Linkwitz-Riley кроссовер → независимая компрессия → сумма
#  Crossover points: 120 Hz, 500 Hz, 2500 Hz
#
#  Band 1 (20–120 Hz)    : контрабас — мягко, сохраняем тело
#  Band 2 (120–500 Hz)   : piano body + buzz zone — основная цель
#  Band 3 (500–2500 Hz)  : piano mids + sympathetic resonance
#  Band 4 (2500+ Hz)     : presence + air — не давим
# ══════════════════════════════════════════════════════════════
print("\n── [2] Multiband Compressor ─────────────────────")

XOVER1, XOVER2, XOVER3 = 120.0, 500.0, 2500.0

# Linkwitz-Riley фильтры
sos_lp1 = lr2_lowpass(XOVER1, fs)
sos_hp1 = lr2_highpass(XOVER1, fs)
sos_lp2 = lr2_lowpass(XOVER2, fs)
sos_hp2 = lr2_highpass(XOVER2, fs)
sos_lp3 = lr2_lowpass(XOVER3, fs)
sos_hp3 = lr2_highpass(XOVER3, fs)

# Параметры компрессора для каждой полосы
# attack медленный = трансиент проходит, давим только sustain/body buzz
BAND_PARAMS = {
    1: dict(threshold_db=-22, ratio=1.5, attack_ms=40, release_ms=200, makeup_db=0.0),
    2: dict(threshold_db=-24, ratio=2.5, attack_ms=30, release_ms=180, makeup_db=0.5),  # главная цель
    3: dict(threshold_db=-26, ratio=2.0, attack_ms=20, release_ms=150, makeup_db=0.3),
    4: dict(threshold_db=-30, ratio=1.2, attack_ms=10, release_ms=100, makeup_db=0.0),
}

out_mb = np.zeros_like(out)

for ch_idx in range(2):
    ch = out[:, ch_idx]

    # Разделяем на 4 полосы через LR кроссовер
    b1 = sg.sosfiltfilt(sos_lp1, ch)                                # 20–120 Hz
    hi = sg.sosfiltfilt(sos_hp1, ch)
    b2 = sg.sosfiltfilt(sos_lp2, hi)                                # 120–500 Hz
    hi = sg.sosfiltfilt(sos_hp2, hi)
    b3 = sg.sosfiltfilt(sos_lp3, hi)                                # 500–2500 Hz
    b4 = sg.sosfiltfilt(sos_hp3, hi)                                # 2500+ Hz

    # Компрессия каждой полосы
    b1c = compress_channel_fast(b1, fs, **BAND_PARAMS[1])
    b2c = compress_channel_fast(b2, fs, **BAND_PARAMS[2])
    b3c = compress_channel_fast(b3, fs, **BAND_PARAMS[3])
    b4c = compress_channel_fast(b4, fs, **BAND_PARAMS[4])

    # Сумма полос (LR кроссовер — идеально плоская сумма)
    out_mb[:, ch_idx] = b1c + b2c + b3c + b4c

    label = "L" if ch_idx == 0 else "R"
    print(f"  [OK] Channel {label}: bands compressed")

print(f"  Band 1 (20–120 Hz)   : ratio={BAND_PARAMS[1]['ratio']}  thr={BAND_PARAMS[1]['threshold_db']} dB  att={BAND_PARAMS[1]['attack_ms']}ms")
print(f"  Band 2 (120–500 Hz)  : ratio={BAND_PARAMS[2]['ratio']}  thr={BAND_PARAMS[2]['threshold_db']} dB  att={BAND_PARAMS[2]['attack_ms']}ms  ← BUZZ ZONE")
print(f"  Band 3 (500–2500 Hz) : ratio={BAND_PARAMS[3]['ratio']}  thr={BAND_PARAMS[3]['threshold_db']} dB  att={BAND_PARAMS[3]['attack_ms']}ms")
print(f"  Band 4 (2500+ Hz)    : ratio={BAND_PARAMS[4]['ratio']}  thr={BAND_PARAMS[4]['threshold_db']} dB  att={BAND_PARAMS[4]['attack_ms']}ms")

out = out_mb

# ══════════════════════════════════════════════════════════════
#  ШАГ 3: SUSTAIN SHAPER
#  Укорачиваем AI-хвост → ноты перестанут сливаться
#  sustain_reduction = -2.5 dB в зоне хвоста — мягко
# ══════════════════════════════════════════════════════════════
print("\n── [3] Sustain Shaper ───────────────────────────")

for ch_idx in range(2):
    out[:, ch_idx] = sustain_shaper(
        out[:, ch_idx], fs,
        attack_ms=8.0,
        release_ms=280.0,
        sustain_reduction_db=-2.5
    )
    label = "L" if ch_idx == 0 else "R"
    print(f"  [OK] Channel {label}: sustain -2.5 dB in tail zone")

print("  Attack intact | Release tail gently reduced")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ — честный peak scaling
# ══════════════════════════════════════════════════════════════
print("\n── Normalization ────────────────────────────────")
peak_orig = np.max(np.abs(data))
peak_out  = np.max(np.abs(out))
print(f"  Original peak : {20*np.log10(peak_orig+1e-12):+.2f} dBFS")
print(f"  After proc    : {20*np.log10(peak_out+1e-12):+.2f} dBFS")

# Восстанавливаем оригинальный уровень пика
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
peak_final = np.max(np.abs(out))
print(f"  Scale applied : {20*np.log10(scale):+.2f} dB")
print(f"  Final peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")

assert np.max(np.abs(out)) <= 1.0, "CLIP BUG"

# ══════════════════════════════════════════════════════════════
#  SAVE
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  COMPARISON CHART
# ══════════════════════════════════════════════════════════════
print("\n── Chart ────────────────────────────────────────")

def smooth_spec(audio_mono, nfft=131072, sm=100):
    n = min(nfft, len(audio_mono))
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(audio_mono[:n]*w, n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0/fs)
    db = 20*np.log10(sp+1e-9)
    return fr, np.convolve(db, np.ones(sm)/sm, mode="same")

mono_orig  = (data[:, 0] + data[:, 1]) / 2.0
mono_v2    = sf.read(str(ROOT/"sound/wav_output/Slow_Piano_Jazz_v1_Fixed_v2.wav"))[0]
mono_v2    = (mono_v2[:, 0] + mono_v2[:, 1]) / 2.0 if mono_v2.ndim > 1 else mono_v2
mono_fixed = (out[:, 0] + out[:, 1]) / 2.0

fr, db_o  = smooth_spec(mono_orig)
_,  db_v2 = smooth_spec(mono_v2[:len(mono_orig)])
_,  db_v3 = smooth_spec(mono_fixed)

BG, PL, GR = "#0d0d0d", "#1a1a1a", "#2a2a2a"
C1, C2, C3 = "#7ec8e3", "#f472b6", "#34d399"

fig = plt.figure(figsize=(14, 10), facecolor=BG)
fig.suptitle("Slow Piano Jazz v1 — v2 vs v3 (Multiband + Sustain Shaper)", 
             color="#e0e0e0", fontsize=13, fontweight="bold")
gs = gridspec.GridSpec(2, 1, hspace=0.42)

ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(PL); ax1.grid(True, color=GR, lw=0.4)
mask = (fr >= 20) & (fr <= 20000)
ax1.semilogx(fr[mask], db_o[mask],  color=C1, lw=1.2, alpha=0.7, label="Original", linestyle="--")
ax1.semilogx(fr[mask], db_v2[mask], color=C2, lw=1.2, alpha=0.8, label="v2 (EQ only)")
ax1.semilogx(fr[mask], db_v3[mask], color=C3, lw=1.5, alpha=0.9, label="v3 (EQ + MB Comp + Sustain)")
# Band zones
for lo, hi, lbl, col in [(20,120,"Bass",C1),(120,500,"Body\nBuzz",C2),(500,2500,"Mid",C3),(2500,20000,"Air","#818cf8")]:
    ax1.axvspan(lo, hi, color=col, alpha=0.04)
    ax1.text((lo*hi)**0.5, -95, lbl, color=col, fontsize=7, ha='center', alpha=0.7)
ax1.axvspan(120, 500, color=C2, alpha=0.06, label="Buzz zone (MB comp band 2)")
TICKS=[20,50,100,200,400,800,1000,2000,4000,8000,16000,20000]
TLABS=["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
ax1.set_xlim(20, 20000)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Original vs v2 vs v3 — Full Spectrum", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(PL); ax2.grid(True, color=GR, lw=0.4)
diff_v2 = np.convolve(db_v2 - db_o, np.ones(80)/80, mode="same")
diff_v3 = np.convolve(db_v3 - db_o, np.ones(80)/80, mode="same")
ax2.semilogx(fr[mask], diff_v2[mask], color=C2, lw=1.2, alpha=0.8, label="v2 − Original")
ax2.semilogx(fr[mask], diff_v3[mask], color=C3, lw=1.5, alpha=0.9, label="v3 − Original")
ax2.axhline(0, color="#666", lw=0.7, linestyle="--")
ax2.fill_between(fr[mask], 0, diff_v3[mask],
                 where=(diff_v3[mask] > 0), color=C3, alpha=0.1)
ax2.fill_between(fr[mask], 0, diff_v3[mask],
                 where=(diff_v3[mask] < 0), color="#ef4444", alpha=0.1)
ax2.set_xticks(TICKS); ax2.set_xticklabels(TLABS, fontsize=8)
ax2.set_xlim(20, 20000); ax2.set_ylim(-12, 8)
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax2.set_ylabel("ΔdB", color="#888", fontsize=9)
ax2.set_title("EQ Correction Curves (v2 and v3 vs Original)", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

rms_o  = 20*np.log10(np.sqrt(np.mean(mono_orig**2))+1e-9)
rms_v3 = 20*np.log10(np.sqrt(np.mean(mono_fixed**2))+1e-9)
fig.text(0.5, 0.01,
    f"RMS: {rms_o:+.1f} → {rms_v3:+.1f} dBFS  |  "
    f"4-band MB Comp (120/500/2500 Hz xover)  |  "
    f"Sustain shaper: -2.5 dB tail  |  Peak: {20*np.log10(peak_final+1e-12):+.2f} dBFS",
    ha="center", va="bottom", fontsize=8, color="#aaa",
    bbox=dict(facecolor="#111", edgecolor="#333", alpha=0.8, pad=5))

out_chart = ROOT / "analysis" / "Slow_Piano_Jazz_v1_fix_v3_comparison.png"
plt.savefig(str(out_chart), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[CHART] {out_chart}")

print("\n" + "="*60)
print("  FIX v3 — REPORT")
print("="*60)
print(f"  Input   : {INPUT.name}  (ОРИГИНАЛ)")
print(f"  Output  : {OUTPUT.name}")
print(f"  RMS     : {rms_o:+.2f} → {rms_v3:+.2f} dBFS  (Δ {rms_v3-rms_o:+.1f} dB)")
print(f"  Peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
print(f"  EQ notches      : 3 (1990, 262, 662 Hz)")
print(f"  MB Comp bands   : 4 (LR xover: 120/500/2500 Hz)")
print(f"  Sustain shaper  : -2.5 dB хвост, attack нетронут")
print(f"  Stereo          : НЕ ТРОНУТО")
print("="*60)
print()
print("ОЖИДАЕМЫЙ РЕЗУЛЬТАТ:")
print("  ✅ Дребезжание на forte — подавлено MB comp band 2 (120-500 Hz)")
print("  ✅ Слияние нот — sustain shaper укорачивает AI-хвост")
print("  ✅ Мягкость пиано — медленный attack (30ms) пропускает felt-удар")
print("  ✅ Контрабас не зажат — band 1 ratio=1.5 (почти прозрачен)")
print("  ✅ Воздух открыт — shelf +3 dB @ 5kHz без шума")
print()
print("ЕСЛИ НУЖНА ПОДСТРОЙКА:")
print("  Дребезг остался  → band2 ratio: 2.5→3.0, threshold: -24→-22 dB")
print("  Ноты слипаются   → sustain_reduction: -2.5→-4.0 dB")
print("  Тихо/зажато      → makeup_db band2: 0.5→1.0 dB")
print("  Бас стал тонким  → band1 ratio: 1.5→1.2")
