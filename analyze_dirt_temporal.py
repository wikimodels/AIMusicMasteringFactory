import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
analyze_dirt_temporal.py
========================
Временно-разрешённый анализ «грязи» в WAV-треках.

Ключевое отличие от статического анализа:
  — Трек делится на короткие кадры (0.5 с, перекрытие 50%)
  — Для каждого кадра считаются dirt-метрики
  — Итог = PEAK DIRT (худший момент), не среднее
  — Показываются временны́е карты (где именно грязно)

Детекторы:
  1. Frame Mud Ratio       — мутность 250–500 Hz / total per frame
  2. Frame Spectral Flux   — резкое изменение спектра (артефакты, щелчки)
  3. Frame THD proxy       — гармонические искажения: энергия чётных гармоник
                             относительно фундаментала (метод cepstrum peaks)
  4. Frame Kurtosis        — тяжёлые хвосты в сигнале = клиппинг, перегруз
  5. Frame Spectral Flatness — шумоподобность спектра per frame
  6. Frame HF Spike        — внезапные пики в 4–12 kHz
  7. Frame Sub Rumble      — неконтролируемый суббас <60 Hz per frame
  8. Frame Distortion Idx  — резкость спектра (variance спектра 200-2k)

Выходные файлы:
  analysis/temporal_<stem>.png  — детальный временно́й отчёт
  analysis/temporal_summary.png — сравнение треков (peak vs avg)
"""

import numpy as np
import soundfile as sndfile
import scipy.signal as sig
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

ROOT      = Path(__file__).parent
INPUT_DIR = ROOT / "sound" / "wav_input"
OUT_DIR   = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

# Параметры кадров
FRAME_MS    = 500   # длина кадра, мс
HOP_MS      = 250   # шаг (50% overlap)

BG      = "#0d0d0d"
PANEL   = "#161616"
GRID    = "#252525"
CLEAN_C = "#4ade80"
OK_C    = "#facc15"
DIRTY_C = "#f97316"
VDIRTY_C= "#ef4444"
ACCENT  = "#c084fc"

TICKS   = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
TLABELS = ["20","50","100","200","500","1k","2k","5k","10k","20k"]


# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class FrameMetrics:
    t:          float    # время начала кадра, сек
    mud:        float    # mud ratio %
    sf:         float    # spectral flatness
    kurt:       float    # kurtosis сигнала
    hf_spike:   float    # HF spike energy ratio
    sub_rumble: float    # sub <60 Hz ratio
    spec_var:   float    # spectral variance 200-2k
    flux:       float    # spectral flux (изменение от предыдущего кадра)
    thd_proxy:  float    # THD approximation
    dirt:       float    # итоговый dirt этого кадра


@dataclass
class TemporalReport:
    name:       str
    sr:         int
    duration_s: float
    frames:     List[FrameMetrics] = field(default_factory=list)

    # Итоги
    avg_dirt:   float = 0.0
    peak_dirt:  float = 0.0
    p95_dirt:   float = 0.0     # 95-й перцентиль

    # Временны́е серии (numpy arrays)
    t_arr:      np.ndarray = field(default_factory=lambda: np.array([]))
    dirt_arr:   np.ndarray = field(default_factory=lambda: np.array([]))
    mud_arr:    np.ndarray = field(default_factory=lambda: np.array([]))
    sf_arr:     np.ndarray = field(default_factory=lambda: np.array([]))
    kurt_arr:   np.ndarray = field(default_factory=lambda: np.array([]))
    hf_arr:     np.ndarray = field(default_factory=lambda: np.array([]))
    sub_arr:    np.ndarray = field(default_factory=lambda: np.array([]))
    flux_arr:   np.ndarray = field(default_factory=lambda: np.array([]))
    thd_arr:    np.ndarray = field(default_factory=lambda: np.array([]))

    # Спектр для референса (полный Welch)
    freqs:      np.ndarray = field(default_factory=lambda: np.array([]))
    spectrum_db:np.ndarray = field(default_factory=lambda: np.array([]))

    # Топ грязных моментов
    top_dirty:  List[Tuple[float, float]] = field(default_factory=list)  # [(t, dirt)]


# ──────────────────────────────────────────────────────────────────────────────
def mono(data: np.ndarray) -> np.ndarray:
    return data.mean(axis=1) if data.ndim > 1 else data


def band_power_ratio(f, pxx, lo, hi, total_power):
    mask = (f >= lo) & (f <= hi)
    if mask.sum() == 0 or total_power < 1e-30:
        return 0.0
    df = f[1] - f[0] if len(f) > 1 else 1.0
    return float(np.sum(pxx[mask]) * df) / total_power


def spectral_flatness_arr(pxx):
    pxx = pxx[pxx > 0]
    if len(pxx) < 2:
        return 0.0
    geo = np.exp(np.mean(np.log(pxx + 1e-30)))
    ari = np.mean(pxx) + 1e-30
    return float(geo / ari)


def thd_proxy_cepstrum(frame: np.ndarray, sr: int) -> float:
    """
    THD proxy через кепстр: сумма энергии кепстральных пиков
    в диапазоне, соответствующем 2f–6f при f=50–400 Hz.
    Высокое значение → гармонические искажения.
    """
    if len(frame) < 256:
        return 0.0
    n = len(frame)
    # Спектр
    sp = np.abs(np.fft.rfft(frame * np.hanning(n)))
    sp_db = 20 * np.log10(sp + 1e-9)
    # Кепстр (обратное FFT от log-спектра)
    cep = np.abs(np.fft.irfft(sp_db))
    # Кепстральные индексы для гармоник f=50..400 Hz: quefrency = 1/f
    # T = sr / f → индекс = round(sr / f)
    # Ищем гармоники: индексы T/2, T/3 (т.е. 2f, 3f)
    harmonic_energy = 0.0
    for f0 in [80, 120, 180, 240, 320]:   # потенциальные фундаменталы
        idx_f0 = int(round(sr / f0))
        for mult in [2, 3, 4]:
            idx_h = int(round(sr / (f0 * mult)))
            if 2 <= idx_h < len(cep) // 2:
                harmonic_energy += cep[idx_h]
    # Нормируем на кепстральную энергию фундамента
    fund_energy = sum(cep[max(2, int(round(sr/f0)))] for f0 in [80,120,180,240,320]
                      if int(round(sr/f0)) < len(cep))
    if fund_energy < 1e-9:
        return 0.0
    return float(np.clip(harmonic_energy / (fund_energy + 1e-9) / 3.0, 0, 1))


def compute_full_spectrum(s, sr):
    nperseg = min(131072, len(s))
    f, pxx = sig.welch(s, fs=sr, nperseg=nperseg, noverlap=nperseg//2,
                       window="hann", scaling="density")
    db = 10 * np.log10(pxx + 1e-12)
    k = np.ones(60) / 60
    return f, np.convolve(db, k, mode="same")


# ──────────────────────────────────────────────────────────────────────────────
def score_component(val, low_ok, high_bad, max_score=100.0) -> float:
    if val <= low_ok:  return 0.0
    if val >= high_bad: return max_score
    return max_score * (val - low_ok) / (high_bad - low_ok)


def frame_dirt_score(mud, sf, kurt, hf, sub, svar, flux, thd) -> float:
    """Итоговый dirt для одного кадра (0–100)."""
    s_mud   = score_component(mud * 100, 3,   12)    # mud ratio %
    s_sf    = score_component(sf,        0.01, 0.08)  # spectral flatness
    s_kurt  = score_component(max(0, 6 - kurt), 0, 5) # низкий kurt = шум
    s_hf    = score_component(hf * 100,  0.5, 5)      # HF ratio %
    s_sub   = score_component(sub * 100, 0.1, 1.5)    # sub rumble %
    s_svar  = score_component(svar,      3,   20)      # spec variance
    s_flux  = score_component(flux,      0.05, 0.5)   # spectral flux
    s_thd   = score_component(thd,       0.1, 0.6)    # THD proxy

    dirt = (
        s_mud  * 0.22 +
        s_sf   * 0.12 +
        s_kurt * 0.10 +
        s_hf   * 0.10 +
        s_sub  * 0.12 +
        s_svar * 0.10 +
        s_flux * 0.12 +
        s_thd  * 0.12
    )
    return float(np.clip(dirt, 0, 100))


# ──────────────────────────────────────────────────────────────────────────────
def analyze_temporal(path: Path) -> TemporalReport:
    data, sr = sndfile.read(str(path))
    s = mono(data).astype(np.float64)
    dur = len(s) / sr

    frame_len = int(sr * FRAME_MS / 1000)
    hop_len   = int(sr * HOP_MS / 1000)

    # Полный спектр для референса
    f_full, sp_full = compute_full_spectrum(s, sr)

    frames = []
    prev_pxx = None

    n_frames = (len(s) - frame_len) // hop_len + 1
    print(f"    {n_frames} frames @ {FRAME_MS}ms / {HOP_MS}ms hop")

    for i in range(n_frames):
        start = i * hop_len
        end   = start + frame_len
        if end > len(s):
            break
        frame = s[start:end]
        t     = start / sr

        # Спектр кадра
        nperseg = min(4096, len(frame))
        f, pxx = sig.welch(frame, fs=sr, nperseg=nperseg,
                           window="hann", scaling="density")
        df = f[1] - f[0] if len(f) > 1 else 1.0
        total_pwr = float(np.sum(pxx) * df) + 1e-30

        # Метрики
        mud      = band_power_ratio(f, pxx, 250, 500, total_pwr)
        sfv      = spectral_flatness_arr(pxx)
        kurt_v   = float(stats.kurtosis(frame))
        hf_spike = band_power_ratio(f, pxx, 4000, 12000, total_pwr)
        sub_rum  = band_power_ratio(f, pxx, 20, 60, total_pwr)

        # Spectral variance 200-2k
        m200 = (f >= 200) & (f <= 2000)
        svar = float(pxx[m200].std() / (pxx[m200].mean() + 1e-30)) if m200.sum() > 1 else 0.0

        # Spectral flux (изменение от предыдущего кадра)
        if prev_pxx is not None and len(prev_pxx) == len(pxx):
            # L2 norm разницы нормированных спектров
            curr_n = pxx / (np.sum(pxx) + 1e-30)
            prev_n = prev_pxx / (np.sum(prev_pxx) + 1e-30)
            flux = float(np.sqrt(np.sum((curr_n - prev_n)**2)))
        else:
            flux = 0.0
        prev_pxx = pxx.copy()

        # THD proxy
        thd = thd_proxy_cepstrum(frame, sr)

        # Dirt score кадра
        dirt = frame_dirt_score(mud, sfv, kurt_v, hf_spike, sub_rum, svar, flux, thd)

        frames.append(FrameMetrics(
            t=t, mud=mud, sf=sfv, kurt=kurt_v, hf_spike=hf_spike,
            sub_rumble=sub_rum, spec_var=svar, flux=flux, thd_proxy=thd,
            dirt=dirt
        ))

    if not frames:
        return TemporalReport(name=path.stem, sr=sr, duration_s=dur,
                              freqs=f_full, spectrum_db=sp_full)

    t_arr    = np.array([fm.t     for fm in frames])
    dirt_arr = np.array([fm.dirt  for fm in frames])
    mud_arr  = np.array([fm.mud   for fm in frames]) * 100
    sf_arr   = np.array([fm.sf    for fm in frames]) * 100
    kurt_arr = np.array([fm.kurt  for fm in frames])
    hf_arr   = np.array([fm.hf_spike for fm in frames]) * 100
    sub_arr  = np.array([fm.sub_rumble for fm in frames]) * 100
    flux_arr = np.array([fm.flux  for fm in frames]) * 100
    thd_arr  = np.array([fm.thd_proxy for fm in frames]) * 100

    avg_dirt = float(dirt_arr.mean())
    peak_dirt= float(dirt_arr.max())
    p95_dirt = float(np.percentile(dirt_arr, 95))

    # Топ-5 грязных моментов
    top_idx   = np.argsort(dirt_arr)[::-1][:5]
    top_dirty = [(float(t_arr[i]), float(dirt_arr[i])) for i in top_idx]

    r = TemporalReport(
        name       = path.stem,
        sr         = sr,
        duration_s = dur,
        frames     = frames,
        avg_dirt   = avg_dirt,
        peak_dirt  = peak_dirt,
        p95_dirt   = p95_dirt,
        t_arr      = t_arr,
        dirt_arr   = dirt_arr,
        mud_arr    = mud_arr,
        sf_arr     = sf_arr,
        kurt_arr   = kurt_arr,
        hf_arr     = hf_arr,
        sub_arr    = sub_arr,
        flux_arr   = flux_arr,
        thd_arr    = thd_arr,
        freqs      = f_full,
        spectrum_db= sp_full,
        top_dirty  = top_dirty,
    )
    return r


# ──────────────────────────────────────────────────────────────────────────────
def grade_and_color(score: float) -> Tuple[str, str]:
    if score < 22:  return "CLEAN",      CLEAN_C
    if score < 42:  return "OK",         OK_C
    if score < 62:  return "DIRTY",      DIRTY_C
    return              "VERY DIRTY",    VDIRTY_C


def ax_style(ax, title=""):
    ax.set_facecolor(PANEL)
    if title:
        ax.set_title(title, color="#bbb", fontsize=8.5, pad=5, fontweight="bold")
    ax.tick_params(colors="#555", labelsize=7)
    ax.spines[:].set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.4, linestyle="--")
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#555")


# ──────────────────────────────────────────────────────────────────────────────
# Детальный временно́й отчёт
# ──────────────────────────────────────────────────────────────────────────────
def plot_temporal(r: TemporalReport, out_path: Path):
    fig = plt.figure(figsize=(18, 14), facecolor=BG)
    grade_p, grade_color_p = grade_and_color(r.peak_dirt)
    grade_a, grade_color_a = grade_and_color(r.avg_dirt)

    fig.suptitle(
        f"Temporal Dirt Analysis  ·  {r.name}\n"
        f"Peak: {r.peak_dirt:.1f} [{grade_p}]   "
        f"Avg: {r.avg_dirt:.1f} [{grade_a}]   "
        f"P95: {r.p95_dirt:.1f}",
        color="#e0e0e0", fontsize=12, fontweight="bold", y=0.99
    )

    gs = gridspec.GridSpec(4, 3, figure=fig, hspace=0.55, wspace=0.38,
                           left=0.06, right=0.97, top=0.94, bottom=0.05)

    # 1. Dirt Timeline (main) ─────────────────────────────────────────────────
    ax_dirt = fig.add_subplot(gs[0, :])
    # Градиентная заливка под кривой
    dirt_norm = r.dirt_arr / 100.0
    for i in range(len(r.t_arr) - 1):
        c = plt.cm.RdYlGn_r(dirt_norm[i])
        ax_dirt.fill_between(r.t_arr[i:i+2], 0, r.dirt_arr[i:i+2], color=c, alpha=0.7)
    ax_dirt.plot(r.t_arr, r.dirt_arr, color="white", lw=0.8, alpha=0.5)

    # Пороговые линии
    for thr, col, lbl in [(22, CLEAN_C, "CLEAN"), (42, OK_C, "OK"), (62, DIRTY_C, "DIRTY")]:
        ax_dirt.axhline(thr, color=col, lw=0.7, linestyle="--", alpha=0.5)

    # Топ-грязные моменты — отмечаем маркерами
    for t_top, d_top in r.top_dirty:
        ax_dirt.annotate(
            f"{t_top:.0f}s\n{d_top:.0f}",
            xy=(t_top, d_top), xytext=(t_top, min(d_top + 12, 98)),
            color=VDIRTY_C, fontsize=6.5, ha="center",
            arrowprops=dict(arrowstyle="-", color=VDIRTY_C, lw=0.8)
        )

    ax_dirt.set_xlim(0, r.duration_s)
    ax_dirt.set_ylim(0, 100)
    ax_dirt.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_dirt.set_ylabel("Dirt Score", color="#555", fontsize=8)
    ax_style(ax_dirt, f"Dirt Score Over Time  (frame={FRAME_MS}ms, hop={HOP_MS}ms)")

    # 2. Mud Ratio over time ──────────────────────────────────────────────────
    ax_mud = fig.add_subplot(gs[1, 0:2])
    ax_mud.fill_between(r.t_arr, 0, r.mud_arr, color=DIRTY_C, alpha=0.4)
    ax_mud.plot(r.t_arr, r.mud_arr, color=DIRTY_C, lw=1.2, alpha=0.9)
    ax_mud.axhline(9, color=VDIRTY_C, lw=0.8, linestyle="--", alpha=0.6, label="dirty threshold")
    ax_mud.axhline(3, color=CLEAN_C,  lw=0.8, linestyle="--", alpha=0.6, label="clean threshold")
    ax_mud.set_xlim(0, r.duration_s); ax_mud.set_ylim(bottom=0)
    ax_mud.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_mud.set_ylabel("Mud Ratio (%)", color="#555", fontsize=8)
    ax_mud.legend(fontsize=6.5, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_mud, "Mud (250–500 Hz) Over Time")

    # 3. THD & Flux ────────────────────────────────────────────────────────────
    ax_thd = fig.add_subplot(gs[1, 2])
    ax_thd.plot(r.t_arr, r.thd_arr, color="#f472b6", lw=1.2, alpha=0.9, label="THD proxy")
    ax_thd.plot(r.t_arr, r.flux_arr, color="#38bdf8", lw=1.0, alpha=0.8, label="Spec Flux ×100")
    ax_thd.set_xlim(0, r.duration_s)
    ax_thd.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_thd.legend(fontsize=6.5, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_thd, "THD Proxy & Spectral Flux")

    # 4. Kurtosis over time ───────────────────────────────────────────────────
    ax_kurt = fig.add_subplot(gs[2, 0])
    ax_kurt.plot(r.t_arr, r.kurt_arr, color="#a78bfa", lw=1.2, alpha=0.9)
    ax_kurt.fill_between(r.t_arr, r.kurt_arr, 3, where=(r.kurt_arr < 3),
                          color=VDIRTY_C, alpha=0.35, label="низкий kurt (шум/грязь)")
    ax_kurt.axhline(3, color=VDIRTY_C, lw=0.8, linestyle="--", alpha=0.6)
    ax_kurt.axhline(0, color="#333", lw=0.6)
    ax_kurt.set_xlim(0, r.duration_s)
    ax_kurt.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_kurt.set_ylabel("Kurtosis", color="#555", fontsize=8)
    ax_kurt.legend(fontsize=6, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_kurt, "Signal Kurtosis (low=noisy/dirty)")

    # 5. Sub Rumble over time ──────────────────────────────────────────────────
    ax_sub = fig.add_subplot(gs[2, 1])
    ax_sub.fill_between(r.t_arr, 0, r.sub_arr, color="#60a5fa", alpha=0.4)
    ax_sub.plot(r.t_arr, r.sub_arr, color="#60a5fa", lw=1.2, alpha=0.9)
    ax_sub.axhline(1.5, color=VDIRTY_C, lw=0.8, linestyle="--", alpha=0.5, label="dirty threshold")
    ax_sub.set_xlim(0, r.duration_s); ax_sub.set_ylim(bottom=0)
    ax_sub.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_sub.set_ylabel("Sub Rumble %", color="#555", fontsize=8)
    ax_sub.legend(fontsize=6.5, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_sub, "Sub Rumble (<60 Hz) Over Time")

    # 6. HF Spike over time ──────────────────────────────────────────────────
    ax_hf = fig.add_subplot(gs[2, 2])
    ax_hf.fill_between(r.t_arr, 0, r.hf_arr, color="#34d399", alpha=0.4)
    ax_hf.plot(r.t_arr, r.hf_arr, color="#34d399", lw=1.2, alpha=0.9)
    ax_hf.set_xlim(0, r.duration_s); ax_hf.set_ylim(bottom=0)
    ax_hf.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_hf.set_ylabel("HF Energy %", color="#555", fontsize=8)
    ax_style(ax_hf, "HF Spike (4–12 kHz) Over Time")

    # 7. Dirt Heatmap (2D) ───────────────────────────────────────────────────
    ax_heat = fig.add_subplot(gs[3, :])
    # Создаём матрицу из метрик [metric × time]
    metric_names = ["Dirt", "Mud", "HF Spike", "Sub Rumble", "THD", "Flux"]
    metric_arrays = [
        r.dirt_arr,
        r.mud_arr / r.mud_arr.max() * 100 if r.mud_arr.max() > 0 else r.mud_arr,
        r.hf_arr  / r.hf_arr.max()  * 100 if r.hf_arr.max()  > 0 else r.hf_arr,
        r.sub_arr / r.sub_arr.max() * 100 if r.sub_arr.max() > 0 else r.sub_arr,
        r.thd_arr / r.thd_arr.max() * 100 if r.thd_arr.max() > 0 else r.thd_arr,
        r.flux_arr/ r.flux_arr.max()* 100 if r.flux_arr.max()> 0 else r.flux_arr,
    ]
    matrix = np.array(metric_arrays)
    im = ax_heat.imshow(matrix, aspect="auto", cmap="hot", vmin=0, vmax=100,
                         extent=[0, r.duration_s, -0.5, len(metric_names) - 0.5],
                         origin="upper", interpolation="bilinear")
    ax_heat.set_yticks(range(len(metric_names)))
    ax_heat.set_yticklabels(metric_names, fontsize=8)
    ax_heat.set_xlabel("Time (s)", color="#555", fontsize=8)
    plt.colorbar(im, ax=ax_heat, orientation="vertical", fraction=0.01, pad=0.005,
                 label="Normalized intensity").ax.tick_params(colors="#666", labelsize=6)

    # Маркируем топ-грязные моменты на heatmap
    for t_top, d_top in r.top_dirty:
        ax_heat.axvline(t_top, color=VDIRTY_C, lw=1.0, linestyle="--", alpha=0.7)

    ax_style(ax_heat, "Dirt Component Heatmap Over Time  (red=dirty, black=clean)  |  ▼ = peak dirt moments")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# Сравнительный summary
# ──────────────────────────────────────────────────────────────────────────────
def plot_temporal_summary(reports: List[TemporalReport], out_path: Path):
    fig = plt.figure(figsize=(18, 10), facecolor=BG)
    fig.suptitle("Temporal Dirt Summary — Peak vs Average",
                 color="#e0e0e0", fontsize=14, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.52, wspace=0.38,
                           left=0.06, right=0.97, top=0.94, bottom=0.06)

    names = [r.name[:35] for r in reports]
    tc    = [ACCENT, CLEAN_C, OK_C, DIRTY_C, VDIRTY_C]

    # A. Peak vs Avg Dirt ─────────────────────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    x = np.arange(len(reports))
    w = 0.28
    for i, r in enumerate(reports):
        gc_peak = grade_and_color(r.peak_dirt)[1]
        gc_avg  = grade_and_color(r.avg_dirt)[1]
        ax_a.bar(i - w, r.avg_dirt,  w*1.8, color=gc_avg,  alpha=0.6, label="Avg"  if i==0 else "")
        ax_a.bar(i + w, r.peak_dirt, w*1.8, color=gc_peak, alpha=0.9, label="Peak" if i==0 else "")
        ax_a.text(i - w, r.avg_dirt  + 1, f"{r.avg_dirt:.1f}",  ha="center", color="#aaa", fontsize=7)
        ax_a.text(i + w, r.peak_dirt + 1, f"{r.peak_dirt:.1f}", ha="center", color=gc_peak, fontsize=7, fontweight="bold")
    for thr, col in [(22, CLEAN_C), (42, OK_C), (62, DIRTY_C)]:
        ax_a.axhline(thr, color=col, lw=0.7, linestyle="--", alpha=0.45)
    ax_a.set_xticks(x); ax_a.set_xticklabels(names, fontsize=6.5, rotation=12)
    ax_a.set_ylim(0, 105)
    ax_a.legend(fontsize=7.5, facecolor="#111", edgecolor="#333", labelcolor="#ccc")
    ax_style(ax_a, "Peak vs Avg Dirt Score")

    # B. P95 Dirt (слуховой ориентир) ─────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    p95_vals = [r.p95_dirt for r in reports]
    bar_colors = [grade_and_color(v)[1] for v in p95_vals]
    bars = ax_b.bar(x, p95_vals, color=bar_colors, alpha=0.85, width=0.5)
    for bar, v in zip(bars, p95_vals):
        g, gc = grade_and_color(v)
        ax_b.text(bar.get_x() + bar.get_width()/2, v + 1,
                  f"{v:.1f}\n[{g}]", ha="center", color=gc, fontsize=7, fontweight="bold")
    ax_b.set_xticks(x); ax_b.set_xticklabels(names, fontsize=6.5, rotation=12)
    ax_b.set_ylim(0, 105)
    ax_style(ax_b, "P95 Dirt Score  (≈ perceived dirtiness)")

    # C. Top Dirty Moments table ───────────────────────────────────────────────
    ax_c = fig.add_subplot(gs[0, 2])
    ax_c.axis("off"); ax_c.set_facecolor(PANEL)
    ax_c.set_title("Top Dirty Moments", color="#bbb", fontsize=9, pad=5, fontweight="bold")
    y = 0.97
    for r in reports:
        ax_c.text(0.01, y, f"▶ {r.name[:30]}", color=ACCENT, fontsize=7.5,
                  va="top", fontweight="bold")
        y -= 0.08
        for rank, (t, d) in enumerate(r.top_dirty[:3], 1):
            g, gc_ = grade_and_color(d)
            mm = int(t // 60); ss = int(t % 60)
            ax_c.text(0.05, y, f"  #{rank}  {mm:02d}:{ss:02d}  dirt={d:.1f}  [{g}]",
                      color="#aaa" if d < 50 else VDIRTY_C, fontsize=7, va="top")
            y -= 0.07
        y -= 0.04

    # D. Overlaid Dirt Timelines ──────────────────────────────────────────────
    ax_d = fig.add_subplot(gs[1, :])
    for i, r in enumerate(reports):
        c = tc[i % len(tc)]
        g_peak = grade_and_color(r.peak_dirt)[0]
        label = f"{r.name[:34]}  [peak={r.peak_dirt:.1f} {g_peak}, avg={r.avg_dirt:.1f}]"
        ax_d.plot(r.t_arr, r.dirt_arr, color=c, lw=1.3, alpha=0.82, label=label)

    for thr, col, lbl in [(22, CLEAN_C, "CLEAN"), (42, OK_C, "OK"), (62, DIRTY_C, "DIRTY")]:
        ax_d.axhline(thr, color=col, lw=0.8, linestyle="--", alpha=0.45)
        ax_d.text(1, thr + 1, lbl, color=col, fontsize=6.5, alpha=0.6)

    ax_d.set_ylim(0, 100)
    ax_d.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_d.set_ylabel("Dirt Score", color="#555", fontsize=8)
    ax_d.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc", fontsize=7.5, loc="upper right")
    ax_style(ax_d, "Overlaid Dirt Timelines — All Tracks")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# Консольный отчёт
# ──────────────────────────────────────────────────────────────────────────────
def print_report(reports: List[TemporalReport]):
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        tbl = Table(title="[bold white]Temporal Dirt Analysis[/bold white]",
                    box=box.ROUNDED, border_style="dim",
                    header_style="bold magenta", show_lines=True)
        tbl.add_column("Track",       style="cyan", max_width=36, no_wrap=True)
        tbl.add_column("Avg Dirt",    justify="right")
        tbl.add_column("Peak Dirt",   justify="right", style="bold")
        tbl.add_column("P95 Dirt",    justify="right")
        tbl.add_column("Top#1 t",     justify="right")
        tbl.add_column("Top#1 score", justify="right")
        tbl.add_column("Top#2 t",     justify="right")
        tbl.add_column("Top#2 score", justify="right")

        gs_map = {"CLEAN": "bold green", "OK": "bold yellow",
                  "DIRTY": "bold red", "VERY DIRTY": "bold red on dark_red"}

        for r in sorted(reports, key=lambda x: x.peak_dirt, reverse=True):
            gp, gcp = grade_and_color(r.peak_dirt)
            ga, gca = grade_and_color(r.avg_dirt)
            t1 = f"{r.top_dirty[0][0]:.0f}s" if r.top_dirty else "-"
            d1 = f"{r.top_dirty[0][1]:.1f}"  if r.top_dirty else "-"
            t2 = f"{r.top_dirty[1][0]:.0f}s" if len(r.top_dirty) > 1 else "-"
            d2 = f"{r.top_dirty[1][1]:.1f}"  if len(r.top_dirty) > 1 else "-"
            tbl.add_row(
                r.name[:36],
                f"[{gs_map.get(ga,'white')}]{r.avg_dirt:.1f}[/{gs_map.get(ga,'white')}]",
                f"[{gs_map.get(gp,'white')}]{r.peak_dirt:.1f}[/{gs_map.get(gp,'white')}]",
                f"{r.p95_dirt:.1f}",
                t1, d1, t2, d2,
            )
        console.print(); console.print(tbl)

        # Топ моментов
        console.print("\n[bold]⚠  Top Dirty Moments[/bold]")
        for r in sorted(reports, key=lambda x: x.peak_dirt, reverse=True):
            console.print(f"\n  [cyan]{r.name}[/cyan]")
            for rank, (t, d) in enumerate(r.top_dirty, 1):
                g, _ = grade_and_color(d)
                mm = int(t // 60); ss = int(t % 60)
                col = "red" if d >= 62 else "yellow" if d >= 42 else "green"
                console.print(f"    #{rank}  [{col}]{mm:02d}:{ss:02d}[/{col}]  dirt={d:.1f}  [{g}]")
    except ImportError:
        for r in sorted(reports, key=lambda x: x.peak_dirt, reverse=True):
            print(f"\n{r.name}")
            print(f"  avg={r.avg_dirt:.1f}  peak={r.peak_dirt:.1f}  p95={r.p95_dirt:.1f}")
            for rank, (t, d) in enumerate(r.top_dirty, 1):
                print(f"  #{rank}  t={t:.0f}s  dirt={d:.1f}")


# ──────────────────────────────────────────────────────────────────────────────
def main():
    wav_files = sorted(INPUT_DIR.glob("*.wav"))
    if not wav_files:
        print(f"[ERROR] No WAV files in {INPUT_DIR}"); return

    print(f"\n[INFO] Temporal analysis of {len(wav_files)} tracks\n")
    reports = []
    for p in wav_files:
        print(f"  → {p.name}")
        r = analyze_temporal(p)
        stem = r.name.replace(" ", "_").replace("/", "_")
        plot_temporal(r, OUT_DIR / f"temporal_{stem}.png")
        reports.append(r)
        print(f"    avg={r.avg_dirt:.1f}  peak={r.peak_dirt:.1f}  p95={r.p95_dirt:.1f}")

    print(f"\n  Generating summary…")
    plot_temporal_summary(reports, OUT_DIR / "temporal_summary.png")
    print_report(reports)
    print(f"\n[DONE] {OUT_DIR}\n")

if __name__ == "__main__":
    main()
