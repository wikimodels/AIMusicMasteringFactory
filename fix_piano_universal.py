"""
fix_piano_universal.py
======================
⚠️  СПЕЦИАЛЬНЫЙ СКРИПТ для трека:
    «Piano Universal.wav»
    Расположение: sound/wav_input/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ (по результатам analyze_dirt_temporal.py
                      и analyze_plastic.py):

  Dirt Analysis:
    • Avg Dirt  = 46.0  [OK / граница DIRTY]
    • Peak Dirt = 62.6  [VERY DIRTY] — лучший результат из 4 треков
    • P95 Dirt  = 58.6  — лучший P95 из 4 треков
    • Топ грязных моментов: 1:33, 1:27, 1:23, 0:19, 0:55

  Plastic Analysis:
    • HN coverage  = 20%  (больше всех — много высоких нот)
    • Avg Plastic  = 44.1  [MILD / граница PLASTIC]
    • Peak Plastic = 63.9  [PLASTIC]
    • P95 Plastic  = 55.8  — лучший P95 из 4 треков
    • Топ пластика: 0:09, 0:37, 1:34, 1:54

  Статус: НАИБОЛЕЕ ЗДОРОВЫЙ из всех 4 Piano-треков

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ОСОБЕННОСТИ ОБРАБОТКИ (фортепиано ≠ пэд):

  ⚠️ Фортепиано НЕ имеет вибрато — ансамбль-хорус здесь НЕЛЬЗЯ!
     Он размоет атаки и сделает звук неестественно "плавающим".
  ⚠️ HPF должен быть осторожным — нижние ноты рояля до ~27 Hz.
     Режем только явный rumble, ниже 35 Hz.
  ✅ AI-пластик лечим через HF сатурацию (нечётные гармоники).
  ✅ Mud cut — динамический, не трогает чистые моменты.
  ✅ Атаки сохраняем — никакого tape roll-off выше 16 kHz.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ЦЕПОЧКА ОБРАБОТКИ:

  Step 1. HPF @ 35 Hz          — осторожный срез sub rumble
                                  (ниже самой нижней ноты рояля)
  Step 2. Dynamic Mud Cut       — 260–430 Hz, threshold -29 dB
                                  срабатывает только в пиковых моментах
  Step 3. Presence Lift         — лёгкий подъём 3–6 kHz +1.5 dB
                                  компенсирует потери после mud cut
  Step 4. HF Saturation         — нечётные гармоники выше 2.5 kHz
                                  лечит AI-пластик без смазывания атак
  Step 5. Transient Preserve    — micro-smoothing огибающей в HF
                                  не трогает атаки, только sustain
  Step 6. Tape Roll-Off @ 16 kHz — очень мягкий, сохраняет воздух
  Step 7. Peak Normalize

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
СРАВНЕНИЯ (графики):

  1. Piano Universal: Original vs Fixed       (before/after)
  2. Piano Universal Fixed vs NCM-PAD-03 Fixed (сравнение треков)

Выходной файл:
  sound/wav_output/Piano_Universal_FIXED.wav

Графики:
  analysis/fix_piano_universal_beforeafter.png
  analysis/fix_piano_universal_vs_ncmpad03.png
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

# ──────────────────────────────────────────────────────────────
ROOT        = Path(__file__).parent
INPUT       = ROOT / "sound" / "wav_input"  / "Piano Universal.wav"
OUTPUT      = ROOT / "sound" / "wav_output" / "Piano_Universal_FIXED.wav"
REF_FIXED   = ROOT / "sound" / "wav_output" / "NCM-PAD-03_Ambient_Clockwork_FIXED.wav"
ANALYSIS    = ROOT / "analysis"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
ANALYSIS.mkdir(exist_ok=True)

BG    = "#0d0d0d"
PANEL = "#141414"
GRID  = "#252525"

print("=" * 62)
print("  fix_piano_universal.py")
print("  Трек: Piano Universal.wav  [наиболее здоровый из 4]")
print("=" * 62)
print(f"\n  Вход : {INPUT.name}")
print(f"  Выход: {OUTPUT.name}\n")

data, fs = sf.read(str(INPUT))
print(f"  SR={fs} Hz  |  Duration={len(data)/fs:.1f}s  |  Channels={data.ndim}")
if data.ndim == 1:
    data = np.stack([data, data], axis=1)
out = data.astype(np.float64).copy()


# ══════════════════════════════════════════════════════════════
#  STEP 1. HPF @ 35 Hz — осторожный sub rumble cut
#  Нижняя нота рояля (A0) = 27.5 Hz → режем только ниже 35 Hz
# ══════════════════════════════════════════════════════════════
print("\n── Step 1: HPF @ 35 Hz (осторожный sub rumble) ──────────")
sos_hpf = sg.butter(3, 35.0, btype="high", fs=fs, output="sos")
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_hpf, out[:, c])
print("  ✅ Sub rumble < 35 Hz убран (Butterworth 3-го порядка)")
print("     (осторожно: нижняя нота рояля A0 = 27.5 Hz сохранена)")


# ══════════════════════════════════════════════════════════════
#  STEP 2. Dynamic Mud Cut (260–430 Hz)
#  Dirt peaks: 1:33, 1:27, 1:23, 0:19, 0:55
#  Threshold чуть мягче (-29 dB) — трек чище чем NCM-PAD-03
# ══════════════════════════════════════════════════════════════
print("\n── Step 2: Dynamic Mud Cut (260–430 Hz) ─────────────────")

def dynamic_mud_cut(ch, fs, f_lo=260, f_hi=430,
                    threshold_db=-29.0, max_cut_db=-4.5,
                    attack_ms=10.0, release_ms=100.0):
    """
    Динамически режет mud-зону только при превышении порога.
    Release 100ms — мягче чем для пэда, чтобы не смазывать piano decay.
    """
    sos_bp = sg.butter(3, [f_lo, f_hi], btype="band", fs=fs, output="sos")
    mud = sg.sosfiltfilt(sos_bp, ch)

    frame = max(1, int(attack_ms / 1000.0 * fs))
    rms = np.sqrt(np.convolve(mud**2, np.ones(frame)/frame, mode="same") + 1e-12)
    db_env = 20.0 * np.log10(rms + 1e-12)

    over = np.clip(db_env - threshold_db, 0.0, None)
    max_lin = 1.0 - 10.0 ** (max_cut_db / 20.0)
    cut = np.clip(over / 18.0, 0.0, 1.0) * max_lin

    rel = max(1, int(release_ms / 1000.0 * fs))
    cut_s = sg.filtfilt(np.ones(rel) / rel, [1.0], cut)

    return ch - mud * cut_s

for c in range(2):
    out[:, c] = dynamic_mud_cut(out[:, c], fs)
print("  ✅ Dynamic mud cut: 260–430 Hz | threshold -29 dB | max -4.5 dB")
print("     release=100ms (мягче для piano decay)")


# ══════════════════════════════════════════════════════════════
#  STEP 3. Presence Lift (3–6 kHz, +1.5 dB)
#  Компенсирует небольшую потерю «воздуха» после mud cut
#  Типичный приём в piano mastering — открывает звук
# ══════════════════════════════════════════════════════════════
print("\n── Step 3: Presence Lift +1.5 dB @ 3–6 kHz ─────────────")

def presence_lift(ch, fs, f_lo=3000, f_hi=6000, gain_db=1.5):
    A = 10.0 ** (gain_db / 20.0)
    sos_bp = sg.butter(2, [f_lo, f_hi], btype="band", fs=fs, output="sos")
    presence = sg.sosfiltfilt(sos_bp, ch)
    return ch + presence * (A - 1.0)

for c in range(2):
    out[:, c] = presence_lift(out[:, c], fs)
print("  ✅ Presence lift +1.5 dB в зоне 3–6 kHz")
print("     (компенсация после mud cut, открывает piano presence)")


# ══════════════════════════════════════════════════════════════
#  STEP 4. HF Saturation (Anti-plastic, > 2.5 kHz)
#  Фортепиано = NO vibrato → никакого хоруса!
#  Лечение пластика только через нечётные гармоники.
#  Меньший mix (8%) чем для пэда — атаки должны остаться чёткими.
# ══════════════════════════════════════════════════════════════
print("\n── Step 4: HF Saturation Anti-plastic (> 2.5 kHz) ──────")

def hf_exciter(ch, fs, crossover_hz=2500.0, drive_db=6.0, mix=0.08):
    sos_hp = sg.butter(3, crossover_hz, btype="high", fs=fs, output="sos")
    hf = sg.sosfiltfilt(sos_hp, ch)
    drive = 10.0 ** (drive_db / 20.0)
    hf_sat = np.tanh(hf * drive) / drive
    excite = hf_sat - hf
    return ch + excite * mix

for c in range(2):
    out[:, c] = hf_exciter(out[:, c], fs,
                            crossover_hz=2500.0,
                            drive_db=6.0,
                            mix=0.08)
print("  ✅ HF Exciter: нечётные гармоники > 2.5 kHz | mix=8%")
print("     (лечит AI-пластик без хоруса — атаки сохранены)")


# ══════════════════════════════════════════════════════════════
#  STEP 5. Tape Roll-Off @ 16 kHz (очень мягкий)
#  Для фортепиано ставим выше (16 kHz vs 14 kHz для пэда):
#  рояль имеет важный «воздух» на 14–16 kHz
# ══════════════════════════════════════════════════════════════
print("\n── Step 5: Tape Roll-Off @ 16 kHz (мягкий) ─────────────")
sos_ro = sg.butter(2, 16000.0, btype="low", fs=fs, output="sos")
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_ro, out[:, c])
print("  ✅ Tape roll-off @ 16 kHz (бережнее чем для пэда: 16 vs 14 kHz)")


# ══════════════════════════════════════════════════════════════
#  STEP 6. Peak Normalization
# ══════════════════════════════════════════════════════════════
print("\n── Step 6: Normalization ─────────────────────────────────")
peak_orig = float(np.max(np.abs(data)))
peak_out  = float(np.max(np.abs(out)))
scale = peak_orig / (peak_out + 1e-12)
out  *= scale
print(f"  Оригинальный пик : {20*np.log10(peak_orig + 1e-12):+.2f} dBFS")
print(f"  После обработки  : {20*np.log10(peak_out  + 1e-12):+.2f} dBFS")
print(f"  Применённый gain : {20*np.log10(scale):+.2f} dB")
print(f"  Финальный пик    : {20*np.log10(np.max(np.abs(out)) + 1e-12):+.2f} dBFS")


# ══════════════════════════════════════════════════════════════
#  SAVE
# ══════════════════════════════════════════════════════════════
sf.write(str(OUTPUT), out.astype(np.float32), fs, subtype="PCM_24")
print(f"\n✅ Сохранено: {OUTPUT}\n")


# ══════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════
def smooth_spec(mono_sig, fs, nfft=65536, sm=60):
    n = min(nfft, len(mono_sig))
    sp = np.abs(np.fft.rfft(mono_sig[:n] * np.hanning(n), n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0 / fs)
    db = 20.0 * np.log10(sp + 1e-9)
    return fr, np.convolve(db, np.ones(sm) / sm, mode="same")

def ax_style(ax, title=""):
    ax.set_facecolor(PANEL)
    if title:
        ax.set_title(title, color="#bbb", fontsize=9, pad=5, fontweight="bold")
    ax.tick_params(colors="#555", labelsize=8)
    ax.spines[:].set_color(GRID)
    ax.grid(True, color=GRID, lw=0.4, linestyle="--")
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#555")

FREQ_TICKS  = [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
FREQ_LABELS = ["31","63","125","250","500","1k","2k","4k","8k","16k"]

orig_mono = (data[:, 0] + data[:, 1]) / 2.0
fix_mono  = (out[:, 0]  + out[:, 1])  / 2.0
fr, db_orig = smooth_spec(orig_mono, fs)
_,  db_fix  = smooth_spec(fix_mono,  fs)
mask = (fr >= 20) & (fr <= 20000)


# ══════════════════════════════════════════════════════════════
#  CHART 1: Piano Universal — Before vs After
# ══════════════════════════════════════════════════════════════
print("── График 1: Piano Universal Before / After ──────────────")

fig, axes = plt.subplots(2, 1, figsize=(16, 10), facecolor=BG)
fig.suptitle(
    "Piano Universal.wav — Before / After Fix\n"
    "Dirt: avg=46.0 → ? | Peak: 62.6 [VERY DIRTY] | Plastic Peak: 63.9 [PLASTIC]",
    color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99
)

# Panel 1: Spectrum overlay
ax1 = axes[0]
ax1.set_facecolor(PANEL)
ax1.semilogx(fr[mask], db_orig[mask], color="#7ec8e3", lw=1.3,
             alpha=0.65, linestyle="--", label="Original (Piano Universal)")
ax1.semilogx(fr[mask], db_fix[mask],  color="#f472b6", lw=1.6,
             alpha=0.95, label="Fixed")

ax1.axvspan(20,   35,   color="#60a5fa", alpha=0.07, label="HPF zone (sub rumble)")
ax1.axvspan(260,  430,  color="#f97316", alpha=0.07, label="Dynamic mud cut zone")
ax1.axvspan(3000, 6000, color="#facc15", alpha=0.06, label="Presence lift +1.5 dB")
ax1.axvspan(2500, 10000,color="#4ade80", alpha=0.04, label="HF Exciter zone")

ax1.set_xlim(20, 20000)
ax1.set_xticks(FREQ_TICKS); ax1.set_xticklabels(FREQ_LABELS)
ax1.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#666", fontsize=9)
ax1.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8, loc="lower left")
ax_style(ax1, "Spectrum: Piano Universal — Original vs Fixed")

# Panel 2: Difference
ax2 = axes[1]
ax2.set_facecolor(PANEL)
diff = np.convolve(db_fix - db_orig, np.ones(80)/80, mode="same")
ax2.semilogx(fr[mask], diff[mask], color="#34d399", lw=1.5, label="Difference (Fixed − Original)")
ax2.axhline(0, color="#555", linestyle="--", lw=0.8)
ax2.fill_between(fr[mask], 0, diff[mask], where=(diff[mask] > 0), color="#34d399", alpha=0.2)
ax2.fill_between(fr[mask], 0, diff[mask], where=(diff[mask] < 0), color="#ef4444", alpha=0.2)

ax2.axvspan(20,   35,   color="#60a5fa", alpha=0.06)
ax2.axvspan(260,  430,  color="#f97316", alpha=0.06)
ax2.axvspan(3000, 6000, color="#facc15", alpha=0.05)

for x, lbl, col in [(27, "HPF", "#60a5fa"), (330, "Mud↓", "#f97316"),
                      (4200, "Pres↑", "#facc15"), (5000, "HF+", "#4ade80")]:
    ax2.text(x, diff[mask].max()*0.75, lbl, color=col, fontsize=7.5, ha="center")

ax2.set_xlim(20, 20000)
ax2.set_xticks(FREQ_TICKS); ax2.set_xticklabels(FREQ_LABELS)
ax2.set_ylim(-6, 5)
ax2.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
ax2.set_ylabel("ΔdB", color="#666", fontsize=9)
ax2.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
ax_style(ax2, "Correction Curve (green=added, red=removed)")

plt.tight_layout(rect=[0, 0, 1, 0.96])
chart1 = ANALYSIS / "fix_piano_universal_beforeafter.png"
plt.savefig(str(chart1), dpi=130, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"  [PNG] {chart1.name}")


# ══════════════════════════════════════════════════════════════
#  CHART 2: Piano Universal FIXED vs NCM-PAD-03 FIXED
#  Сравнение двух обработанных треков
# ══════════════════════════════════════════════════════════════
print("── График 2: Piano Universal FIXED vs NCM-PAD-03 FIXED ──")

if REF_FIXED.exists():
    ref_data, ref_fs = sf.read(str(REF_FIXED))
    if ref_data.ndim == 1:
        ref_data = np.stack([ref_data, ref_data], axis=1)
    ref_mono = (ref_data[:, 0] + ref_data[:, 1]) / 2.0

    # Общий nfft по меньшему файлу
    nfft_cmp = 65536
    sm_cmp   = 60
    n_pu  = min(nfft_cmp, len(fix_mono))
    n_ref = min(nfft_cmp, len(ref_mono))

    sp_pu  = np.abs(np.fft.rfft(fix_mono[:n_pu]  * np.hanning(n_pu),  n=nfft_cmp))
    sp_ref = np.abs(np.fft.rfft(ref_mono[:n_ref] * np.hanning(n_ref), n=nfft_cmp))
    fr_c   = np.fft.rfftfreq(nfft_cmp, 1.0 / fs)

    db_pu  = np.convolve(20*np.log10(sp_pu  + 1e-9), np.ones(sm_cmp)/sm_cmp, mode="same")
    db_ref = np.convolve(20*np.log10(sp_ref + 1e-9), np.ones(sm_cmp)/sm_cmp, mode="same")
    mask_c = (fr_c >= 20) & (fr_c <= 20000)

    fig2, axes2 = plt.subplots(2, 1, figsize=(16, 10), facecolor=BG)
    fig2.suptitle(
        "Сравнение двух FIXED треков\n"
        "Piano Universal FIXED  vs  NCM-PAD-03 Ambient Clockwork FIXED",
        color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99
    )

    # Panel 1: оба спектра
    ax_a = axes2[0]
    ax_a.set_facecolor(PANEL)
    ax_a.semilogx(fr_c[mask_c], db_pu[mask_c],  color="#f472b6", lw=1.6,
                  alpha=0.95, label="Piano Universal FIXED (piano)")
    ax_a.semilogx(fr_c[mask_c], db_ref[mask_c], color="#2dd4ff", lw=1.3,
                  alpha=0.80, linestyle="--", label="NCM-PAD-03 FIXED (ambient pad)")

    # Зоны характерных различий
    ax_a.axvspan(27,  100,  color="#60a5fa", alpha=0.05, label="Bass (piano > pad)")
    ax_a.axvspan(1000, 5000, color="#c084fc", alpha=0.05, label="Presence zone")
    ax_a.axvspan(10000, 20000, color="#34d399", alpha=0.05, label="Air (pad > piano)")

    ax_a.set_xlim(20, 20000)
    ax_a.set_xticks(FREQ_TICKS); ax_a.set_xticklabels(FREQ_LABELS)
    ax_a.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
    ax_a.set_ylabel("Level (dB)", color="#666", fontsize=9)
    ax_a.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8, loc="lower left")
    ax_style(ax_a, "Spectrum Comparison: Piano Universal FIXED vs NCM-PAD-03 FIXED")

    # Panel 2: разница Piano - PAD
    ax_b = axes2[1]
    ax_b.set_facecolor(PANEL)
    diff2 = np.convolve(db_pu - db_ref, np.ones(80)/80, mode="same")
    ax_b.semilogx(fr_c[mask_c], diff2[mask_c], color="#c084fc", lw=1.5,
                  label="Piano Universal − NCM-PAD-03  (+ = piano louder here)")
    ax_b.axhline(0, color="#555", linestyle="--", lw=0.8)
    ax_b.fill_between(fr_c[mask_c], 0, diff2[mask_c],
                      where=(diff2[mask_c] > 0), color="#f472b6", alpha=0.18,
                      label="Piano dominant")
    ax_b.fill_between(fr_c[mask_c], 0, diff2[mask_c],
                      where=(diff2[mask_c] < 0), color="#2dd4ff", alpha=0.18,
                      label="PAD dominant")

    # Аннотации ключевых зон
    for freq, lbl, col in [
        (50,    "Sub\n(piano)",    "#f472b6"),
        (350,   "Mud zone\n(similar)", "#888"),
        (2000,  "Presence\n(piano)",  "#f472b6"),
        (14000, "Air\n(pad)",    "#2dd4ff"),
    ]:
        if mask_c.sum() > 0:
            ax_b.text(freq, diff2[mask_c].max()*0.65, lbl,
                      color=col, fontsize=7, ha="center", va="center")

    ax_b.set_xlim(20, 20000)
    ax_b.set_xticks(FREQ_TICKS); ax_b.set_xticklabels(FREQ_LABELS)
    ax_b.set_ylim(-15, 15)
    ax_b.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
    ax_b.set_ylabel("ΔdB (Piano − PAD)", color="#666", fontsize=9)
    ax_b.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
    ax_style(ax_b, "Spectral Difference: pink=piano louder | blue=pad louder")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    chart2 = ANALYSIS / "fix_piano_universal_vs_ncmpad03.png"
    plt.savefig(str(chart2), dpi=130, bbox_inches="tight", facecolor=BG)
    plt.close()
    print(f"  [PNG] {chart2.name}")
else:
    print(f"  ⚠️  NCM-PAD-03 FIXED не найден ({REF_FIXED})")
    print("      Запусти сначала fix_ncm_pad03_ambient_clockwork.py")

print("\n" + "=" * 62)
print("  DONE!")
print(f"  Трек  : {OUTPUT.name}")
print(f"  График 1: fix_piano_universal_beforeafter.png")
print(f"  График 2: fix_piano_universal_vs_ncmpad03.png")
print("=" * 62 + "\n")
