import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
analyze_plastic.py
==================
Детектор «пластика» на высоких нотах духовых/хора в AI-генерированной музыке.

«Пластик» — это специфический AI-артефакт:
  ▸ Реальная медь/хор: гармоники слегка нерегулярны (inharmonicity),
    между гармониками есть живой шум («дыхание»), амплитуда имеет
    натуральное вибрато 4–7 Hz.
  ▸ AI-звук: идеально регулярные гармоники, стерильная тишина между ними,
    слишком ровная или неестественно модулированная амплитуда.
    На высоких нотах модель «ломается» и добавляет артефакт — «пластик».

Алгоритмы:
  1. High-note detection   — обнаружение кадров где доминируют частоты >800 Hz
  2. Harmonic regularity   — насколько гармоники близки к идеальному ряду 1x,2x,3x…
                             реал=нерегулярно (inharmonic), AI=идеально регулярно
  3. Inter-harmonic noise  — уровень шума МЕЖДУ гармониками
                             реал=высокий (дыхание), AI=стерильно низкий
  4. Spectral smoothness   — дисперсия вокруг пика: реал=текстурировано, AI=гладко
  5. Amplitude modulation  — анализ огибающей в полосе высоких нот
                             реал=4–7 Hz вибрато, AI=либо 0 Hz либо аномальные частоты
  6. Spectral flux HF      — резкие изменения спектра >1 kHz при переходах нот
  7. Phase coherence       — фазовая когерентность STFT (слишком высокая = синтетика)
  8. Harmonic decay shape  — форма затухания гармоник (слишком линейная = AI)

Plastic Score:
  0–25   → NATURAL  (живой звук)
  25–50  → MILD     (лёгкий пластик, некритично)
  50–75  → PLASTIC  (заметно на слух)
  75–100 → VERY PLASTIC (грубый артефакт)

Выходные файлы:
  analysis/plastic_<stem>.png        — детальный отчёт
  analysis/plastic_summary.png       — сравнение треков
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
from typing import List, Tuple, Dict

ROOT      = Path(__file__).parent
INPUT_DIR = ROOT / "sound" / "wav_input"
OUT_DIR   = ROOT / "analysis"
OUT_DIR.mkdir(exist_ok=True)

FRAME_MS  = 100    # короткие кадры для точного временно́го разрешения
HOP_MS    = 50

# Пороги «высокой ноты» — доминирование частот выше этой границы
HN_THRESH_HZ  = 800    # если спектральный центроид > этого — «высокая нота»
HN_RATIO_THR  = 0.25   # доля энергии выше 800 Hz должна быть > этого

# Диапазон типичных нот духовых/хора: сопрано/флейта до ~2 kHz, медь до ~1.5 kHz
BRASS_LO  = 400
BRASS_HI  = 4000

BG, PANEL, GRID = "#0d0d0d", "#161616", "#252525"
NAT_C  = "#4ade80"   # NATURAL
MILD_C = "#facc15"   # MILD
PLAS_C = "#f97316"   # PLASTIC
VPLA_C = "#ef4444"   # VERY PLASTIC
ACCENT = "#c084fc"


# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class PlasticFrame:
    t:                float
    is_high_note:     bool     # кадр с высокой нотой
    centroid_hz:      float    # спектральный центроид
    harmonic_reg:     float    # регулярность гармоник (0=хаос, 1=идеал/пластик)
    inter_harm_noise: float    # шум между гармониками (высокий=живой)
    spectral_smooth:  float    # гладкость спектра (высокий=пластик)
    am_rate_hz:       float    # частота AM модуляции огибающей
    am_naturalness:   float    # 0=неест., 1=естественно (4-7 Hz вибрато)
    hf_flux:          float    # спектральный flux в HF (резкие изменения)
    phase_coh:        float    # фазовая когерентность (высокий=синтетика)
    plastic_score:    float    # итоговый 0-100


@dataclass
class PlasticReport:
    name:          str
    sr:            int
    duration_s:    float

    frames:        List[PlasticFrame] = field(default_factory=list)

    # Временны́е серии
    t_arr:         np.ndarray = field(default_factory=lambda: np.array([]))
    plastic_arr:   np.ndarray = field(default_factory=lambda: np.array([]))
    hn_mask:       np.ndarray = field(default_factory=lambda: np.array([]))  # bool
    centroid_arr:  np.ndarray = field(default_factory=lambda: np.array([]))
    hreg_arr:      np.ndarray = field(default_factory=lambda: np.array([]))
    noise_arr:     np.ndarray = field(default_factory=lambda: np.array([]))
    smooth_arr:    np.ndarray = field(default_factory=lambda: np.array([]))
    am_nat_arr:    np.ndarray = field(default_factory=lambda: np.array([]))
    flux_hf_arr:   np.ndarray = field(default_factory=lambda: np.array([]))
    pcoh_arr:      np.ndarray = field(default_factory=lambda: np.array([]))

    # Агрегаты только по high-note кадрам
    hn_avg_plastic:  float = 0.0
    hn_peak_plastic: float = 0.0
    hn_p95_plastic:  float = 0.0
    hn_fraction:     float = 0.0   # % кадров с высокими нотами

    top_plastic:  List[Tuple[float, float]] = field(default_factory=list)

    # Полный спектр
    freqs:        np.ndarray = field(default_factory=lambda: np.array([]))
    spectrum_db:  np.ndarray = field(default_factory=lambda: np.array([]))


# ──────────────────────────────────────────────────────────────────────────────
def mono(data):
    return data.mean(axis=1) if data.ndim > 1 else data


def spectral_centroid(f, pxx):
    total = np.sum(pxx)
    if total < 1e-30:
        return 0.0
    return float(np.sum(f * pxx) / total)


def detect_fundamental(f, pxx, lo=100, hi=2000):
    """Находим доминирующий пик в диапазоне lo-hi Hz."""
    mask = (f >= lo) & (f <= hi)
    if mask.sum() == 0:
        return None
    idx = np.argmax(pxx[mask])
    return float(f[mask][idx])


def harmonic_regularity(f, pxx, f0, n_harm=8):
    """
    Насколько гармоники close to f0*1, f0*2, f0*3…?
    Возвращает 0..1, где 1 = идеально регулярные (пластик).
    Метод: для каждой гармоники f0*k ищем ближайший пик
    и смотрим на отклонение.
    """
    if f0 is None or f0 < 50:
        return 0.0

    deviations = []
    for k in range(2, n_harm + 1):
        ideal = f0 * k
        if ideal > f[-1]:
            break
        # Окно поиска: ±5% от идеальной
        win = ideal * 0.05
        mask = (f >= ideal - win) & (f <= ideal + win)
        if mask.sum() < 2:
            deviations.append(win)   # максимальное отклонение
            continue
        # Взвешенный центр пика
        p_sub = pxx[mask]
        f_sub = f[mask]
        weighted = float(np.sum(f_sub * p_sub) / (np.sum(p_sub) + 1e-30))
        deviations.append(abs(weighted - ideal))

    if not deviations:
        return 0.5
    # Нормируем: малое отклонение = высокая регулярность (пластик)
    mean_dev_ratio = np.mean(deviations) / (f0 * 0.05 + 1e-9)
    # 0 = нет отклонений (идеал/пластик) → 1; большое отклонение → 0
    regularity = float(np.clip(1.0 - mean_dev_ratio, 0, 1))
    return regularity


def inter_harmonic_noise(f, pxx, f0, n_harm=6):
    """
    Уровень шума МЕЖДУ гармониками (midpoints between harmonics).
    Высокий уровень = живой звук (дыхание инструмента).
    Низкий уровень = стерильный AI-звук.
    Возвращает отношение: inter_noise / harmonic_peak (0..1)
    """
    if f0 is None or f0 < 50:
        return 0.5

    harm_powers = []
    noise_powers = []

    for k in range(1, n_harm + 1):
        ideal = f0 * k
        if ideal > f[-1] * 0.9:
            break
        # Пик гармоники
        win = max(f0 * 0.04, 10)
        mh = (f >= ideal - win) & (f <= ideal + win)
        if mh.sum() > 0:
            harm_powers.append(float(np.max(pxx[mh])))

        # Шум между k и k+1 гармониками (середина)
        if k < n_harm:
            mid = ideal + f0 * 0.5
            mw = f0 * 0.1
            mn = (f >= mid - mw) & (f <= mid + mw)
            if mn.sum() > 0:
                noise_powers.append(float(np.mean(pxx[mn])))

    if not harm_powers or not noise_powers:
        return 0.3
    h_avg = np.mean(harm_powers)
    n_avg = np.mean(noise_powers)
    ratio = float(n_avg / (h_avg + 1e-30))
    return float(np.clip(ratio, 0, 1))


def spectral_local_smoothness(f, pxx, lo=800, hi=5000):
    """
    Гладкость спектра в зоне высоких нот.
    Считаем 2-ю производную логарифмического спектра.
    Низкая — слишком гладко (пластик). Высокая — живая текстура.
    """
    mask = (f >= lo) & (f <= hi)
    if mask.sum() < 10:
        return 0.5
    lp = np.log10(pxx[mask] + 1e-30)
    d2 = np.diff(lp, n=2)
    return float(np.std(d2))


def amplitude_modulation_analysis(envelope, sr_env, expected_vibrato=(4.0, 7.0)):
    """
    Анализирует огибающую сигнала на предмет AM модуляции.
    Возвращает:
      am_rate_hz   — доминирующая частота модуляции
      naturalness  — 0..1 (1 = натуральное вибрато 4-7 Hz)
    """
    if len(envelope) < 16:
        return 0.0, 0.5

    # Нормируем и убираем DC
    env = envelope - envelope.mean()
    if env.std() < 1e-9:
        return 0.0, 0.0   # нет модуляции вообще = неестественно ровно

    # FFT огибающей
    n = len(env)
    sp = np.abs(np.fft.rfft(env * np.hanning(n)))
    f_env = np.fft.rfftfreq(n, 1.0 / sr_env)

    # Доминирующая частота (исключаем DC)
    mask = (f_env >= 0.5) & (f_env <= 20)
    if mask.sum() == 0:
        return 0.0, 0.5
    dom_idx = np.argmax(sp[mask])
    am_rate = float(f_env[mask][dom_idx])

    # Naturalness: 4-7 Hz = хорошо (вибрато), иначе — плохо
    lo_v, hi_v = expected_vibrato
    if lo_v <= am_rate <= hi_v:
        naturalness = 1.0
    elif am_rate < 1.0:
        naturalness = 0.1   # почти нет вибрато = пластик
    elif am_rate > 15.0:
        naturalness = 0.1   # слишком быстрая модуляция = артефакт
    else:
        # плавный спад
        dist = min(abs(am_rate - lo_v), abs(am_rate - hi_v))
        naturalness = float(max(0, 1.0 - dist / 5.0))

    return am_rate, naturalness


def phase_coherence_stft(frame: np.ndarray, sr: int, lo=800, hi=5000):
    """
    Фазовая когерентность в зоне высоких частот.
    Использует overlapping STFT: если фаза слишком когерентна между
    соседними фреймами — это признак синтетики/AI.
    Возвращает 0..1, где 1 = максимально когерентно (пластик).
    """
    if len(frame) < 512:
        return 0.5
    n_fft = min(512, len(frame) // 2)
    hop   = n_fft // 4
    # Разбить frame на под-кадры
    sub_specs = []
    for start in range(0, len(frame) - n_fft, hop):
        chunk = frame[start:start + n_fft] * np.hanning(n_fft)
        sub_specs.append(np.fft.rfft(chunk))

    if len(sub_specs) < 3:
        return 0.5

    f_bins = np.fft.rfftfreq(n_fft, 1/sr)
    fmask  = (f_bins >= lo) & (f_bins <= hi)
    if fmask.sum() == 0:
        return 0.5

    # Разность фаз между соседними фреймами
    phases = np.array([np.angle(s[fmask]) for s in sub_specs])
    phase_diffs = np.diff(phases, axis=0)
    # Нормируем в -π..π
    phase_diffs = (phase_diffs + np.pi) % (2*np.pi) - np.pi
    # Когерентность = насколько стабильны разности фаз
    coherence = float(1.0 - np.std(phase_diffs) / np.pi)
    return float(np.clip(coherence, 0, 1))


def plastic_score_from_components(hreg, inter_noise, smooth, am_nat, hf_flux, pcoh,
                                   is_high_note: bool) -> float:
    """
    Plastic Score 0..100.
    Высокий hreg, низкий inter_noise, высокий smooth, низкий am_nat,
    высокий pcoh → пластик.
    """
    if not is_high_note:
        # На низких нотах plastic score меньший вес
        weight = 0.4
    else:
        weight = 1.0

    # Компоненты: каждый 0..100 где 100 = максимально пластиково
    s_hreg   = hreg * 100                  # высокая регулярность → пластик
    s_noise  = (1.0 - inter_noise) * 100   # низкий шум → пластик
    s_smooth = float(np.clip((1.0 - smooth / 0.05) * 100, 0, 100))  # слишком гладко
    s_amnat  = (1.0 - am_nat) * 100        # ненатуральная модуляция
    s_pcoh   = pcoh * 100                  # высокая когерентность

    score = (
        s_hreg   * 0.25 +
        s_noise  * 0.25 +
        s_smooth * 0.20 +
        s_amnat  * 0.15 +
        s_pcoh   * 0.15
    )
    return float(np.clip(score * weight, 0, 100))


def plastic_grade(score: float) -> Tuple[str, str]:
    if score < 25:  return "NATURAL",      NAT_C
    if score < 50:  return "MILD",         MILD_C
    if score < 75:  return "PLASTIC",      PLAS_C
    return              "VERY PLASTIC",    VPLA_C


def compute_full_spectrum(s, sr):
    nperseg = min(131072, len(s))
    f, pxx = sig.welch(s, fs=sr, nperseg=nperseg, noverlap=nperseg//2,
                       window="hann", scaling="density")
    db = 10 * np.log10(pxx + 1e-12)
    k = np.ones(60) / 60
    return f, np.convolve(db, k, mode="same")


# ──────────────────────────────────────────────────────────────────────────────
def analyze_plastic(path: Path) -> PlasticReport:
    data, sr = sndfile.read(str(path))
    s = mono(data).astype(np.float64)
    dur = len(s) / sr

    frame_len = int(sr * FRAME_MS / 1000)
    hop_len   = int(sr * HOP_MS   / 1000)
    n_frames  = (len(s) - frame_len) // hop_len + 1

    # Для AM-анализа: строим огибающую через Hilbert с окнами
    # Окно для AM = 3 секунды вокруг текущего кадра
    am_win_frames = int(3.0 / (HOP_MS / 1000))

    f_full, sp_full = compute_full_spectrum(s, sr)

    # Сначала считаем все PSD и конвертируем огибающую
    all_frames = []
    psd_list   = []
    env_list   = []

    print(f"    Pass 1: computing PSDs ({n_frames} frames)…")
    for i in range(n_frames):
        start = i * hop_len
        end   = start + frame_len
        if end > len(s):
            break
        frame = s[start:end]
        t     = start / sr

        # PSD кадра
        nperseg = min(2048, len(frame))
        f, pxx  = sig.welch(frame, fs=sr, nperseg=nperseg, window="hann", scaling="density")

        # Огибающая кадра: RMS в полосе 800–4000 Hz
        sos_hf = sig.butter(4, [BRASS_LO/(sr/2), BRASS_HI/(sr/2)], btype="band", output="sos")
        hf_filt = sig.sosfilt(sos_hf, frame)
        env_rms = float(np.sqrt(np.mean(hf_filt**2)))

        psd_list.append((f, pxx))
        env_list.append(env_rms)
        all_frames.append(t)

    env_arr   = np.array(env_list)
    # Нормируем огибающую для AM-анализа
    env_norm  = env_arr / (env_arr.max() + 1e-9)
    env_sr    = 1000.0 / HOP_MS   # "sample rate" огибающей

    print(f"    Pass 2: computing plastic metrics…")
    frames = []
    prev_pxx_hf = None

    for i, (t, (f, pxx)) in enumerate(zip(all_frames, psd_list)):
        frame = s[i*hop_len:i*hop_len + frame_len]

        # Спектральный центроид
        sc = spectral_centroid(f, pxx)

        # Доля энергии выше HN_THRESH_HZ
        df_val = f[1] - f[0] if len(f) > 1 else 1.0
        total_pwr = float(np.sum(pxx) * df_val) + 1e-30
        hf_mask   = f >= HN_THRESH_HZ
        hf_pwr    = float(np.sum(pxx[hf_mask]) * df_val)
        is_hn     = (hf_pwr / total_pwr) > HN_RATIO_THR

        # Фундаментал
        f0 = detect_fundamental(f, pxx, lo=BRASS_LO//2, hi=BRASS_HI//2)

        # 1. Гармоническая регулярность
        hreg = harmonic_regularity(f, pxx, f0)

        # 2. Межгармонический шум
        inter_noise = inter_harmonic_noise(f, pxx, f0)

        # 3. Гладкость спектра
        smooth = spectral_local_smoothness(f, pxx)

        # 4. AM naturalness (из ±am_win_frames/2 кадров)
        lo_i = max(0, i - am_win_frames // 2)
        hi_i = min(len(env_norm), i + am_win_frames // 2)
        env_chunk = env_norm[lo_i:hi_i]
        am_rate, am_nat = amplitude_modulation_analysis(env_chunk, env_sr)

        # 5. HF Spectral Flux
        pxx_hf = pxx[f >= BRASS_LO]
        if prev_pxx_hf is not None and len(prev_pxx_hf) == len(pxx_hf):
            curr_n = pxx_hf / (np.sum(pxx_hf) + 1e-30)
            prev_n = prev_pxx_hf / (np.sum(prev_pxx_hf) + 1e-30)
            hf_flux = float(np.sqrt(np.sum((curr_n - prev_n)**2)))
        else:
            hf_flux = 0.0
        prev_pxx_hf = pxx_hf.copy()

        # 6. Phase coherence
        pcoh = phase_coherence_stft(frame, sr)

        # Plastic score
        ps = plastic_score_from_components(hreg, inter_noise, smooth, am_nat,
                                           hf_flux, pcoh, is_hn)

        frames.append(PlasticFrame(
            t=t, is_high_note=is_hn, centroid_hz=sc,
            harmonic_reg=hreg, inter_harm_noise=inter_noise,
            spectral_smooth=smooth, am_rate_hz=am_rate, am_naturalness=am_nat,
            hf_flux=hf_flux, phase_coh=pcoh, plastic_score=ps
        ))

    if not frames:
        return PlasticReport(name=path.stem, sr=sr, duration_s=dur,
                             freqs=f_full, spectrum_db=sp_full)

    t_arr      = np.array([fm.t             for fm in frames])
    ps_arr     = np.array([fm.plastic_score for fm in frames])
    hn_arr     = np.array([fm.is_high_note  for fm in frames])
    cen_arr    = np.array([fm.centroid_hz   for fm in frames])
    hreg_arr   = np.array([fm.harmonic_reg  for fm in frames]) * 100
    noise_arr  = np.array([fm.inter_harm_noise for fm in frames]) * 100
    smooth_arr = np.array([fm.spectral_smooth  for fm in frames])
    amnat_arr  = np.array([fm.am_naturalness   for fm in frames]) * 100
    flux_arr   = np.array([fm.hf_flux          for fm in frames]) * 100
    pcoh_arr   = np.array([fm.phase_coh        for fm in frames]) * 100

    # Агрегаты только по high-note кадрам
    hn_ps = ps_arr[hn_arr]
    if len(hn_ps) == 0:
        hn_ps = ps_arr

    hn_avg  = float(hn_ps.mean())
    hn_peak = float(hn_ps.max())
    hn_p95  = float(np.percentile(hn_ps, 95))
    hn_frac = float(hn_arr.mean()) * 100

    # Топ-5 пластиковых моментов (только среди high-note кадров)
    hn_idx = np.where(hn_arr)[0]
    if len(hn_idx) == 0:
        hn_idx = np.arange(len(frames))
    top_idx   = hn_idx[np.argsort(ps_arr[hn_idx])[::-1][:5]]
    top_plastic = [(float(t_arr[i]), float(ps_arr[i])) for i in top_idx]

    return PlasticReport(
        name         = path.stem,
        sr           = sr,
        duration_s   = dur,
        frames       = frames,
        t_arr        = t_arr,
        plastic_arr  = ps_arr,
        hn_mask      = hn_arr,
        centroid_arr = cen_arr,
        hreg_arr     = hreg_arr,
        noise_arr    = noise_arr,
        smooth_arr   = smooth_arr,
        am_nat_arr   = amnat_arr,
        flux_hf_arr  = flux_arr,
        pcoh_arr     = pcoh_arr,
        hn_avg_plastic  = hn_avg,
        hn_peak_plastic = hn_peak,
        hn_p95_plastic  = hn_p95,
        hn_fraction     = hn_frac,
        top_plastic  = top_plastic,
        freqs        = f_full,
        spectrum_db  = sp_full,
    )


# ──────────────────────────────────────────────────────────────────────────────
def ax_style(ax, title=""):
    ax.set_facecolor(PANEL)
    if title:
        ax.set_title(title, color="#bbb", fontsize=8.5, pad=5, fontweight="bold")
    ax.tick_params(colors="#555", labelsize=7)
    ax.spines[:].set_color(GRID)
    ax.grid(True, color=GRID, linewidth=0.4, linestyle="--")
    for lbl in ax.get_xticklabels() + ax.get_yticklabels():
        lbl.set_color("#555")


def plot_plastic(r: PlasticReport, out_path: Path):
    fig = plt.figure(figsize=(18, 16), facecolor=BG)
    gp, gpc = plastic_grade(r.hn_peak_plastic)
    ga, gac = plastic_grade(r.hn_avg_plastic)

    fig.suptitle(
        f"Plastic Artifact Analysis  ·  {r.name}\n"
        f"HIGH NOTES  Peak: {r.hn_peak_plastic:.1f} [{gp}]   "
        f"Avg: {r.hn_avg_plastic:.1f} [{ga}]   "
        f"P95: {r.hn_p95_plastic:.1f}   "
        f"HN coverage: {r.hn_fraction:.0f}%",
        color="#e0e0e0", fontsize=12, fontweight="bold", y=0.995
    )

    gs = gridspec.GridSpec(5, 3, figure=fig, hspace=0.60, wspace=0.38,
                           left=0.06, right=0.97, top=0.95, bottom=0.04)

    # 1. Plastic Timeline ──────────────────────────────────────────────────────
    ax_ps = fig.add_subplot(gs[0, :])
    # Фоновая заливка — где high notes
    for i in range(len(r.t_arr)):
        if r.hn_mask[i]:
            x0 = r.t_arr[i]
            x1 = r.t_arr[i+1] if i+1 < len(r.t_arr) else x0 + HOP_MS/1000
            ax_ps.axvspan(x0, x1, color="#1a1a3a", alpha=0.6)

    # Gradients
    for i in range(len(r.t_arr)-1):
        c = plt.cm.RdYlGn_r(r.plastic_arr[i] / 100)
        ax_ps.fill_between(r.t_arr[i:i+2], 0, r.plastic_arr[i:i+2], color=c, alpha=0.75)
    ax_ps.plot(r.t_arr, r.plastic_arr, color="white", lw=0.6, alpha=0.4)

    for thr, col, lbl in [(25, NAT_C, "NATURAL"), (50, MILD_C, "MILD"),
                           (75, PLAS_C, "PLASTIC")]:
        ax_ps.axhline(thr, color=col, lw=0.8, linestyle="--", alpha=0.5)

    # Топ пластиковые моменты
    for t_top, ps_top in r.top_plastic:
        g_, gc_ = plastic_grade(ps_top)
        mm, ss = int(t_top//60), int(t_top%60)
        ax_ps.annotate(
            f"{mm:02d}:{ss:02d}\n{ps_top:.0f}",
            xy=(t_top, ps_top), xytext=(t_top, min(ps_top+12, 98)),
            color=VPLA_C, fontsize=6.5, ha="center",
            arrowprops=dict(arrowstyle="-", color=VPLA_C, lw=0.8)
        )

    ax_ps.set_xlim(0, r.duration_s); ax_ps.set_ylim(0, 100)
    ax_ps.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_ps.set_ylabel("Plastic Score", color="#555", fontsize=8)
    # Легенда для подсветки high notes
    ax_ps.text(r.duration_s * 0.01, 93, "█ = high note region",
               color="#4040aa", fontsize=7, alpha=0.8)
    ax_style(ax_ps, f"Plastic Score Over Time  (frame={FRAME_MS}ms)  — HIGH NOTES highlighted")

    # 2. Spectral Centroid ────────────────────────────────────────────────────
    ax_cen = fig.add_subplot(gs[1, 0:2])
    ax_cen.fill_between(r.t_arr, 0, r.centroid_arr, color=ACCENT, alpha=0.3)
    ax_cen.plot(r.t_arr, r.centroid_arr, color=ACCENT, lw=1.0, alpha=0.9)
    ax_cen.axhline(HN_THRESH_HZ, color=MILD_C, lw=0.8, linestyle="--",
                   alpha=0.6, label=f"HN threshold {HN_THRESH_HZ} Hz")
    ax_cen.set_xlim(0, r.duration_s)
    ax_cen.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_cen.set_ylabel("Centroid (Hz)", color="#555", fontsize=8)
    ax_cen.legend(fontsize=6.5, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_cen, "Spectral Centroid — High Notes Detection")

    # 3. HN Coverage Pie ───────────────────────────────────────────────────────
    ax_pie = fig.add_subplot(gs[1, 2])
    ax_pie.set_facecolor(PANEL)
    hn_count = int(r.hn_mask.sum())
    non_count= int((~r.hn_mask).sum())
    if hn_count + non_count > 0:
        wedge_colors = ["#4040cc", "#1a1a2a"]
        ax_pie.pie([hn_count, non_count],
                   labels=[f"High notes\n{r.hn_fraction:.0f}%",
                            f"Other\n{100-r.hn_fraction:.0f}%"],
                   colors=wedge_colors, autopct=None,
                   textprops={"color": "#aaa", "fontsize": 8},
                   startangle=90, wedgeprops={"edgecolor": GRID})
    ax_pie.set_title("High Note Coverage", color="#bbb", fontsize=8.5, pad=5, fontweight="bold")

    # 4. Harmonic Regularity ──────────────────────────────────────────────────
    ax_hreg = fig.add_subplot(gs[2, 0])
    ax_hreg.plot(r.t_arr[r.hn_mask], r.hreg_arr[r.hn_mask],
                  color=VPLA_C, lw=1.2, alpha=0.9, label="High notes")
    ax_hreg.plot(r.t_arr[~r.hn_mask], r.hreg_arr[~r.hn_mask],
                  color="#444", lw=0.7, alpha=0.6, label="Other")
    ax_hreg.axhline(70, color=PLAS_C, lw=0.8, linestyle="--", alpha=0.5, label="plastic zone")
    ax_hreg.set_xlim(0, r.duration_s); ax_hreg.set_ylim(0, 105)
    ax_hreg.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_hreg.set_ylabel("Regularity %", color="#555", fontsize=8)
    ax_hreg.legend(fontsize=6, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_hreg, "Harmonic Regularity (high=plastic)")

    # 5. Inter-harmonic Noise ──────────────────────────────────────────────────
    ax_noise = fig.add_subplot(gs[2, 1])
    ax_noise.plot(r.t_arr[r.hn_mask], r.noise_arr[r.hn_mask],
                   color=NAT_C, lw=1.2, alpha=0.9, label="High notes")
    ax_noise.plot(r.t_arr[~r.hn_mask], r.noise_arr[~r.hn_mask],
                   color="#333", lw=0.7, alpha=0.6)
    ax_noise.axhline(5, color=VPLA_C, lw=0.8, linestyle="--", alpha=0.5, label="plastic zone (<5%)")
    ax_noise.set_xlim(0, r.duration_s); ax_noise.set_ylim(0)
    ax_noise.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_noise.set_ylabel("Inter-harm noise %", color="#555", fontsize=8)
    ax_noise.legend(fontsize=6, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_noise, "Inter-Harmonic Noise (low=plastic/sterile)")

    # 6. AM Naturalness ────────────────────────────────────────────────────────
    ax_am = fig.add_subplot(gs[2, 2])
    ax_am.plot(r.t_arr[r.hn_mask], r.am_nat_arr[r.hn_mask],
                color=MILD_C, lw=1.2, alpha=0.9, label="High notes")
    ax_am.plot(r.t_arr[~r.hn_mask], r.am_nat_arr[~r.hn_mask],
                color="#333", lw=0.7, alpha=0.6)
    ax_am.axhline(70, color=NAT_C, lw=0.8, linestyle="--", alpha=0.5, label="natural zone (>70%)")
    ax_am.set_xlim(0, r.duration_s); ax_am.set_ylim(0, 105)
    ax_am.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_am.set_ylabel("AM Naturalness %", color="#555", fontsize=8)
    ax_am.legend(fontsize=6, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_am, "AM Naturalness (4–7 Hz vibrato=natural, 0 Hz or chaos=plastic)")

    # 7. Phase Coherence ───────────────────────────────────────────────────────
    ax_pcoh = fig.add_subplot(gs[3, 0])
    ax_pcoh.plot(r.t_arr[r.hn_mask], r.pcoh_arr[r.hn_mask],
                  color="#38bdf8", lw=1.2, alpha=0.9, label="High notes")
    ax_pcoh.plot(r.t_arr[~r.hn_mask], r.pcoh_arr[~r.hn_mask],
                  color="#333", lw=0.7, alpha=0.6)
    ax_pcoh.axhline(75, color=PLAS_C, lw=0.8, linestyle="--", alpha=0.5, label="plastic zone")
    ax_pcoh.set_xlim(0, r.duration_s); ax_pcoh.set_ylim(0, 105)
    ax_pcoh.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_pcoh.set_ylabel("Phase Coherence %", color="#555", fontsize=8)
    ax_pcoh.legend(fontsize=6, facecolor="#111", edgecolor="#333", labelcolor="#aaa")
    ax_style(ax_pcoh, "Phase Coherence (high=synthetic/plastic)")

    # 8. HF Spectral Flux ──────────────────────────────────────────────────────
    ax_flux = fig.add_subplot(gs[3, 1])
    ax_flux.fill_between(r.t_arr, 0, r.flux_hf_arr, color="#f472b6", alpha=0.4)
    ax_flux.plot(r.t_arr, r.flux_hf_arr, color="#f472b6", lw=1.0, alpha=0.9)
    ax_flux.set_xlim(0, r.duration_s)
    ax_flux.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_flux.set_ylabel("HF Flux ×100", color="#555", fontsize=8)
    ax_style(ax_flux, "HF Spectral Flux (spikes = note transitions / artifacts)")

    # 9. Component summary bar ─────────────────────────────────────────────────
    ax_bar = fig.add_subplot(gs[3, 2])
    ax_bar.set_facecolor(PANEL)
    # Средние по high-note кадрам
    hn = r.hn_mask
    comp_labels = ["Harm.\nRegularity", "Sterile\n(1-Noise)", "Smooth\nSpectrum",
                   "Unnat.\nModulation", "Phase\nCoherence"]
    if hn.sum() > 0:
        hreg_avg  = float(r.hreg_arr[hn].mean())
        noise_avg = float((100 - r.noise_arr[hn]).mean())
        smooth_avg= float(np.clip((1 - r.smooth_arr[hn] / 0.05) * 100, 0, 100).mean())
        amnat_avg = float((100 - r.am_nat_arr[hn]).mean())
        pcoh_avg  = float(r.pcoh_arr[hn].mean())
    else:
        hreg_avg = noise_avg = smooth_avg = amnat_avg = pcoh_avg = 0.0
    comp_vals = [hreg_avg, noise_avg, smooth_avg, amnat_avg, pcoh_avg]
    bar_c = [VPLA_C if v > 65 else PLAS_C if v > 45 else MILD_C if v > 25 else NAT_C
             for v in comp_vals]
    ax_bar.barh(comp_labels, comp_vals, color=bar_c, alpha=0.85, height=0.55)
    ax_bar.axvline(50, color="#333", lw=0.8, linestyle="--")
    ax_bar.axvline(75, color="#555", lw=0.8, linestyle="--")
    for i, v in enumerate(comp_vals):
        ax_bar.text(v + 0.5, i, f"{v:.0f}", va="center", color="#aaa", fontsize=7)
    ax_bar.set_xlim(0, 105)
    ax_bar.set_xlabel("Avg score on high notes (100=plastic)", color="#555", fontsize=8)
    ax_style(ax_bar, "Plastic Components (High Notes only)")

    # 10. Heatmap ─────────────────────────────────────────────────────────────
    ax_heat = fig.add_subplot(gs[4, :])
    metric_names = ["Plastic", "Harm.Reg", "Sterile", "AM Unnat.", "Phase Coh.", "HF Flux"]
    def norm_row(arr):
        mx = arr.max()
        return arr / mx * 100 if mx > 0 else arr
    rows = [
        r.plastic_arr,
        r.hreg_arr,
        norm_row(100 - r.noise_arr),
        norm_row(100 - r.am_nat_arr),
        r.pcoh_arr,
        norm_row(r.flux_hf_arr),
    ]
    matrix = np.array(rows)
    im = ax_heat.imshow(matrix, aspect="auto", cmap="hot", vmin=0, vmax=100,
                         extent=[0, r.duration_s, -0.5, len(metric_names)-0.5],
                         origin="upper", interpolation="bilinear")
    # Подсветка high-note регионов
    for i in range(len(r.t_arr)):
        if r.hn_mask[i]:
            x0 = r.t_arr[i]
            x1 = r.t_arr[i+1] if i+1 < len(r.t_arr) else x0 + HOP_MS/1000
            ax_heat.axvspan(x0, x1, ymin=0.97, ymax=1.0, color="#4040ff", alpha=0.6)
    # Топ метки
    for t_top, ps_top in r.top_plastic:
        ax_heat.axvline(t_top, color=VPLA_C, lw=1.0, linestyle="--", alpha=0.7)
    ax_heat.set_yticks(range(len(metric_names)))
    ax_heat.set_yticklabels(metric_names, fontsize=8)
    ax_heat.set_xlabel("Time (s)", color="#555", fontsize=8)
    plt.colorbar(im, ax=ax_heat, orientation="vertical", fraction=0.008, pad=0.004)
    ax_style(ax_heat, "Plastic Components Heatmap  (red=plastic, black=natural)  | blue bar = high note region  | ▼ = peak plastic moments")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
def plot_plastic_summary(reports: List[PlasticReport], out_path: Path):
    n = len(reports)
    fig = plt.figure(figsize=(16, 9), facecolor=BG)
    fig.suptitle("Plastic Artifact Summary — High Notes Analysis",
                 color="#e0e0e0", fontsize=14, fontweight="bold", y=0.99)

    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.52, wspace=0.38,
                           left=0.07, right=0.97, top=0.94, bottom=0.07)

    names = [r.name[:35] for r in reports]
    tc    = [ACCENT, "#4ade80", "#facc15", "#38bdf8"]

    # A. Peak vs Avg ───────────────────────────────────────────────────────────
    ax_a = fig.add_subplot(gs[0, 0])
    x = np.arange(n)
    w = 0.28
    for i, r in enumerate(reports):
        gp_ = plastic_grade(r.hn_peak_plastic)[1]
        ga_ = plastic_grade(r.hn_avg_plastic)[1]
        ax_a.bar(i-w, r.hn_avg_plastic,  w*1.8, color=ga_,  alpha=0.55)
        ax_a.bar(i+w, r.hn_peak_plastic, w*1.8, color=gp_,  alpha=0.9)
        ax_a.text(i-w, r.hn_avg_plastic+1,  f"{r.hn_avg_plastic:.1f}", ha="center", color="#aaa", fontsize=7)
        ax_a.text(i+w, r.hn_peak_plastic+1, f"{r.hn_peak_plastic:.1f}", ha="center", color=gp_, fontsize=7, fontweight="bold")
    for thr, col in [(25,NAT_C),(50,MILD_C),(75,PLAS_C)]:
        ax_a.axhline(thr, color=col, lw=0.7, linestyle="--", alpha=0.45)
    ax_a.set_xticks(x); ax_a.set_xticklabels(names, fontsize=6.5, rotation=12)
    ax_a.set_ylim(0, 105)
    ax_a.legend(["Avg (bar left)","Peak (bar right)"],
                fontsize=7, facecolor="#111", edgecolor="#333", labelcolor="#ccc")
    ax_style(ax_a, "Plastic Score: Peak vs Avg (High Notes Only)")

    # B. Top dirty moments table ────────────────────────────────────────────────
    ax_b = fig.add_subplot(gs[0, 1])
    ax_b.axis("off"); ax_b.set_facecolor(PANEL)
    ax_b.set_title("Top Plastic Moments (High Notes)", color="#bbb", fontsize=9,
                    pad=5, fontweight="bold")
    y = 0.97
    for r in reports:
        ax_b.text(0.01, y, f"▶ {r.name[:32]}", color=ACCENT, fontsize=7.5,
                  va="top", fontweight="bold")
        y -= 0.10
        for rank, (t, ps) in enumerate(r.top_plastic[:3], 1):
            g_, _ = plastic_grade(ps)
            mm, ss = int(t//60), int(t%60)
            col_ = "#ef4444" if ps >= 75 else "#f97316" if ps >= 50 else "#facc15"
            ax_b.text(0.04, y, f"  #{rank}  {mm:02d}:{ss:02d}  score={ps:.1f}  [{g_}]",
                      color=col_, fontsize=7, va="top")
            y -= 0.09
        y -= 0.05

    # C. Overlaid timelines ────────────────────────────────────────────────────
    ax_c = fig.add_subplot(gs[1, :])
    for i, r in enumerate(reports):
        c = tc[i % len(tc)]
        gp_, _ = plastic_grade(r.hn_peak_plastic)
        lbl = f"{r.name[:34]}  [peak={r.hn_peak_plastic:.1f} {gp_}, avg={r.hn_avg_plastic:.1f}]"
        ax_c.plot(r.t_arr, r.plastic_arr, color=c, lw=1.3, alpha=0.82, label=lbl)
        # Подсветить high-note зоны слегка
        ax_c.fill_between(r.t_arr, r.plastic_arr,
                           where=r.hn_mask, color=c, alpha=0.08)

    for thr, col, lbl in [(25, NAT_C, "NATURAL"), (50, MILD_C, "MILD"), (75, PLAS_C, "PLASTIC")]:
        ax_c.axhline(thr, color=col, lw=0.8, linestyle="--", alpha=0.4)
        ax_c.text(0.5, thr+1, lbl, color=col, fontsize=6.5, alpha=0.6)

    ax_c.set_ylim(0, 100)
    ax_c.set_xlabel("Time (s)", color="#555", fontsize=8)
    ax_c.set_ylabel("Plastic Score", color="#555", fontsize=8)
    ax_c.legend(facecolor="#111", edgecolor="#333", labelcolor="#ccc",
                fontsize=7.5, loc="upper right")
    ax_style(ax_c, "Overlaid Plastic Timelines")

    plt.savefig(str(out_path), dpi=140, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    print(f"  [PNG] {out_path.name}")


# ──────────────────────────────────────────────────────────────────────────────
def print_report(reports: List[PlasticReport]):
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        console = Console()
        tbl = Table(title="[bold white]Plastic Artifact Analysis — High Notes[/bold white]",
                    box=box.ROUNDED, border_style="dim",
                    header_style="bold magenta", show_lines=True)
        tbl.add_column("Track",      style="cyan", max_width=36, no_wrap=True)
        tbl.add_column("HN%",        justify="right")
        tbl.add_column("Avg",        justify="right")
        tbl.add_column("Peak",       style="bold", justify="right")
        tbl.add_column("P95",        justify="right")
        tbl.add_column("Top#1",      justify="right")
        tbl.add_column("Score#1",    justify="right")

        gs_map = {"NATURAL": "bold green", "MILD": "bold yellow",
                  "PLASTIC": "bold red", "VERY PLASTIC": "bold red on dark_red"}

        for r in sorted(reports, key=lambda x: x.hn_peak_plastic, reverse=True):
            gp, _ = plastic_grade(r.hn_peak_plastic)
            ga, _ = plastic_grade(r.hn_avg_plastic)
            t1  = f"{int(r.top_plastic[0][0]//60):02d}:{int(r.top_plastic[0][0]%60):02d}" if r.top_plastic else "-"
            d1  = f"{r.top_plastic[0][1]:.1f}" if r.top_plastic else "-"
            tbl.add_row(
                r.name[:36],
                f"{r.hn_fraction:.0f}%",
                f"[{gs_map.get(ga,'white')}]{r.hn_avg_plastic:.1f}[/{gs_map.get(ga,'white')}]",
                f"[{gs_map.get(gp,'white')}]{r.hn_peak_plastic:.1f}[/{gs_map.get(gp,'white')}]",
                f"{r.hn_p95_plastic:.1f}",
                t1, d1,
            )
        console.print(); console.print(tbl)

        console.print("\n[bold]🎵 Top Plastic Moments on High Notes[/bold]")
        for r in sorted(reports, key=lambda x: x.hn_peak_plastic, reverse=True):
            console.print(f"\n  [cyan]{r.name}[/cyan]  (HN coverage: {r.hn_fraction:.0f}%)")
            for rank, (t, ps) in enumerate(r.top_plastic, 1):
                g_, _ = plastic_grade(ps)
                mm, ss = int(t//60), int(t%60)
                col = "red" if ps >= 75 else "yellow" if ps >= 50 else "green"
                console.print(f"    #{rank}  [{col}]{mm:02d}:{ss:02d}[/{col}]  plastic={ps:.1f}  [{g_}]")

    except ImportError:
        for r in sorted(reports, key=lambda x: x.hn_peak_plastic, reverse=True):
            print(f"\n{r.name}  HN={r.hn_fraction:.0f}%  avg={r.hn_avg_plastic:.1f}  peak={r.hn_peak_plastic:.1f}")
            for rank, (t, ps) in enumerate(r.top_plastic, 1):
                print(f"  #{rank}  t={int(t//60):02d}:{int(t%60):02d}  plastic={ps:.1f}")


# ──────────────────────────────────────────────────────────────────────────────
def main():
    wav_files = sorted(INPUT_DIR.glob("*.wav"))
    if not wav_files:
        print(f"[ERROR] No WAV files in {INPUT_DIR}"); return

    print(f"\n[INFO] Plastic analysis of {len(wav_files)} tracks\n")
    reports = []
    for p in wav_files:
        print(f"  → {p.name}")
        r = analyze_plastic(p)
        stem = r.name.replace(" ","_").replace("/","_")
        plot_plastic(r, OUT_DIR / f"plastic_{stem}.png")
        reports.append(r)
        print(f"    HN={r.hn_fraction:.0f}%  avg={r.hn_avg_plastic:.1f}  peak={r.hn_peak_plastic:.1f}  p95={r.hn_p95_plastic:.1f}")

    print(f"\n  Generating summary…")
    plot_plastic_summary(reports, OUT_DIR / "plastic_summary.png")
    print_report(reports)
    print(f"\n[DONE] {OUT_DIR}\n")

if __name__ == "__main__":
    main()
