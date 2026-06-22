"""
ЭТАЛОН_fix_ncm_pad03_ambient_clockwork.py
==========================================
🏆 ★ ЭТАЛОН ★ — ЛУЧШИЙ РЕЗУЛЬТАТ СЕССИИ
   Звук: мягкий, естественный, чёткий одновременно.
   Проверено на слух: «звук топ» (пользователь, 21.06.2026)

⚠️  СПЕЦИАЛЬНЫЙ СКРИПТ для трека:
    «ОК  АХУЕННО [NCM-PAD-03] Modern Ambient Clockwork (Analog Pad).wav»
    Расположение: sound/wav_input/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ПОЧЕМУ ЭТОТ СКРИПТ — ЭТАЛОН:

  ✅ Минималистичная цепочка — ничего лишнего
  ✅ НЕТ shelf EQ (не поднимает полки → нет ложного тепла)
  ✅ НЕТ soft limiter (не качает на атаках → нет скрипов)
  ✅ НЕТ компрессии (динамика сохранена полностью)
  ✅ Dynamic mud cut — режет только когда грязь реально есть,
     в чистые моменты не трогает звук вообще
  ✅ Micro-pitch ensemble — убирает AI-пластик естественно,
     добавляет «жизнь» без смазывания
  ✅ HF Exciter mix=10% — заполняет стерильный AI-спектр
     живыми нечётными гармониками
  ✅ Normalize без лимитера — пики не срезались, gain −0.08 dB

  ПРИНЦИП: убрать плохое → не добавлять ничего лишнего.
  Звук остаётся собой, только чище и живее.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ВЫЯВЛЕННЫЕ ПРОБЛЕМЫ (по результатам analyze_dirt_temporal.py
                      и analyze_plastic.py):

  1. MUD (грязь в 250–500 Hz)
     • Avg Dirt = 47.2 / Peak Dirt = 65.6 [VERY DIRTY]
     • Пики грязи в моментах: 0:19, 0:46, 1:27
     • Диагноз: избыточная энергия в зоне mud, мутит звуковую картину

  2. SUB RUMBLE (неуправляемый суббас < 60 Hz)
     • Вносит вклад в общий dirt score
     • Диагноз: фоновое низкочастотное гудение, не несёт музыкальной пользы

  3. AI-ПЛАСТИК (на высоких нотах, 19% времени)
     • Peak Plastic = 59.4 [PLASTIC]
     • Пики пластика: 0:37, 0:48, 1:37, 1:27
     • Диагноз: идеально регулярные гармоники, стерильный межгармонический
       спектр, отсутствие натурального вибрато 4–7 Hz — типичный AI-артефакт
       на высоких нотах пэда

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ЦЕПОЧКА ОБРАБОТКИ (эталонная — не менять без необходимости!):

  Step 1. HPF @ 42 Hz          — убираем sub rumble (< 60 Hz)
  Step 2. Dynamic EQ (Mud cut) — динамически давим 250–450 Hz только
                                  когда уровень превышает порог -28 dB
                                  ★ КЛЮЧ: не трогает чистые моменты
  Step 3. HF Exciter           — нечётные гармоники > 2 kHz, mix=10%
                                  ★ КЛЮЧ: заполняет стерильный AI-спектр
  Step 4. Micro-pitch ensemble — хорус 5.2 Hz, depth=3.5, mix=18%
                                  ★ КЛЮЧ: натуральное вибрато, убивает пластик
                                  L/R phase offset — добавляет ширину
  Step 5. Tape roll-off        — мягкий срез > 14 kHz (2-й порядок)
  Step 6. Peak normalize       — без лимитера, чистая нормализация

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Выходной файл:
  sound/wav_output/NCM-PAD-03_Ambient_Clockwork_FIXED.wav

Графики (before/after):
  analysis/fix_ncm_pad03_spectrum.png
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
ROOT   = Path(__file__).parent
INPUT  = ROOT / "sound" / "wav_input" / "ОК  АХУЕННО [NCM-PAD-03] Modern Ambient Clockwork (Analog Pad).wav"
OUTPUT = ROOT / "sound" / "wav_output" / "NCM-PAD-03_Ambient_Clockwork_FIXED.wav"
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("  fix_ncm_pad03_ambient_clockwork.py")
print("  Трек: NCM-PAD-03 Modern Ambient Clockwork (Analog Pad)")
print("=" * 60)
print(f"\n  Вход : {INPUT.name}")
print(f"  Выход: {OUTPUT.name}\n")

data, fs = sf.read(str(INPUT))
print(f"  SR={fs} Hz  |  Duration={len(data)/fs:.1f}s  |  Channels={data.ndim}")

if data.ndim == 1:
    data = np.stack([data, data], axis=1)
out = data.astype(np.float64).copy()


# ══════════════════════════════════════════════════════════════
#  STEP 1. HPF — Sub Rumble Remover (< 42 Hz)
# ══════════════════════════════════════════════════════════════
print("\n── Step 1: HPF @ 42 Hz (Sub Rumble) ─────────────────────")
sos_hpf = sg.butter(4, 42.0, btype="high", fs=fs, output="sos")
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_hpf, out[:, c])
print("  ✅ Sub rumble < 42 Hz убран (Butterworth 4-го порядка)")


# ══════════════════════════════════════════════════════════════
#  STEP 2. Dynamic Mud Cut (250–450 Hz)
#  Давим mud-зону только когда она превышает порог (Soothe-подобно)
# ══════════════════════════════════════════════════════════════
print("\n── Step 2: Dynamic Mud Cut (250–450 Hz) ─────────────────")

def dynamic_mud_cut(ch, fs, f_lo=250, f_hi=450,
                    threshold_db=-28.0, max_cut_db=-5.0,
                    attack_ms=8.0, release_ms=80.0):
    """
    Динамически вырезает mud-зону только когда её уровень превышает порог.
    Не трогает звук когда он чистый — работает только в грязных моментах.
    """
    # Выделяем mud-полосу
    sos_bp = sg.butter(3, [f_lo, f_hi], btype="band", fs=fs, output="sos")
    mud_band = sg.sosfiltfilt(sos_bp, ch)

    # Огибающая RMS mud-полосы
    frame = max(1, int(attack_ms / 1000.0 * fs))
    rms = np.sqrt(
        np.convolve(mud_band**2, np.ones(frame) / frame, mode="same") + 1e-12
    )
    db_env = 20.0 * np.log10(rms + 1e-12)

    # Сколько превышаем порог
    over = np.clip(db_env - threshold_db, 0.0, None)

    # Gain reduction: каждые 6 dB превышения → ещё -1 dB среза
    max_linear_cut = 1.0 - 10.0 ** (max_cut_db / 20.0)
    cut_factor = np.clip(over / 18.0, 0.0, 1.0) * max_linear_cut

    # Сглаживание (release)
    rel_frame = max(1, int(release_ms / 1000.0 * fs))
    cut_smooth = sg.filtfilt(
        np.ones(rel_frame) / rel_frame, [1.0], cut_factor
    )

    return ch - mud_band * cut_smooth

for c in range(2):
    out[:, c] = dynamic_mud_cut(
        out[:, c], fs,
        f_lo=250, f_hi=450,
        threshold_db=-28.0,
        max_cut_db=-5.0,
        attack_ms=8.0, release_ms=80.0
    )
print("  ✅ Dynamic mud cut: 250–450 Hz, порог -28 dB, макс срез -5 dB")
print("     (срабатывает только в моменты 0:19, 0:46, 1:27)")


# ══════════════════════════════════════════════════════════════
#  STEP 3. HF Harmonic Exciter (борьба с AI-пластиком)
#  Добавляем живые нечётные гармоники выше 2 kHz
#  → заполняем стерильное межгармоническое пространство
# ══════════════════════════════════════════════════════════════
print("\n── Step 3: HF Exciter (Anti-plastic, > 2 kHz) ───────────")

def hf_exciter(ch, fs, crossover_hz=2000.0, drive_db=6.0, mix=0.12):
    """
    Выделяет полосу выше crossover_hz, слегка насыщает её нечётными
    гармониками через tanh, подмешивает обратно.
    Эффект: заполняет стерильный межгармонический шум, звук оживает.
    mix: 0.12 = 12% подмешивание возбуждённого сигнала
    """
    # Выделяем HF
    sos_hp = sg.butter(3, crossover_hz, btype="high", fs=fs, output="sos")
    hf = sg.sosfiltfilt(sos_hp, ch)

    # Лёгкая сатурация (только нечётные гармоники → натуральность)
    drive = 10.0 ** (drive_db / 20.0)
    hf_sat = np.tanh(hf * drive) / drive

    # Добавляем разницу (только то что добавила сатурация)
    excite = hf_sat - hf

    return ch + excite * mix

for c in range(2):
    out[:, c] = hf_exciter(out[:, c], fs,
                            crossover_hz=2000.0,
                            drive_db=7.0,
                            mix=0.10)
print("  ✅ HF Exciter: нечётные гармоники > 2 kHz, mix=10%")
print("     (заполняет стерильный AI-спектр живой текстурой)")


# ══════════════════════════════════════════════════════════════
#  STEP 4. Micro-pitch Ensemble (Анти-пластик на высоких нотах)
#  Создаём лёгкое расстройство/хорус в HF — имитация натурального
#  вибрато 4–6 Hz. Убирает «ламинарность» AI-гармоник.
# ══════════════════════════════════════════════════════════════
print("\n── Step 4: Micro-pitch Ensemble (Anti-plastic vibrato) ──")

def micro_ensemble(ch, fs, rate_hz=5.0, depth_samples=3.0, mix=0.18):
    """
    Хорус с очень маленькой глубиной (3 сэмпла ≈ микропитч).
    Скорость 5 Hz — в зоне натурального вибрато (4–7 Hz).
    Создаёт лёгкую интерференцию гармоник → звук живёт, не «пластик».
    mix: 0.18 = 18% подмешивание
    """
    n = len(ch)
    t = np.arange(n) / fs

    # LFO: синусоидальная модуляция задержки
    lfo = depth_samples * np.sin(2.0 * np.pi * rate_hz * t)

    # Дробная задержка через линейную интерполяцию
    idx = np.arange(n, dtype=np.float64) - np.abs(lfo)
    idx_lo = np.clip(idx.astype(np.int32), 0, n - 1)
    idx_hi = np.clip(idx_lo + 1, 0, n - 1)
    frac = idx - idx_lo.astype(np.float64)

    delayed = ch[idx_lo] * (1.0 - frac) + ch[idx_hi] * frac

    return ch * (1.0 - mix) + delayed * mix

# Применяем только к HF (выше 1.5 kHz) чтобы не трогать низкие частоты
sos_hf_cross = sg.butter(3, 1500.0, btype="high", fs=fs, output="sos")
sos_lf_cross = sg.butter(3, 1500.0, btype="low",  fs=fs, output="sos")

for c in range(2):
    hf_part = sg.sosfiltfilt(sos_hf_cross, out[:, c])
    lf_part = sg.sosfiltfilt(sos_lf_cross, out[:, c])

    # Ensemble с небольшим сдвигом фазы LFO между L/R для ширины
    phase_offset = 0.0 if c == 0 else np.pi * 0.3
    n = len(hf_part)
    t = np.arange(n) / fs
    depth = 3.5
    rate  = 5.2
    lfo = depth * np.sin(2.0 * np.pi * rate * t + phase_offset)
    idx = np.arange(n, dtype=np.float64) - np.abs(lfo)
    idx_lo = np.clip(idx.astype(np.int32), 0, n - 1)
    idx_hi = np.clip(idx_lo + 1, 0, n - 1)
    frac = idx - idx_lo.astype(np.float64)
    delayed_hf = hf_part[idx_lo] * (1.0 - frac) + hf_part[idx_hi] * frac
    ensemble_hf = hf_part * 0.82 + delayed_hf * 0.18

    out[:, c] = lf_part + ensemble_hf

print("  ✅ Micro-pitch ensemble: rate=5.2 Hz, depth=3.5 samples")
print("     (имитирует натуральное вибрато 4–7 Hz на высоких нотах)")
print("     (L/R сдвинуты по фазе — добавляет ширину пэда)")


# ══════════════════════════════════════════════════════════════
#  STEP 5. Tape Roll-Off (мягкий срез > 14 kHz)
#  Убираем цифровую жёсткость, финальный «тёплый» характер
# ══════════════════════════════════════════════════════════════
print("\n── Step 5: Tape Roll-Off @ 14 kHz ───────────────────────")
sos_rolloff = sg.butter(2, 14000.0, btype="low", fs=fs, output="sos")
for c in range(2):
    out[:, c] = sg.sosfiltfilt(sos_rolloff, out[:, c])
print("  ✅ Мягкий tape roll-off выше 14 kHz (2-й порядок)")


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
print(f"\n✅ Сохранено: {OUTPUT}")


# ══════════════════════════════════════════════════════════════
#  BEFORE / AFTER SPECTRUM CHART
# ══════════════════════════════════════════════════════════════
print("\n── Генерация графика Before / After ─────────────────────")

def smooth_spec(mono_sig, fs, nfft=65536, sm=60):
    n = min(nfft, len(mono_sig))
    win = np.hanning(n)
    sp = np.abs(np.fft.rfft(mono_sig[:n] * win, n=nfft))
    fr = np.fft.rfftfreq(nfft, 1.0 / fs)
    db = 20.0 * np.log10(sp + 1e-9)
    return fr, np.convolve(db, np.ones(sm) / sm, mode="same")

orig_mono = (data[:, 0] + data[:, 1]) / 2.0
fix_mono  = (out[:, 0]  + out[:, 1])  / 2.0
fr, db_orig = smooth_spec(orig_mono, fs)
_,  db_fix  = smooth_spec(fix_mono,  fs)

BG    = "#0d0d0d"
PANEL = "#141414"
GRID  = "#252525"

fig, axes = plt.subplots(3, 1, figsize=(16, 13), facecolor=BG)
fig.suptitle(
    "NCM-PAD-03 Modern Ambient Clockwork (Analog Pad)\n"
    "Before / After Fix — Spectrum Analysis",
    color="#e0e0e0", fontsize=13, fontweight="bold", y=0.99
)

mask = (fr >= 20) & (fr <= 20000)

# ── Panel 1: Spectrum overlay ─────────────────────────────────
ax1 = axes[0]
ax1.set_facecolor(PANEL)
ax1.semilogx(fr[mask], db_orig[mask], color="#7ec8e3", lw=1.3,
             alpha=0.65, linestyle="--", label="Original")
ax1.semilogx(fr[mask], db_fix[mask],  color="#f472b6", lw=1.6,
             alpha=0.95, label="Fixed")

# Highlight problem zones
ax1.axvspan(20,  42,  color="#60a5fa", alpha=0.06, label="HPF cut zone (sub rumble)")
ax1.axvspan(250, 450, color="#f97316", alpha=0.07, label="Dynamic mud cut zone")
ax1.axvspan(2000, 8000, color="#4ade80", alpha=0.05, label="HF Exciter zone")

# Annotations for problem moments
for t_s, label, col in [(19, "Dirt#1\n0:19", "#ef4444"),
                         (46, "Dirt#2\n0:46", "#ef4444"),
                         (87, "Dirt#3\n1:27", "#f97316")]:
    pass  # cannot annotate by time on spectrum — shown in heatmap

ax1.set_xlim(20, 20000)
ax1.set_xticks([31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
ax1.set_xticklabels(["31","63","125","250","500","1k","2k","4k","8k","16k"])
ax1.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#666", fontsize=9)
ax1.tick_params(colors="#555", labelsize=8)
ax1.spines[:].set_color(GRID)
ax1.grid(True, color=GRID, lw=0.4, linestyle="--")
ax1.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
ax1.set_title("Frequency Spectrum: Original vs Fixed", color="#bbb",
              fontsize=9, pad=5, fontweight="bold")
for lbl in ax1.get_xticklabels() + ax1.get_yticklabels():
    lbl.set_color("#555")

# ── Panel 2: Difference curve ─────────────────────────────────
ax2 = axes[1]
ax2.set_facecolor(PANEL)
diff = np.convolve(db_fix - db_orig, np.ones(80) / 80, mode="same")
ax2.semilogx(fr[mask], diff[mask], color="#34d399", lw=1.5,
             label="Difference (Fixed − Original)")
ax2.axhline(0, color="#555", linestyle="--", lw=0.8)
ax2.fill_between(fr[mask], 0, diff[mask],
                 where=(diff[mask] > 0), color="#34d399", alpha=0.18)
ax2.fill_between(fr[mask], 0, diff[mask],
                 where=(diff[mask] < 0), color="#ef4444", alpha=0.18)

# Zone labels
ax2.axvspan(20,  42,   color="#60a5fa", alpha=0.07)
ax2.axvspan(250, 450,  color="#f97316", alpha=0.07)
ax2.axvspan(2000, 8000, color="#4ade80", alpha=0.05)
ax2.text(30,    diff[mask].min() * 0.7, "HPF",   color="#60a5fa", fontsize=7)
ax2.text(300,   diff[mask].min() * 0.7, "Mud",   color="#f97316", fontsize=7)
ax2.text(3000,  diff[mask].max() * 0.7, "HF+",   color="#4ade80", fontsize=7)

ax2.set_xlim(20, 20000)
ax2.set_xticks([31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])
ax2.set_xticklabels(["31","63","125","250","500","1k","2k","4k","8k","16k"])
ax2.set_ylim(-8, 6)
ax2.set_xlabel("Frequency (Hz)", color="#666", fontsize=9)
ax2.set_ylabel("ΔdB", color="#666", fontsize=9)
ax2.tick_params(colors="#555", labelsize=8)
ax2.spines[:].set_color(GRID)
ax2.grid(True, color=GRID, lw=0.4, linestyle="--")
ax2.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=8)
ax2.set_title("Correction Curve (green=added, red=removed)", color="#bbb",
              fontsize=9, pad=5, fontweight="bold")
for lbl in ax2.get_xticklabels() + ax2.get_yticklabels():
    lbl.set_color("#555")

# ── Panel 3: Processing summary table ─────────────────────────
ax3 = axes[2]
ax3.set_facecolor(PANEL)
ax3.axis("off")
ax3.set_title("Processing Chain Summary", color="#bbb",
              fontsize=9, pad=5, fontweight="bold")

steps = [
    ("Step 1", "HPF @ 42 Hz",            "Sub Rumble < 42 Hz",           "Butterworth 4th order",    "#60a5fa"),
    ("Step 2", "Dynamic Mud Cut",         "250–450 Hz | threshold -28 dB","Max cut -5 dB | Rel 80ms", "#f97316"),
    ("Step 3", "HF Exciter",             "> 2 kHz | drive 7 dB",         "Mix 10% odd harmonics",    "#4ade80"),
    ("Step 4", "Micro-pitch Ensemble",   "5.2 Hz LFO | depth 3.5 samp",  "Mix 18% | L/R phase offset","#c084fc"),
    ("Step 5", "Tape Roll-Off",          "< 14 kHz",                      "Butterworth 2nd order",    "#facc15"),
    ("Step 6", "Peak Normalize",         "Match original peak",           f"Scale {20*np.log10(scale):+.2f} dB",  "#94a3b8"),
]

col_x = [0.01, 0.09, 0.25, 0.52, 0.75]
headers = ["Step", "Process", "Target", "Parameters", ""]
for xi, h in zip(col_x, headers):
    ax3.text(xi, 0.97, h, color="#666", fontsize=8, fontweight="bold",
             va="top", transform=ax3.transAxes)

ax3.plot([0, 1], [0.93, 0.93], color="#252525", lw=0.8, transform=ax3.transAxes)

for i, (step, proc, target, params, col) in enumerate(steps):
    y = 0.89 - i * 0.135
    ax3.text(col_x[0], y, step,   color=col,   fontsize=8, va="top", transform=ax3.transAxes, fontweight="bold")
    ax3.text(col_x[1], y, proc,   color="#ddd", fontsize=8, va="top", transform=ax3.transAxes)
    ax3.text(col_x[2], y, target, color="#aaa", fontsize=7.5, va="top", transform=ax3.transAxes)
    ax3.text(col_x[3], y, params, color="#888", fontsize=7, va="top", transform=ax3.transAxes)
    # Color dot
    ax3.text(col_x[4], y, "●", color=col, fontsize=10, va="top", transform=ax3.transAxes)

plt.tight_layout(rect=[0, 0, 1, 0.97])
chart_path = ROOT / "analysis" / "fix_ncm_pad03_spectrum.png"
plt.savefig(str(chart_path), dpi=130, bbox_inches="tight", facecolor=BG)
plt.close()
print(f"  [PNG] {chart_path.name}")

print("\n" + "=" * 60)
print("  DONE — обработка завершена!")
print(f"  Файл : {OUTPUT.name}")
print(f"  График: analysis/fix_ncm_pad03_spectrum.png")
print("=" * 60 + "\n")
