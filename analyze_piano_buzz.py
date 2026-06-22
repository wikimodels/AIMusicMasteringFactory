"""
analyze_piano_buzz.py
=====================
Целевой анализ felt piano артефактов:
  1. Buzz/Rattle — что именно дребезжит на громких моментах
  2. Attack smear — смазаны ли атаки нот
  3. Bass-piano intermodulation — где контрабас вызывает дребезжание
  4. Sustain decay — как ведёт себя хвост (AI-реверб vs натуральный)
  5. Динамическая спектрограмма с маркерами "горячих" моментов
"""

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import scipy.signal as sg
from scipy.ndimage import uniform_filter1d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
import warnings; warnings.filterwarnings("ignore")

ROOT  = Path(__file__).parent
FPATH = ROOT / "Slow piano Jazz v 1.wav"
OUT   = ROOT / "analysis"

data, fs = sf.read(str(FPATH))
if data.ndim == 1: data = np.stack([data, data], axis=1)
data = data.astype(np.float64)
mono = (data[:, 0] + data[:, 1]) / 2.0
N    = len(mono)
print(f"Loaded: {N} samples, {fs} Hz, {N/fs:.1f}s")

# ══════════════════════════════════════════════════════════════
#  1. BUZZ HUNTER — ищем частоты которые активируются на forte
# ══════════════════════════════════════════════════════════════
# Делим трек на блоки 500мс.
# В каждом блоке смотрим FFT.
# Сравниваем "горячие" блоки (топ 20% по RMS) с "тихими" (нижние 40%).
# Разница = частоты, которые НЕПРОПОРЦИОНАЛЬНО усиливаются на forte = buzz.

BLOCK = int(0.5 * fs)  # 500 ms
N_BLK = N // BLOCK

rms_blk = np.array([
    np.sqrt(np.mean(mono[i*BLOCK:(i+1)*BLOCK]**2))
    for i in range(N_BLK)
])

loud_thresh  = np.percentile(rms_blk, 80)
quiet_thresh = np.percentile(rms_blk, 40)
loud_idx  = np.where(rms_blk >= loud_thresh)[0]
quiet_idx = np.where(rms_blk <= quiet_thresh)[0]

N_FFT = 32768
fr = np.fft.rfftfreq(N_FFT, 1.0/fs)

def avg_spectrum(block_indices):
    specs = []
    for i in block_indices:
        seg = mono[i*BLOCK:(i+1)*BLOCK]
        if len(seg) < N_FFT:
            seg = np.pad(seg, (0, N_FFT - len(seg)))
        w = np.hanning(N_FFT)
        sp = np.abs(np.fft.rfft(seg[:N_FFT] * w, n=N_FFT))
        specs.append(20 * np.log10(sp + 1e-9))
    return np.mean(specs, axis=0) if specs else np.zeros(len(fr))

db_loud  = avg_spectrum(loud_idx)
db_quiet = avg_spectrum(quiet_idx)

k = np.ones(60) / 60
db_loud_s  = np.convolve(db_loud,  k, mode="same")
db_quiet_s = np.convolve(db_quiet, k, mode="same")

# Buzz = loud_spectrum - quiet_spectrum, выше baseline
buzz_diff = db_loud_s - db_quiet_s

# Находим пики buzz в диапазоне 50–2000 Hz (где контрабас + пианино)
buzz_mask = (fr >= 50) & (fr <= 2000)
buzz_seg  = buzz_diff[buzz_mask]
buzz_f    = fr[buzz_mask]
baseline_b = uniform_filter1d(buzz_seg, size=200)
peaks_b    = buzz_seg - baseline_b
thresh_b   = 3.0  # dB выше baseline

spike_i = np.where(peaks_b > thresh_b)[0]
buzz_resonances = []
if len(spike_i) > 0:
    g, grps = [spike_i[0]], []
    for idx in spike_i[1:]:
        if idx - g[-1] < 30: g.append(idx)
        else: grps.append(g); g = [idx]
    grps.append(g)
    for g in grps:
        c = g[np.argmax(peaks_b[g])]
        buzz_resonances.append((buzz_f[c], peaks_b[c]))
    buzz_resonances.sort(key=lambda x: -x[1])

print(f"\n── BUZZ FREQUENCIES (активируются при forte) ────")
print(f"  Loud blocks   : {len(loud_idx)} / {N_BLK}")
print(f"  Quiet blocks  : {len(quiet_idx)} / {N_BLK}")
print(f"  Buzz spikes > +{thresh_b} dB: {len(buzz_resonances)}")
for f0, amp in buzz_resonances[:8]:
    zone = "КОНТРАБАС" if f0 < 120 else "ФУНДАМЕНТАЛ ПИАНО" if f0 < 300 else "BODY/BOX" if f0 < 600 else "НАSAL"
    print(f"    {f0:5.0f} Hz  +{amp:.1f} dB  [{zone}]")

# ══════════════════════════════════════════════════════════════
#  2. ATTACK ANALYSIS — насколько смазан фронт нот
# ══════════════════════════════════════════════════════════════
# Берём кратковременную энергию (10мс блоки) и смотрим на скорость нарастания
env_10ms = int(0.010 * fs)
n_env    = N // env_10ms
env = np.array([
    np.sqrt(np.mean(mono[i*env_10ms:(i+1)*env_10ms]**2))
    for i in range(n_env)
])

# Нарастание: производная энергии
d_env = np.diff(env)
attack_speed_p90 = np.percentile(d_env[d_env > 0], 90)
attack_speed_p50 = np.percentile(d_env[d_env > 0], 50)
print(f"\n── ATTACK ANALYSIS ─────────────────────────────")
print(f"  Attack speed P90: {attack_speed_p90:.5f}  (больше = резче атаки)")
print(f"  Attack speed P50: {attack_speed_p50:.5f}")
if attack_speed_p90 < 0.005:
    print("  → Атаки СИЛЬНО СМАЗАНЫ (felt + AI-реверб убивает трансиенты)")
elif attack_speed_p90 < 0.020:
    print("  → Атаки умеренно мягкие (нормально для felt piano)")
else:
    print("  → Атаки достаточно чёткие")

# ══════════════════════════════════════════════════════════════
#  3. SUSTAIN / REVERB TAIL АНАЛИЗ
# ══════════════════════════════════════════════════════════════
# После каждой "ноты" (всплеска) смотрим как быстро затихает хвост
# Найдём моменты атаки (env > P70) и смотрим RT60-like decay
note_thresh = np.percentile(env, 70)
note_starts = np.where((env[:-1] < note_thresh) & (env[1:] >= note_thresh))[0]

decay_rates = []
for ns in note_starts[:20]:  # Берём первые 20 нот
    peak_val = env[ns]
    # Ищем падение на -20 dB
    for j in range(ns, min(ns + 200, len(env))):
        if env[j] < peak_val * 0.1:
            decay_ms = (j - ns) * 10
            decay_rates.append(decay_ms)
            break

if decay_rates:
    mean_decay = np.mean(decay_rates)
    print(f"\n── SUSTAIN DECAY ────────────────────────────────")
    print(f"  Mean -20dB decay: {mean_decay:.0f} ms")
    if mean_decay > 800:
        print("  → ДЛИННЫЙ хвост — AI-реверб сливает ноты в кашу")
    elif mean_decay > 400:
        print("  → Умеренный хвост — пограничная зона")
    else:
        print("  → Нормальный decay")

# ══════════════════════════════════════════════════════════════
#  4. INTERMODULATION — контрабас vs пианино
# ══════════════════════════════════════════════════════════════
# Фильтруем: bass band (40-120 Hz) и piano body (200-600 Hz)
sos_bass  = sg.butter(4, [40,  120],  "bp", fs=fs, output="sos")
sos_piano = sg.butter(4, [200, 600],  "bp", fs=fs, output="sos")

bass_sig  = sg.sosfiltfilt(sos_bass,  mono)
piano_sig = sg.sosfiltfilt(sos_piano, mono)

# RMS за 200мс окна
W = int(0.2 * fs)
n_w = N // W
bass_rms  = np.array([np.sqrt(np.mean(bass_sig[i*W:(i+1)*W]**2))  for i in range(n_w)])
piano_rms = np.array([np.sqrt(np.mean(piano_sig[i*W:(i+1)*W]**2)) for i in range(n_w)])
t_w = np.arange(n_w) * 0.2

# Корреляция между RMS баса и уровнем пиано на "buzz" частоте
if buzz_resonances:
    buzz_f0 = buzz_resonances[0][0]
    sos_buzz = sg.butter(6, [max(20, buzz_f0*0.85), min(fs/2-1, buzz_f0*1.15)],
                         "bp", fs=fs, output="sos")
    buzz_sig  = sg.sosfiltfilt(sos_buzz, mono)
    buzz_rms  = np.array([np.sqrt(np.mean(buzz_sig[i*W:(i+1)*W]**2)) for i in range(n_w)])
    corr_bass_buzz = np.corrcoef(bass_rms, buzz_rms)[0, 1]
    print(f"\n── INTERMODULATION ──────────────────────────────")
    print(f"  Buzz freq: {buzz_f0:.0f} Hz")
    print(f"  Корреляция BASS_RMS ↔ BUZZ_RMS: {corr_bass_buzz:.3f}")
    if corr_bass_buzz > 0.5:
        print("  ✗ ВЫСОКАЯ корреляция — контрабас ПРОВОЦИРУЕТ дребезжание!")
        print("  → Нужен dynamic EQ notch на buzz freq, триггер = bass level")
    elif corr_bass_buzz > 0.3:
        print("  ▸ Умеренная корреляция — частичная intermod")
    else:
        print("  ✓ Низкая корреляция — buzz не от контрабаса")
else:
    buzz_rms = piano_rms.copy()
    corr_bass_buzz = 0.0

# ══════════════════════════════════════════════════════════════
#  PLOT — 4 панели
# ══════════════════════════════════════════════════════════════
BG, PL, GR = "#0d0d0d", "#1a1a1a", "#2a2a2a"
C1, C2, C3, C4 = "#7ec8e3", "#f472b6", "#f59e0b", "#34d399"

fig = plt.figure(figsize=(16, 12), facecolor=BG)
fig.suptitle("Felt Piano Buzz Autopsy — Slow Piano Jazz v1",
             color="#e0e0e0", fontsize=14, fontweight="bold")
gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.32)

# ── Panel 1: Buzz spectrum (loud vs quiet) ─────────
ax1 = fig.add_subplot(gs[0, :])
ax1.set_facecolor(PL); ax1.grid(True, color=GR, lw=0.4)
bm = (fr >= 30) & (fr <= 3000)
ax1.semilogx(fr[bm], db_loud_s[bm],  color=C2, lw=1.5, alpha=0.9, label=f"Forte (P80-P100 RMS)")
ax1.semilogx(fr[bm], db_quiet_s[bm], color=C1, lw=1.5, alpha=0.9, label=f"Piano (P0-P40 RMS)")
ax1.fill_between(fr[bm], db_quiet_s[bm], db_loud_s[bm],
                 where=(db_loud_s[bm] > db_quiet_s[bm]),
                 color="#f59e0b", alpha=0.15, label="Непропорциональный рост (buzz zone)")
# Отмечаем buzz пики
for f0, amp in buzz_resonances[:5]:
    ax1.axvline(f0, color="#ef4444", lw=0.9, linestyle="--", alpha=0.7)
    ax1.text(f0*1.02, ax1.get_ylim()[0]+2 if ax1.get_ylim()[0] > -200 else -60,
             f"{f0:.0f}Hz\n+{amp:.1f}dB", color="#ef4444", fontsize=7, va="bottom")
TICKS = [30,60,100,200,400,800,1000,2000,3000]
TLABS = ["30","60","100","200","400","800","1k","2k","3k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
ax1.set_xlim(30, 3000)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Buzz Hunter: Forte vs Piano spectrum — жёлтая зона = непропорционально растёт на громкости", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

# ── Panel 2: Dynamics envelope + note attacks ──────
ax2 = fig.add_subplot(gs[1, 0])
ax2.set_facecolor(PL); ax2.grid(True, color=GR, lw=0.4)
t_e = np.arange(n_env) * 0.010
ax2.plot(t_e, 20*np.log10(env+1e-9), color=C1, lw=0.6, alpha=0.8, label="Envelope (10ms)")
# Mark note starts
for ns in note_starts[:50]:
    ax2.axvline(ns * 0.010, color=C3, lw=0.4, alpha=0.3)
ax2.axhline(20*np.log10(note_thresh+1e-9), color=C3, lw=0.8, linestyle="--", alpha=0.6, label="Note threshold")
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Time (s)", color="#888", fontsize=9)
ax2.set_ylabel("dBFS", color="#888", fontsize=9)
ax2.set_title(f"Envelope + Note Attacks (жёлтые = ноты, {len(note_starts)} найдено)", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

# ── Panel 3: Bass vs Buzz correlation ──────────────
ax3 = fig.add_subplot(gs[1, 1])
ax3.set_facecolor(PL); ax3.grid(True, color=GR, lw=0.4)
ax3.plot(t_w, 20*np.log10(bass_rms+1e-9),  color=C1, lw=0.9, alpha=0.9, label="Bass 40-120Hz RMS")
ax3.plot(t_w, 20*np.log10(buzz_rms+1e-9),  color="#ef4444", lw=0.9, alpha=0.8,
         label=f"Buzz @ {buzz_resonances[0][0]:.0f}Hz RMS" if buzz_resonances else "Buzz RMS")
ax3.plot(t_w, 20*np.log10(piano_rms+1e-9), color=C3, lw=0.7, alpha=0.6, label="Piano body 200-600Hz")
[l.set_color("#888") for l in ax3.get_xticklabels()+ax3.get_yticklabels()]
ax3.spines[:].set_color(GR)
ax3.set_xlabel("Time (s)", color="#888", fontsize=9)
ax3.set_ylabel("dBFS", color="#888", fontsize=9)
ax3.set_title(f"Bass vs Buzz intermod  [corr={corr_bass_buzz:.2f}]", color="#ccc", fontsize=10)
ax3.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=9)

# ── Summary box ────────────────────────────────────
summary_lines = ["ДИАГНОЗ FELT PIANO:"]
if buzz_resonances:
    summary_lines.append(f"  Buzz peak: {buzz_resonances[0][0]:.0f} Hz (+{buzz_resonances[0][1]:.1f} dB при forte)")
summary_lines.append(f"  Attack P90 speed: {attack_speed_p90:.5f} — {'СМАЗАН' if attack_speed_p90 < 0.005 else 'OK'}")
if decay_rates:
    summary_lines.append(f"  Sustain decay -20dB: {mean_decay:.0f}ms — {'ДЛИННЫЙ/СЛИВ' if mean_decay > 800 else 'OK'}")
summary_lines.append(f"  Bass→Buzz corr: {corr_bass_buzz:.2f} — {'INTERMOD!' if corr_bass_buzz > 0.5 else 'умеренная'}")
fig.text(0.5, 0.01, "\n".join(summary_lines), ha="center", va="bottom",
         fontsize=9, color="#e0e0e0",
         bbox=dict(facecolor="#1a1a2e", edgecolor="#444", alpha=0.85, pad=6))

out_path = OUT / "Slow_Piano_Jazz_v1_buzz_analysis.png"
plt.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"\n[CHART] {out_path}")

print("\n── BUZZ SUMMARY ────────────────────────────────")
if buzz_resonances:
    print(f"  Топ buzz-частоты для dynamic EQ:")
    for f0, amp in buzz_resonances[:5]:
        print(f"    {f0:.0f} Hz  (+{amp:.1f} dB при forte) → notch -4..-6 dB, триггер по RMS")
