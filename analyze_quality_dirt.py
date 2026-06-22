import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
analyze_quality_dirt.py  v2
===========================
Оценка качества и «грязи» WAV-треков в sound/wav_input.

Алгоритм работает с ОТНОСИТЕЛЬНЫМИ метриками, что позволяет
сравнивать треки в одном стиле и жанре.

Компоненты Dirt Score:
───────────────────────────────────────────────────────────────────
 1. Mud Ratio      — LowMid (250–500 Hz) относительно полного RMS
                     спектра. Чем толще «горб» в этом диапазоне —
                     тем выше mud.

 2. Bass Bloat     — отношение SubBass+Bass к Mid (500–2k).
                     Перевес НЧ создаёт «бубнение».

 3. Spectral Tilt  — наклон спектра (dB/octave, линейная регрессия
                     в лог-шкале). Слишком крутой спад → «тёмный»
                     или «мутный» звук; слишком плоский → «крикливый».
                     Нормально для этого жанра: −3 … −8 dB/oct.

 4. Spectral Flatness (Wiener entropy) — мера шумоподобности спектра.
                     Высокая SF → фоновый шум / грязь.

 5. Crest Factor   — Peak / RMS (dB). < 8 dB → перекомпрессия.

 6. Dynamic Range  — std кратковременных RMS (300 мс окна, в dB).
                     Малое DR → «задавленная» динамика.

 7. Clip Score     — % сэмплов с |amp| ≥ 0.99.

 8. Sub Rumble     — энергия <40 Hz. Неконтролируемый суббас.

 9. HF Harshness   — пиковость (kurtosis) в полосе 6–12 kHz.
                     Острые пики → «резкость» / «грязь» в ВЧ.

10. Spectral Variance — дисперсия спектра в полосе 200–2000 Hz.
                     Неровный, «зубастый» спектр → артефакты.

Выходные файлы:
  analysis/dirt_report_<stem>.png  — детальный отчёт по треку
  analysis/dirt_summary.png        — сравнительный дашборд
"""

import numpy as np
import soundfile as sndfile
import scipy.signal as sig
import scipy.stats as stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Tuple

# ──────────────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent
INPUT_DIR = ROOT / "sound" / "wav_input"
OUT_DIR   = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

BANDS = {
    "SubBass":  (20,    80),
    "Bass":     (80,   250),
    "LowMid":   (250,  500),
    "Mid":      (500,  2000),
    "HiMid":    (2000, 8000),
    "Air":      (8000, 20000),
}

# Нормальный тilt для cinematic / jazz инструментал (dB/octave)
TILT_IDEAL   = -5.5
TILT_TOL     = 2.5      # ±2.5 dB/oct считается OK

# Пороги Spectral Flatness (0..1, 0=тональный, 1=белый шум)
SF_CLEAN     = 0.018    # ниже этого — чистый тональный сигнал
SF_DIRTY     = 0.06     # выше → явный шум

BG, PANEL, GRID = "#0d0d0d", "#161616", "#252525"
ACCENT = "#c084fc"
CLEAN_C, OK_C, DIRTY_C, VDIRTY_C = "#4ade80", "#facc15", "#f97316", "#ef4444"

TICKS   = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
TLABELS = ["20","50","100","200","500","1k","2k","5k","10k","20k"]


# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class TrackReport:
    name:          str
    sr:            int
    duration_s:    float
    rms_db:        float
    peak_db:       float
    crest_db:      float
    dr_std:        float        # dB std of short RMS frames
    clip_pct:      float        # % samples ≥ 0.99

    mud_ratio:     float        # LowMid / Total power ratio (%)
    bass_bloat:    float        # (SubBass+Bass) dB above Mid
    tilt_dbpoct:   float        # spectral slope dB/octave
    sf_global:     float        # spectral flatness 0..1
    sub_rumble:    float        # <40Hz energy relative to total (%)
    hf_kurtosis:   float        # kurtosis in 6-12k band
    spec_variance: float        # spectral variance 200-2k

    band_db:       Dict[str, float] = field(default_factory=dict)

    # Компоненты score (0..100 каждый перед взвешиванием)
    components:    Dict[str, float] = field(default_factory=dict)
    dirt_score:    float = 0.0
    grade:         str   = ""

    freqs:         np.ndarray = field(default_factory=lambda: np.array([]))
    spectrum_db:   np.ndarray = field(default_factory=lambda: np.array([]))
    psd_linear:    np.ndarray = field(default_factory=lambda: np.array([]))


# ──────────────────────────────────────────────────────────────────────────────
def mono(data: np.ndarray) -> np.ndarray:
    return data.mean(axis=1) if data.ndim > 1 else data


def compute_welch(s: np.ndarray, sr: int):
    nperseg = min(131072, len(s))
    f, pxx = sig.welch(s, fs=sr, nperseg=nperseg, noverlap=nperseg//2,
                       window="hann", scaling="density")
    return f, pxx   # linear PSD


def smooth_db(db: np.ndarray, k: int = 80) -> np.ndarray:
    kernel = np.ones(k) / k
    return np.convolve(db, kernel, mode="same")


def band_power(f, pxx, lo, hi):
    """Интегральная мощность в полосе (линейная)."""
    mask = (f >= lo) & (f <= hi)
    if mask.sum() == 0:
        return 1e-12
    df = f[1] - f[0] if len(f) > 1 else 1.0
    return float(np.sum(pxx[mask]) * df)


def band_db_avg(f, db_smooth, lo, hi):
    mask = (f >= lo) & (f <= hi)
    if mask.sum() == 0:
        return -90.0
    return float(db_smooth[mask].mean())


def spectral_flatness(pxx, f, lo=20, hi=20000):
    mask = (f >= lo) & (f <= hi)
    p = pxx[mask]
    p = p[p > 0]
    if len(p) < 2:
        return 0.0
    geo = np.exp(np.mean(np.log(p)))
    ari = np.mean(p)
    return float(geo / (ari + 1e-30))


def spectral_tilt(f, pxx, lo=80, hi=16000):
    """Линейная регрессия log(pxx) по log(f) → dB/octave."""
    mask = (f >= lo) & (f <= hi) & (pxx > 0)
    if mask.sum() < 10:
        return 0.0
    lf  = np.log2(f[mask])
    lp  = 10 * np.log10(pxx[mask])
    slope, _, _, _, _ = stats.linregress(lf, lp)
    return float(slope)   # dB/octave


def compute_dr(s: np.ndarray, sr: int, window_ms: int = 300) -> float:
    frame = int(sr * window_ms / 1000)
    n_f = len(s) // frame
    if n_f < 2:
        return 0.0
    rms_arr = np.array([
        20 * np.log10(np.sqrt(np.mean(s[i*frame:(i+1)*frame]**2)) + 1e-9)
        for i in range(n_f)
    ])
    return float(rms_arr.std())


def hf_kurtosis(s: np.ndarray, sr: int, lo=6000, hi=12000) -> float:
    """Kurtosis signal в полосе 6–12k. Высокое значение → острые пики / артефакты."""
    sos = sig.butter(4, [lo / (sr/2), hi / (sr/2)], btype="band", output="sos")
    filtered = sig.sosfilt(sos, s)
    return float(stats.kurtosis(filtered))


def spec_variance_band(f, pxx, lo=200, hi=2000) -> float:
    """Нормированная дисперсия PSD в полосе (коэф. вариации)."""
    mask = (f >= lo) & (f <= hi)
    p = pxx[mask]
    if len(p) < 2 or p.mean() == 0:
        return 0.0
    return float(p.std() / (p.mean() + 1e-30))


# ──────────────────────────────────────────────────────────────────────────────
def grade_and_color(score: float) -> Tuple[str, str]:
    if score < 22:  return "CLEAN",      CLEAN_C
    if score < 42:  return "OK",         OK_C
    if score < 62:  return "DIRTY",      DIRTY_C
    return              "VERY DIRTY",    VDIRTY_C


def score_component(val, low_ok, high_bad, max_score=100.0) -> float:
    """Линейная нормировка: val<=low_ok → 0, val>=high_bad → max_score."""
    if val <= low_ok:
        return 0.0
    if val >= high_bad:
        return max_score
    return max_score * (val - low_ok) / (high_bad - low_ok)


# ──────────────────────────────────────────────────────────────────────────────
def analyze_track(path: Path) -> TrackReport:
    data, sr = sndfile.read(str(path))
    s = mono(data).astype(np.float64)
    dur = len(s) / sr

    f, pxx = compute_welch(s, sr)
    db_raw    = 10 * np.log10(pxx + 1e-12)
    db_smooth = smooth_db(db_raw, k=60)

    # ── Уровни ────────────────────────────────────────────────────────────────
    rms   = 20 * np.log10(np.sqrt(np.mean(s**2)) + 1e-9)
    pk    = 20 * np.log10(np.abs(s).max() + 1e-9)
    crest = pk - rms
    clip  = 100.0 * float(np.mean(np.abs(s) >= 0.99))
    dr    = compute_dr(s, sr)

    band_db  = {n: band_db_avg(f, db_smooth, lo, hi) for n, (lo, hi) in BANDS.items()}

    # ── Мощности бандов ───────────────────────────────────────────────────────
    total_pwr   = band_power(f, pxx, 20, 20000)
    sub_pwr     = band_power(f, pxx, 20, 40)
    bass_pwr    = band_power(f, pxx, 80, 250)
    lowmid_pwr  = band_power(f, pxx, 250, 500)
    mid_pwr     = band_power(f, pxx, 500, 2000)
    subbass_pwr = band_power(f, pxx, 20, 80)

    # 1. Mud Ratio — LowMid относительно всего спектра (%)
    mud_ratio = 100.0 * lowmid_pwr / (total_pwr + 1e-30)

    # 2. Bass Bloat — dB превышение (SubBass+Bass) над Mid
    bass_bloat_db = 10*np.log10((subbass_pwr+bass_pwr)/(mid_pwr+1e-30))

    # 3. Spectral Tilt (dB/octave)
    tilt = spectral_tilt(f, pxx)

    # 4. Spectral Flatness
    sflatness = spectral_flatness(pxx, f)

    # 5. Sub Rumble — <40 Hz
    sub_rumble = 100.0 * sub_pwr / (total_pwr + 1e-30)

    # 6. HF Kurtosis (6–12 kHz)
    hf_kurt = hf_kurtosis(s, sr)

    # 7. Spectral Variance 200–2000 Hz
    spec_var = spec_variance_band(f, pxx)

    # ── Scoring ───────────────────────────────────────────────────────────────
    # Mud Ratio: OK < 3%, dirty > 8%
    s_mud     = score_component(mud_ratio,     3.0,   9.0)

    # Bass Bloat: OK < 8 dB, dirty > 15 dB
    s_bloat   = score_component(bass_bloat_db, 8.0,  16.0)

    # Tilt: отклонение от идеала (dB/oct)
    tilt_dev  = abs(tilt - TILT_IDEAL) - TILT_TOL
    s_tilt    = score_component(max(0, tilt_dev), 0.0,  4.0)

    # Spectral Flatness: clean < 0.02, dirty > 0.06
    s_sf      = score_component(sflatness,       SF_CLEAN, SF_DIRTY)

    # Crest Factor: > 12 OK, < 7 очень плохо
    crest_inv = 14.0 - crest   # чем меньше crest, тем выше inv
    s_crest   = score_component(max(0, crest_inv), 0.0, 8.0)

    # DR: > 7 OK, < 3 плохо
    dr_inv    = 8.0 - dr
    s_dr      = score_component(max(0, dr_inv),    0.0, 6.0)

    # Clipping
    s_clip    = score_component(clip, 0.0001, 0.05)

    # Sub Rumble: < 0.1% OK, > 0.5% плохо
    s_rumble  = score_component(sub_rumble, 0.05, 0.6)

    # HF Kurtosis: тональный сигнал имеет высокий kurtosis (>5)
    # Низкий kurtosis (< 3) → шумовая грязь в ВЧ
    hfk_inv   = max(0.0, 4.5 - hf_kurt)
    s_hfk     = score_component(hfk_inv, 0.0, 3.0)

    # Spectral Variance 200-2k: < 5 тихо, > 20 зубасто
    s_svar    = score_component(spec_var, 4.0, 25.0)

    components = {
        "Mud Ratio":      s_mud,
        "Bass Bloat":     s_bloat,
        "Spectral Tilt":  s_tilt,
        "Noise (SF)":     s_sf,
        "Crest Factor":   s_crest,
        "Dynamic Range":  s_dr,
        "Clipping":       s_clip,
        "Sub Rumble":     s_rumble,
        "HF Kurtosis":    s_hfk,
        "Spec Variance":  s_svar,
    }

    weights = {
        "Mud Ratio":     0.20,
        "Bass Bloat":    0.15,
        "Spectral Tilt": 0.12,
        "Noise (SF)":    0.12,
        "Crest Factor":  0.10,
        "Dynamic Range": 0.10,
        "Clipping":      0.06,
        "Sub Rumble":    0.07,
        "HF Kurtosis":   0.04,
        "Spec Variance": 0.04,
    }

    dirt_score = sum(components[k] * weights[k] for k in components)
    dirt_score = float(np.clip(dirt_score, 0, 100))
    grade, _   = grade_and_color(dirt_score)

    return TrackReport(
        name          = path.stem,
        sr            = sr,
        duration_s    = dur,
        rms_db        = rms,
        peak_db       = pk,
        crest_db      = crest,
        dr_std        = dr,
        clip_pct      = clip,
        mud_ratio     = mud_ratio,
        bass_bloat    = bass_bloat_db,
        tilt_dbpoct   = tilt,
        sf_global     = sflatness,
        sub_rumble    = sub_rumble,
        hf_kurtosis   = hf_kurt,
        spec_variance = spec_var,
        band_db       = band_db,
        components    = components,
        dirt_score    = dirt_score,
        grade         = grade,
        freqs         = f,
        spectrum_db   = db_smooth,
        psd_linear    = pxx,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Стиль осей
# ──────────────────────────────────────────────────────────────────────────────
def ax_style(ax, title):
    ax.set_facecolor(PANEL)
    ax.set_title(title, color="#bbb", fontsize=8.5, pad=5, fontweight="bold")
    ax.tick_params(colors="#555", labelsize=7)
    ax.spines[:].set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.4, linestyle="--")
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#555")


# ──────────────────────────────────────────────────────────────────────────────
# Детальный отчёт по треку
# ──────────────────────────────────────────────────────────────────────────────
def plot_single(r: TrackReport, out_path: Path):
    fig = plt.figure(figsize=(18, 11), facecolor=BG)
    grade, grade_color = grade_and_color(r.dirt_score)
    fig.suptitle(f"Quality & Dirt Analysis  ·  {r.name}",
                 color="#e0e0e0", fontsize=13, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(3, 4, figure=fig, hspace=0.58, wspace=0.40,
                           left=0.06, right=0.97, top=0.94, bottom=0.06)

    # 1. Спектр полный ─────────────────────────────────────────────────────────
    ax_spec = fig.add_subplot(gs[0, :])
    mask = (r.freqs >= 20) & (r.freqs <= 20000)
    ax_spec.semilogx(r.freqs[mask], r.spectrum_db[mask], color=ACCENT, lw=1.8, alpha=0.9)

    band_fills = ["#1e3a5f","#1a4a2e","#5a2e10","#2a1a4a","#1a3a3a","#3a1a2a"]
    for (bname, (lo, hi)), bc in zip(BANDS.items(), band_fills):
        bm = (r.freqs >= lo) & (r.freqs <= hi)
        if bm.sum():
            ax_spec.fill_between(r.freqs[bm], -120, r.spectrum_db[bm], color=bc, alpha=0.30)
            mid_f = (lo * hi) ** 0.5
            ypos  = r.spectrum_db[bm].max() + 2
            ax_spec.text(mid_f, min(ypos, -8), bname, color="#666", fontsize=6.5, ha="center")

    ax_spec.set_xlim(20, 20000); ax_spec.set_ylim(-110, 0)
    ax_spec.set_xticks(TICKS); ax_spec.set_xticklabels(TLABELS)
    ax_spec.set_xlabel("Frequency (Hz)", color="#555", fontsize=8)
    ax_spec.set_ylabel("Level (dB PSD)", color="#555", fontsize=8)
    ax_style(ax_spec, "Full-Range Frequency Spectrum  (Welch PSD, smoothed)")

    # 2. Dirt Gauge ────────────────────────────────────────────────────────────
    ax_g = fig.add_subplot(gs[1, 0])
    ax_g.set_aspect("equal"); ax_g.axis("off"); ax_g.set_facecolor(PANEL)
    theta = np.linspace(np.pi, 0, 300)
    for i in range(299):
        c_seg = plt.cm.RdYlGn_r(i/299)
        ax_g.plot(theta[i:i+2], [1]*2, lw=22, color=c_seg,
                  solid_capstyle="butt", transform=ax_g.transData)
    angle = np.pi - (r.dirt_score / 100.0) * np.pi
    ax_g.annotate("", xy=(np.cos(angle)*0.82, np.sin(angle)*0.82), xytext=(0,0),
                  arrowprops=dict(arrowstyle="-|>", color="white", lw=2.5))
    ax_g.set_xlim(-1.35, 1.35); ax_g.set_ylim(-0.25, 1.4)
    ax_g.text(0, -0.12, f"{r.dirt_score:.1f}", ha="center", va="center",
              color=grade_color, fontsize=26, fontweight="bold")
    ax_g.text(0, -0.35, grade, ha="center", va="center",
              color=grade_color, fontsize=11, fontweight="bold")
    ax_g.text(-1.25, 0.0, "0\nCLEAN", ha="center", color=CLEAN_C, fontsize=6)
    ax_g.text( 1.25, 0.0, "100\nDIRTY", ha="center", color=VDIRTY_C, fontsize=6)
    ax_g.set_title("DIRT SCORE", color="#aaa", fontsize=9, pad=5, fontweight="bold")

    # 3. Dirt Components Radar / Bar ───────────────────────────────────────────
    ax_comp = fig.add_subplot(gs[1, 1:3])
    comp_names = list(r.components.keys())
    comp_vals  = [r.components[k] for k in comp_names]
    c_colors   = [VDIRTY_C if v > 65 else DIRTY_C if v > 40 else OK_C if v > 20 else CLEAN_C
                  for v in comp_vals]
    bars = ax_comp.barh(comp_names, comp_vals, color=c_colors, alpha=0.82, height=0.6)
    ax_comp.axvline(20, color="#2a2a2a", lw=1, linestyle="--")
    ax_comp.axvline(40, color="#3a2a0a", lw=1, linestyle="--")
    ax_comp.axvline(65, color="#3a1a0a", lw=1, linestyle="--")
    for bar, v in zip(bars, comp_vals):
        ax_comp.text(v + 0.8, bar.get_y() + bar.get_height()/2,
                     f"{v:.1f}", va="center", color="#aaa", fontsize=7)
    ax_comp.set_xlim(0, 105)
    ax_comp.set_xlabel("Component Score (0=clean, 100=dirty)", color="#555", fontsize=8)
    ax_style(ax_comp, "Dirt Components (weighted)")

    # 4. Метрики текстом ───────────────────────────────────────────────────────
    ax_m = fig.add_subplot(gs[1, 3])
    ax_m.axis("off"); ax_m.set_facecolor(PANEL)
    metrics = [
        ("Duration",      f"{r.duration_s:.1f} s"),
        ("RMS",           f"{r.rms_db:.1f} dB"),
        ("Peak",          f"{r.peak_db:.1f} dBFS"),
        ("Crest Factor",  f"{r.crest_db:.1f} dB"),
        ("Dyn. Range",    f"{r.dr_std:.2f} dB std"),
        ("Clip Samples",  f"{r.clip_pct:.5f}%"),
        ("Mud Ratio",     f"{r.mud_ratio:.2f}%"),
        ("Bass Bloat",    f"{r.bass_bloat:.1f} dB"),
        ("Spec Tilt",     f"{r.tilt_dbpoct:.2f} dB/oct"),
        ("Spec Flatness", f"{r.sf_global:.4f}"),
        ("HF Kurtosis",   f"{r.hf_kurtosis:.2f}"),
        ("Sub Rumble",    f"{r.sub_rumble:.4f}%"),
    ]
    for i, (lbl, val) in enumerate(metrics):
        y = 0.97 - i * 0.083
        ax_m.text(0.02, y, lbl + ":", color="#666", fontsize=7.5, va="top")
        ax_m.text(0.55, y, val, color="#ccc", fontsize=7.5, va="top", fontweight="bold")
    ax_m.set_title("Raw Metrics", color="#aaa", fontsize=9, pad=5, fontweight="bold")

    # 5. Mud Zone ──────────────────────────────────────────────────────────────
    ax_mud = fig.add_subplot(gs[2, 0:2])
    mud_m = (r.freqs >= 100) & (r.freqs <= 800)
    if mud_m.sum():
        ax_mud.fill_between(r.freqs[mud_m], r.spectrum_db[mud_m].min()-2,
                             r.spectrum_db[mud_m], color=DIRTY_C, alpha=0.28)
        ax_mud.plot(r.freqs[mud_m], r.spectrum_db[mud_m], color=DIRTY_C, lw=1.6, alpha=0.9)
        ax_mud.axvspan(250, 500, color=DIRTY_C, alpha=0.06)
        ax_mud.text(350, r.spectrum_db[mud_m].max()+0.5, "MUD ZONE",
                    color=DIRTY_C, fontsize=7, ha="center", alpha=0.7)
    ax_mud.set_xlabel("Frequency (Hz)", color="#555", fontsize=8)
    ax_mud.set_ylabel("Level (dB)", color="#555", fontsize=8)
    ax_style(ax_mud, f"Mud Zone  100–800 Hz  [Mud Ratio: {r.mud_ratio:.2f}%]")

    # 6. HF Zone ───────────────────────────────────────────────────────────────
    ax_hf = fig.add_subplot(gs[2, 2:4])
    hf_m = (r.freqs >= 4000) & (r.freqs <= 20000)
    if hf_m.sum():
        ax_hf.fill_between(r.freqs[hf_m], r.spectrum_db[hf_m].min()-2,
                            r.spectrum_db[hf_m], color="#38bdf8", alpha=0.25)
        ax_hf.plot(r.freqs[hf_m], r.spectrum_db[hf_m], color="#38bdf8", lw=1.6, alpha=0.9)
        ax_hf.axvspan(6000, 12000, color="#f97316", alpha=0.06)
        ax_hf.text(8500, r.spectrum_db[hf_m].max()+0.5, "HF Zone (kurtosis)",
                   color="#f97316", fontsize=7, ha="center", alpha=0.7)
    ax_hf.set_xlabel("Frequency (Hz)", color="#555", fontsize=8)
    ax_hf.set_ylabel("Level (dB)", color="#555", fontsize=8)
    ax_style(ax_hf, f"High Frequency Zone  4k–20k  [HF Kurt: {r.hf_kurtosis:.1f}]")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# Сравнительный дашборд
# ──────────────────────────────────────────────────────────────────────────────
def plot_summary(reports: List[TrackReport], out_path: Path):
    n = len(reports)
    fig = plt.figure(figsize=(18, 12), facecolor=BG)
    fig.suptitle("Track Quality Summary — Dirt Report  (v2)",
                 color="#e0e0e0", fontsize=14, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(3, 3, figure=fig, hspace=0.55, wspace=0.38,
                           left=0.06, right=0.97, top=0.94, bottom=0.06)

    names  = [r.name[:38] for r in reports]
    scores = [r.dirt_score for r in reports]
    colors = [grade_and_color(r.dirt_score)[1] for r in reports]

    # A. Dirt Score ──────────────────────────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    bars = ax_a.barh(names, scores, color=colors, alpha=0.85, height=0.55)
    for thr, col, lbl in [(22, CLEAN_C, "CLEAN"), (42, OK_C, "OK"),
                           (62, DIRTY_C, "DIRTY")]:
        ax_a.axvline(thr, color=col, lw=0.9, linestyle="--", alpha=0.5)
    for bar, r in zip(bars, reports):
        g, gc = grade_and_color(r.dirt_score)
        ax_a.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                  f"{r.dirt_score:.1f} [{g}]", va="center", color=gc, fontsize=7)
    ax_a.set_xlim(0, 108)
    ax_a.set_xlabel("Dirt Score", color="#555", fontsize=8)
    ax_style(ax_a, "Dirt Score Ranking")

    # B. DR vs Crest ──────────────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    for i, r in enumerate(reports):
        c = grade_and_color(r.dirt_score)[1]
        ax_b.scatter(r.crest_db, r.dr_std, color=c, s=90, zorder=5)
        ax_b.text(r.crest_db + 0.1, r.dr_std + 0.05,
                  r.name[:20], color="#aaa", fontsize=6.5)
    ax_b.set_xlabel("Crest Factor (dB)  [higher=better]", color="#555", fontsize=8)
    ax_b.set_ylabel("Dynamic Range std (dB)  [higher=better]", color="#555", fontsize=8)
    ax_style(ax_b, "Dynamics: Crest vs DR")

    # C. Component Heatmap ────────────────────────────────────────────────────
    ax_c = fig.add_subplot(gs[0, 2])
    comp_keys = list(reports[0].components.keys())
    matrix = np.array([[r.components[k] for k in comp_keys] for r in reports])
    im = ax_c.imshow(matrix, aspect="auto", cmap="RdYlGn_r", vmin=0, vmax=100)
    ax_c.set_xticks(range(len(comp_keys)))
    ax_c.set_xticklabels(comp_keys, rotation=50, ha="right", fontsize=6)
    ax_c.set_yticks(range(n)); ax_c.set_yticklabels(names, fontsize=6.5)
    for i in range(n):
        for j in range(len(comp_keys)):
            ax_c.text(j, i, f"{matrix[i,j]:.0f}", ha="center", va="center",
                      color="white", fontsize=6, fontweight="bold")
    plt.colorbar(im, ax=ax_c, fraction=0.025, pad=0.01).ax.tick_params(colors="#666", labelsize=6)
    ax_c.set_title("Component Scores Heatmap (0=clean, 100=dirty)",
                   color="#aaa", fontsize=8, pad=5, fontweight="bold")
    ax_c.set_facecolor(PANEL)
    ax_c.tick_params(colors="#666")

    # D. Band Energy Heatmap ──────────────────────────────────────────────────
    ax_d = fig.add_subplot(gs[1, 0])
    bnames = list(BANDS.keys())
    bmatrix = np.array([[r.band_db[b] for b in bnames] for r in reports])
    im2 = ax_d.imshow(bmatrix, aspect="auto", cmap="plasma")
    ax_d.set_xticks(range(len(bnames))); ax_d.set_xticklabels(bnames, fontsize=7.5)
    ax_d.set_yticks(range(n)); ax_d.set_yticklabels(names, fontsize=6.5)
    for i in range(n):
        for j in range(len(bnames)):
            ax_d.text(j, i, f"{bmatrix[i,j]:.0f}", ha="center", va="center",
                      color="white", fontsize=7, fontweight="bold")
    plt.colorbar(im2, ax=ax_d, fraction=0.025).ax.tick_params(colors="#666", labelsize=6)
    ax_d.set_title("Band Energy Heatmap (dB)", color="#aaa", fontsize=8, pad=5, fontweight="bold")
    ax_d.set_facecolor(PANEL); ax_d.tick_params(colors="#666")

    # E. Mud Ratio & Bass Bloat ───────────────────────────────────────────────
    ax_e = fig.add_subplot(gs[1, 1])
    x = np.arange(n)
    w = 0.35
    mud_vals  = [r.mud_ratio for r in reports]
    bloat_vals= [max(0, r.bass_bloat) for r in reports]
    b1 = ax_e.bar(x - w/2, mud_vals,  w, label="Mud Ratio (%)",   color=DIRTY_C, alpha=0.8)
    b2 = ax_e.bar(x + w/2, bloat_vals, w, label="Bass Bloat (dB)", color=ACCENT, alpha=0.8)
    ax_e.set_xticks(x); ax_e.set_xticklabels([r.name[:15] for r in reports], fontsize=6.5, rotation=15)
    ax_e.legend(fontsize=7, facecolor="#1a1a1a", edgecolor="#333", labelcolor="#ccc")
    ax_e.set_ylabel("Value", color="#555", fontsize=8)
    ax_style(ax_e, "Mud & Bass Bloat")

    # F. Spectral Metrics ────────────────────────────────────────────────────
    ax_f = fig.add_subplot(gs[1, 2])
    sf_vals   = [r.sf_global * 1000 for r in reports]   # ×1000 для читаемости
    tilt_vals = [abs(r.tilt_dbpoct) for r in reports]
    dr_vals   = [r.dr_std for r in reports]
    ax_f.plot(names, sf_vals,   "o-", color="#38bdf8", lw=1.5, label="SF ×1000", markersize=6)
    ax_f.plot(names, tilt_vals, "s-", color=OK_C,     lw=1.5, label="|Tilt| dB/oct", markersize=6)
    ax_f.plot(names, dr_vals,   "^-", color=CLEAN_C,  lw=1.5, label="DR std (dB)", markersize=6)
    ax_f.legend(fontsize=7, facecolor="#1a1a1a", edgecolor="#333", labelcolor="#ccc")
    ax_f.tick_params(axis="x", labelsize=6, labelrotation=12)
    ax_style(ax_f, "Spectral Metrics Comparison")

    # G. Overlaid Spectra (full width) ────────────────────────────────────────
    ax_over = fig.add_subplot(gs[2, :])
    tc = ["#c084fc", "#4ade80", "#facc15", "#38bdf8", "#f97316"]
    for i, r in enumerate(reports):
        mask = (r.freqs >= 20) & (r.freqs <= 20000)
        lbl  = f"{r.name[:36]}  [{r.grade}  Dirt={r.dirt_score:.1f}]"
        ax_over.semilogx(r.freqs[mask], r.spectrum_db[mask],
                          color=tc[i % len(tc)], lw=1.5, alpha=0.85, label=lbl)

    for bname, (lo, hi) in BANDS.items():
        ax_over.axvspan(lo, hi, alpha=0.025, color="white")
        ax_over.axvline(lo, color="#222", lw=0.5)
        mid_f = (lo * hi) ** 0.5
        ax_over.text(mid_f, -8, bname, color="#333", fontsize=6, ha="center")

    ax_over.set_xlim(20, 20000); ax_over.set_ylim(-110, 0)
    ax_over.set_xticks(TICKS); ax_over.set_xticklabels(TLABELS)
    ax_over.set_xlabel("Frequency (Hz)", color="#555", fontsize=8)
    ax_over.set_ylabel("Level (dB PSD)", color="#555", fontsize=8)
    ax_over.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc",
                   fontsize=7.5, loc="lower right")
    ax_style(ax_over, "Overlaid Spectra — All Tracks")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
# Консольный отчёт
# ──────────────────────────────────────────────────────────────────────────────
def print_report(reports: List[TrackReport]):
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        tbl = Table(title="[bold white]Track Quality & Dirt Analysis  v2[/bold white]",
                    box=box.ROUNDED, border_style="dim", header_style="bold magenta",
                    show_lines=True)
        tbl.add_column("Track",        style="cyan",  max_width=38, no_wrap=True)
        tbl.add_column("Dur",          justify="right", style="dim")
        tbl.add_column("RMS",          justify="right")
        tbl.add_column("Crest",        justify="right")
        tbl.add_column("DR std",       justify="right")
        tbl.add_column("Mud %",        justify="right")
        tbl.add_column("Bass Bloat",   justify="right")
        tbl.add_column("Spec Tilt",    justify="right")
        tbl.add_column("SF×1k",        justify="right")
        tbl.add_column("Clip %",       justify="right")
        tbl.add_column("DIRT",  style="bold", justify="right")
        tbl.add_column("Grade",        justify="center")

        gs = {"CLEAN": "bold green", "OK": "bold yellow",
              "DIRTY": "bold red", "VERY DIRTY": "bold red on dark_red"}

        for r in sorted(reports, key=lambda x: x.dirt_score):
            g  = r.grade
            gc = gs.get(g, "white")
            tbl.add_row(
                r.name[:38],
                f"{r.duration_s:.0f}s",
                f"{r.rms_db:.1f}",
                f"{r.crest_db:.1f}",
                f"{r.dr_std:.2f}",
                f"{r.mud_ratio:.2f}",
                f"{r.bass_bloat:.1f}",
                f"{r.tilt_dbpoct:.2f}",
                f"{r.sf_global*1000:.2f}",
                f"{r.clip_pct:.5f}",
                f"{r.dirt_score:.1f}",
                f"[{gc}]{g}[/{gc}]",
            )
        console.print(); console.print(tbl)
    except ImportError:
        print("\n{:<40} {:>6} {:>6} {:>5} {:>6} {:>5} {:>6}".format(
            "Track","RMS","Crest","DR","Mud%","DIRT","Grade"))
        for r in sorted(reports, key=lambda x: x.dirt_score):
            print(f"{r.name[:40]:<40} {r.rms_db:>6.1f} {r.crest_db:>6.1f} "
                  f"{r.dr_std:>5.2f} {r.mud_ratio:>6.2f} {r.dirt_score:>5.1f} {r.grade}")


# ──────────────────────────────────────────────────────────────────────────────
def main():
    wav_files = sorted(INPUT_DIR.glob("*.wav"))
    if not wav_files:
        print(f"[ERROR] No WAV files in {INPUT_DIR}"); return

    print(f"\n[INFO] Analyzing {len(wav_files)} track(s) in {INPUT_DIR}\n")
    reports = []
    for p in wav_files:
        print(f"  → {p.name}")
        r = analyze_track(p)
        stem    = r.name.replace(" ", "_").replace("/","_")
        out_png = OUT_DIR / f"dirt_report_{stem}.png"
        plot_single(r, out_png)
        reports.append(r)

    print(f"\n  Generating summary…")
    plot_summary(reports, OUT_DIR / "dirt_summary.png")
    print_report(reports)
    print(f"\n[DONE] Saved to {OUT_DIR}\n")

if __name__ == "__main__":
    main()
