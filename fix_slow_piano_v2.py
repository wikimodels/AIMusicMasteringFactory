"""
fix_slow_piano_v2.py
====================
ВЕРСИЯ 2 — после краша первой версии.

ЧТО БЫЛО НЕ ТАК В v1:
  ✗ +7 dB @ 8kHz + +4 dB @ 12kHz → там ничего нет (-42 dB) → поднял шумовой пол → ПЕСОК/ХРИ П
  ✗ tanh "soft limiter" — это сатуратор, не лимитер → ДИСТОШН
  ✗ 10 узких нотчей подряд через filtfilt → pre-ringing артефакты → ХРИПЫ
  ✗ Side 0.75 + bass mono → кастрация стерео → ОДНА НОЗДРЯ

НОВАЯ ФИЛОСОФИЯ:
  • Минимальное вмешательство — "не навреди"
  • Только САМЫЕ ЗЛОБНЫЕ резонансы (3 штуки, не 10)
  • Воздух: +3 dB @ 6kHz (не 8!) — там ещё есть реальный сигнал
  • Нормализация через простой peak scaling — никакого tanh
  • Стерео не трогаем (оставляем как есть)
  • Лимитер — честный hard clip ceiling, не сатурация
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as sig
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path

ROOT   = Path(__file__).parent
INPUT  = ROOT / "Slow piano Jazz v 1.wav"
OUTPUT = ROOT / "sound" / "wav_output" / "Slow_Piano_Jazz_v1_Fixed_v2.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print(f"Input  : {INPUT}")
print(f"Output : {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  BELL EQ (Audio-EQ-Cookbook)
# ══════════════════════════════════════════════════════════════
def make_bell(f0: float, Q: float, gain_db: float, fs: int):
    A     = 10 ** (gain_db / 40.0)
    w0    = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2.0 * Q)
    b = np.array([1 + alpha*A, -2*np.cos(w0), 1 - alpha*A])
    a = np.array([1 + alpha/A, -2*np.cos(w0), 1 - alpha/A])
    return b, a

def make_high_shelf(f0: float, gain_db: float, S: float, fs: int):
    A      = 10 ** (gain_db / 40.0)
    w0     = 2 * np.pi * f0 / fs
    alpha  = np.sin(w0) / 2.0 * np.sqrt((A + 1.0/A) * (1.0/S - 1.0) + 2.0)
    cos_w  = np.cos(w0)
    sq_A   = np.sqrt(A)
    b = np.array([
         A*((A+1) + (A-1)*cos_w + 2*sq_A*alpha),
        -2*A*((A-1) + (A+1)*cos_w),
         A*((A+1) + (A-1)*cos_w - 2*sq_A*alpha),
    ])
    a = np.array([
        (A+1) - (A-1)*cos_w + 2*sq_A*alpha,
        2*((A-1) - (A+1)*cos_w),
        (A+1) - (A-1)*cos_w - 2*sq_A*alpha,
    ])
    return b, a

def apply_zp(ch: np.ndarray, b, a) -> np.ndarray:
    """Zero-phase biquad. ТОЛЬКО для sharp notch. Для shelf — обычный lfilter."""
    return sig.filtfilt(b, a, ch)

def apply_causal(ch: np.ndarray, b, a) -> np.ndarray:
    """Каузальный фильтр — без pre-ringing. Для буста воздуха."""
    return sig.lfilter(b, a, ch)


# ══════════════════════════════════════════════════════════════
#  LOAD
# ══════════════════════════════════════════════════════════════
data, fs = sf.read(str(INPUT))
print(f"\nLoaded: sr={fs} Hz, shape={data.shape}, dur={len(data)/fs:.1f}s")

if data.ndim == 1:
    data = np.stack([data, data], axis=1)

data = data.astype(np.float64)
out = data.copy()

# ══════════════════════════════════════════════════════════════
#  ШАГИ ОБРАБОТКИ
# ══════════════════════════════════════════════════════════════
print("\n── EQ chain (v2 — minimal & surgical) ──────────")

# ─── ШАГ 1: High-pass @ 25 Hz (убираем DC и инфра) ─────────
# Мягкий, 2-й порядок — не кастрирует суббас
sos_hp = sig.butter(2, 25.0, "high", fs=fs, output="sos")
for ch in range(2):
    out[:, ch] = sig.sosfiltfilt(sos_hp, out[:, ch])
print("  [1] HP @ 25 Hz, 2-й порядок — DC/инфра")

# ─── ШАГ 2: Только 3 ХИРУРГИЧЕСКИХ нотча ──────────────────
# Только топ-3 реальных врага, с разумной глубиной.
# Q=10 — достаточно узко, не убивает соседей.
# Не используем filtfilt для широких вырезов — pre-ringing!
# Для Q >= 8 filtfilt безопасен (узкий фильтр, маленький импульс).

surgical = [
    # (freq, Q,  gain_dB,  description)
    (1990, 10, -8.0,  "Presence sting — самый злобный (+33 dB)"),
    (262,   8, -5.0,  "Low-mid mud (+30 dB)"),
    (662,   8, -4.0,  "Nasal box (+28 dB)"),
]

for f0, Q, gain, desc in surgical:
    b, a = make_bell(f0, Q, gain, fs)
    for ch in range(2):
        out[:, ch] = apply_zp(out[:, ch], b, a)
    print(f"  [Notch] {f0:4.0f} Hz  Q={Q}  {gain:+.0f} dB  — {desc}")

# ─── ШАГ 3: Broad low-mid tilt — снимаем общую грязь ───────
# ОЧЕНЬ широко (Q=0.4), совсем немного (-2 дБ).
# Не убивает пианино, только чуть выравнивает горб 200-500 Hz.
b_lm, a_lm = make_bell(350.0, 0.4, -2.0, fs)
for ch in range(2):
    out[:, ch] = apply_causal(out[:, ch], b_lm, a_lm)
print("  [3] Low-mid tilt @ 350 Hz  Q=0.4  -2 dB")

# ─── ШАГ 4: Presence restore @ 2.5 kHz ──────────────────────
# Возвращаем прозрачность пианинных нот. ШИРОКО, Q=0.6, +2 дБ.
b_pr, a_pr = make_bell(2500.0, 0.6, +2.0, fs)
for ch in range(2):
    out[:, ch] = apply_causal(out[:, ch], b_pr, a_pr)
print("  [4] Presence @ 2.5 kHz  Q=0.6  +2 dB")

# ─── ШАГ 5: Air shelf @ 5 kHz ────────────────────────────────
# КЛЮЧЕВОЕ ИЗМЕНЕНИЕ от v1:
# Начинаем подъём с 5 kHz (там ещё есть -30 dB реального сигнала)
# а не с 8 kHz (там -42 dB = шумовой пол).
# +3 дБ, мягкий shelf (S=0.5). Это открывает звук, но не создаёт песок.
b_air, a_air = make_high_shelf(5000.0, +3.0, 0.5, fs)
for ch in range(2):
    out[:, ch] = apply_causal(out[:, ch], b_air, a_air)
print("  [5] Air shelf @ 5 kHz  +3 dB  S=0.5 (мягкий)")

# ─── ШАГ 6: НЕТ harmonic exciter, НЕТ MS processing ─────────
# Стерео оставляем как есть — пианино само управляется с фазой.
# Экзайтер убрал — он создавал "песок" в мёртвом HF диапазоне.
print("  [6] Stereo: БЕЗ изменений (не трогаем фазу)")
print("  [7] Harmonic exciter: ВЫКЛЮЧЕН")

# ══════════════════════════════════════════════════════════════
#  НОРМАЛИЗАЦИЯ — честный peak scaling, никакого tanh
# ══════════════════════════════════════════════════════════════
print("\n── Normalization ────────────────────────────────")

peak_in  = np.max(np.abs(data))
peak_out = np.max(np.abs(out))
CEIL = 0.97   # -0.26 dBFS — стандартный запас

print(f"  Original peak : {20*np.log10(peak_in+1e-12):+.2f} dBFS")
print(f"  After EQ peak : {20*np.log10(peak_out+1e-12):+.2f} dBFS")

if peak_out > CEIL:
    gain = CEIL / peak_out
    out *= gain
    print(f"  Applied gain  : {20*np.log10(gain):.2f} dB (peak limiting)")
else:
    # EQ не поднял пик выше потолка — просто масштабируем к оригинальному уровню
    gain = peak_in / peak_out
    out *= gain
    print(f"  Level restore : {20*np.log10(gain):.2f} dB (вернули оригинальный уровень)")

peak_final = np.max(np.abs(out))
print(f"  Final peak    : {20*np.log10(peak_final+1e-12):+.2f} dBFS")

# Проверка — нет клиппинга
assert np.max(np.abs(out)) <= 1.0, "CLIP DETECTED — bug in normalization!"

# ══════════════════════════════════════════════════════════════
#  SAVE (24-bit WAV, 48 kHz)
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Saved: {OUTPUT}")

# ══════════════════════════════════════════════════════════════
#  BEFORE / AFTER CHART
# ══════════════════════════════════════════════════════════════
print("\n── Generating comparison chart ──────────────────")

def smooth_spectrum(audio_mono, n_fft=131072, smooth=100):
    n = min(n_fft, len(audio_mono))
    w = np.hanning(n)
    sp = np.abs(np.fft.rfft(audio_mono[:n] * w, n=n_fft))
    fr = np.fft.rfftfreq(n_fft, 1.0 / fs)
    db = 20 * np.log10(sp + 1e-9)
    k  = np.ones(smooth) / smooth
    return fr, np.convolve(db, k, mode="same")

mono_orig  = data[:, 0] / 2 + data[:, 1] / 2
mono_fixed = out[:, 0]  / 2 + out[:, 1]  / 2

fr, db_o = smooth_spectrum(mono_orig)
_,  db_f = smooth_spectrum(mono_fixed)

BG, PL, GR = "#0d0d0d", "#1a1a1a", "#2a2a2a"
C1, C2 = "#7ec8e3", "#f472b6"

fig = plt.figure(figsize=(14, 9), facecolor=BG)
fig.suptitle("Slow Piano Jazz v1 — Before vs After (v2)", color="#e0e0e0", fontsize=13, fontweight="bold")
gs = gridspec.GridSpec(2, 1, hspace=0.42)

# Top: spectrum overlay
ax1 = fig.add_subplot(gs[0])
ax1.set_facecolor(PL); ax1.grid(True, color=GR, lw=0.4)
mask = (fr >= 20) & (fr <= 20000)
ax1.semilogx(fr[mask], db_o[mask], color=C1, lw=1.4, alpha=0.85, label="Original")
ax1.semilogx(fr[mask], db_f[mask], color=C2, lw=1.4, alpha=0.85, label="Fixed v2")
diff = db_f - db_o
ax1.fill_between(fr[mask], db_o[mask], db_f[mask],
                 where=(diff[mask] > 0), color=C2, alpha=0.13, label="Boost")
ax1.fill_between(fr[mask], db_o[mask], db_f[mask],
                 where=(diff[mask] < 0), color="#ef4444", alpha=0.13, label="Cut")
TICKS = [20,50,100,200,400,800,1000,2000,4000,8000,16000,20000]
TLABS = ["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
ax1.set_xlim(20, 20000)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Full Spectrum Overlay", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

# Bottom: EQ diff curve
ax2 = fig.add_subplot(gs[1])
ax2.set_facecolor(PL); ax2.grid(True, color=GR, lw=0.4)
diff_s = np.convolve(diff, np.ones(80)/80, mode="same")
ax2.semilogx(fr[mask], diff_s[mask], color="#f59e0b", lw=1.5, label="EQ curve (Fixed − Original)")
ax2.axhline(0, color="#666", lw=0.7, linestyle="--")
ax2.fill_between(fr[mask], 0, diff_s[mask], where=(diff_s[mask] > 0), color=C2, alpha=0.15)
ax2.fill_between(fr[mask], 0, diff_s[mask], where=(diff_s[mask] < 0), color="#ef4444", alpha=0.15)
for f0, Q, gain, desc in surgical:
    ax2.axvline(f0, color="#ef4444", lw=0.7, linestyle=":", alpha=0.5)
    ax2.text(f0, -9, f"{f0:.0f}", color="#ef4444", fontsize=7, rotation=90, va="bottom", ha="right")
ax2.axvline(5000, color=C2, lw=0.7, linestyle=":", alpha=0.5)
ax2.text(5000, 0.2, "5k shelf", color=C2, fontsize=7, rotation=90, va="bottom", ha="right")
ax2.set_xticks(TICKS); ax2.set_xticklabels(TLABS, fontsize=8)
ax2.set_xlim(20, 20000)
ax2.set_ylim(-12, 8)
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax2.set_ylabel("ΔdB", color="#888", fontsize=9)
ax2.set_title("EQ Correction Curve", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

# Stats
rms_o = 20*np.log10(np.sqrt(np.mean(mono_orig**2)) + 1e-9)
rms_f = 20*np.log10(np.sqrt(np.mean(mono_fixed**2)) + 1e-9)
hf_m  = (fr >= 4000) & (fr <= 12000)
hf_o  = np.mean(db_o[hf_m])
hf_f  = np.mean(db_f[hf_m])
stats = (
    f"RMS: {rms_o:+.1f} → {rms_f:+.1f} dBFS  |  "
    f"HF 4k-12k avg: {hf_o:+.1f} → {hf_f:+.1f} dBFS  |  "
    f"Notches: 1990, 262, 662 Hz  |  Air shelf: +3 dB @ 5 kHz"
)
fig.text(0.5, 0.01, stats, ha="center", va="bottom", fontsize=8, color="#aaa",
         bbox=dict(facecolor="#111", edgecolor="#333", alpha=0.8, pad=5))

out_chart = ROOT / "analysis" / "Slow_Piano_Jazz_v1_fix_v2_comparison.png"
plt.savefig(str(out_chart), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"[CHART] {out_chart}")

# ══════════════════════════════════════════════════════════════
#  REPORT
# ══════════════════════════════════════════════════════════════
print("\n" + "="*60)
print("  FIX v2 — REPORT")
print("="*60)
print(f"  Input  : {INPUT.name}")
print(f"  Output : {OUTPUT.name}")
print(f"  RMS before : {rms_o:+.2f} dBFS")
print(f"  RMS after  : {rms_f:+.2f} dBFS  (Δ {rms_f-rms_o:+.1f} dB)")
print(f"  HF 4-12k before : {hf_o:+.1f} dB")
print(f"  HF 4-12k after  : {hf_f:+.1f} dB  (Δ {hf_f-hf_o:+.1f} dB)")
print(f"  True Peak final : {20*np.log10(peak_final+1e-12):+.2f} dBFS")
print(f"  Notches applied : 3 (не 10)")
print(f"  Exciter         : ВЫКЛЮЧЕН")
print(f"  Stereo          : НЕ ТРОНУТО")
print(f"  Limiter         : peak scaling (честный)")
print("="*60)
print()
print("ЧТО ИЗМЕНИЛОСЬ (v2 vs v1):")
print("  ✅ Воздух с 5 kHz (+3 dB) — там реальный сигнал, не шум")
print("  ✅ Только 3 нотча (не 10) — пианино звучит живым")
print("  ✅ Без экзайтера — без песка")
print("  ✅ Честная нормализация — без tanh дистошна")
print("  ✅ Стерео нетронуто — нет зажатости")
print()
print("ЕСЛИ ПОСЛЕ ПРОСЛУШИВАНИЯ:")
print("  Воздух не хватает → air shelf +3→+4 dB @ 5kHz")
print("  1990 Hz ещё бьёт  → notch gain -8→-10 dB, Q=12")
print("  Гнусавит @ 262 Hz → notch gain -5→-7 dB")
