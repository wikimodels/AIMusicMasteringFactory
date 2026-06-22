import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

# ─── Try librosa imports (optional but powerful) ───
try:
    import librosa
    import librosa.display
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False
    print("[WARN] librosa not found — skipping spectral rolloff/centroid")

try:
    import pyloudnorm as pyln
    HAS_PYLN = True
except ImportError:
    HAS_PYLN = False
    print("[WARN] pyloudnorm not found — skipping LUFS")

# ─── File ──────────────────────────────────────────
ROOT   = Path(__file__).parent
FPATH  = ROOT / "Slow piano Jazz v 1.wav"
OUT    = ROOT / "analysis"
OUT.mkdir(exist_ok=True)

print(f"Loading: {FPATH}")
data, sr = sf.read(str(FPATH))
print(f"  Sample rate : {sr} Hz")
print(f"  Samples     : {len(data)}")
print(f"  Duration    : {len(data)/sr:.2f} sec")
print(f"  Channels    : {data.shape[1] if data.ndim > 1 else 1}")

# Stereo → keep L/R for phase, mono for spectrum
if data.ndim > 1:
    L, R = data[:, 0], data[:, 1]
    mono = (L + R) / 2
else:
    L = R = mono = data

N_FULL = len(mono)
dur_sec = N_FULL / sr

# ════════════════════════════════════════════════════
#  1. LOUDNESS (LUFS, Peak, Crest)
# ════════════════════════════════════════════════════
peak_dbfs = 20 * np.log10(np.max(np.abs(data)) + 1e-12)
rms = np.sqrt(np.mean(mono**2))
rms_db = 20 * np.log10(rms + 1e-12)
crest = peak_dbfs - rms_db

print("\n── LOUDNESS ───────────────────────────────────")
print(f"  True Peak   : {peak_dbfs:+.2f} dBFS")
print(f"  RMS         : {rms_db:+.2f} dBFS")
print(f"  Crest Factor: {crest:.2f} dB")

lufs_val = None
if HAS_PYLN:
    meter = pyln.Meter(sr)
    stereo_data = np.stack([L, R], axis=1) if data.ndim > 1 else np.stack([mono, mono], axis=1)
    try:
        lufs_val = meter.integrated_loudness(stereo_data)
        print(f"  Integrated  : {lufs_val:.2f} LUFS")
    except Exception as e:
        print(f"  LUFS error  : {e}")

# ════════════════════════════════════════════════════
#  2. FULL-RANGE SPECTRUM (FFT, 20–20k Hz)
# ════════════════════════════════════════════════════
N_FFT = 131072
w = np.hanning(min(N_FFT, N_FULL))
sig = mono[:len(w)] * w
sp  = np.abs(np.fft.rfft(sig, n=N_FFT))
freqs = np.fft.rfftfreq(N_FFT, 1 / sr)

db_raw = 20 * np.log10(sp + 1e-9)
k = np.ones(120) / 120
db_smooth = np.convolve(db_raw, k, mode="same")

# Band energy breakdown
def band_rms(f_lo, f_hi):
    mask = (freqs >= f_lo) & (freqs < f_hi)
    return 20 * np.log10(np.sqrt(np.mean(sp[mask]**2)) + 1e-9)

bands = {
    "Sub-bass  (20–60 Hz)":   (20, 60),
    "Bass      (60–200 Hz)":  (60, 200),
    "Low-mid   (200–800 Hz)": (200, 800),
    "Mid       (800–3k Hz)":  (800, 3000),
    "High-mid  (3k–8k Hz)":  (3000, 8000),
    "Air/HF    (8k–20k Hz)": (8000, 20000),
}
print("\n── BAND ENERGY ────────────────────────────────")
band_vals = {}
for name, (lo, hi) in bands.items():
    val = band_rms(lo, hi)
    band_vals[name] = val
    bar = "█" * max(0, int((val + 80) / 4))
    print(f"  {name}: {val:+.1f} dB  {bar}")

# ════════════════════════════════════════════════════
#  3. DYNAMICS: Short-time RMS envelope
# ════════════════════════════════════════════════════
frame_s = 0.1   # 100 ms frames
frame_len = int(sr * frame_s)
n_frames = N_FULL // frame_len
rms_env = np.array([
    np.sqrt(np.mean(mono[i*frame_len:(i+1)*frame_len]**2))
    for i in range(n_frames)
])
rms_env_db = 20 * np.log10(rms_env + 1e-9)
t_env = np.arange(n_frames) * frame_s

# Dynamic range (P95 - P10)
dr = np.percentile(rms_env_db, 95) - np.percentile(rms_env_db, 10)
print(f"\n── DYNAMICS ───────────────────────────────────")
print(f"  Dynamic Range (P95-P10): {dr:.1f} dB")
print(f"  RMS env min : {rms_env_db.min():.1f} dBFS")
print(f"  RMS env max : {rms_env_db.max():.1f} dBFS")

# ════════════════════════════════════════════════════
#  4. STEREO PHASE CORRELATION over time
# ════════════════════════════════════════════════════
frame_phase = int(sr * 0.5)  # 500 ms
n_phase = N_FULL // frame_phase
corr_t = np.zeros(n_phase)
t_phase = np.arange(n_phase) * 0.5

for i in range(n_phase):
    s, e = i*frame_phase, (i+1)*frame_phase
    lf, rf = L[s:e], R[s:e]
    if np.std(lf) > 1e-7 and np.std(rf) > 1e-7:
        corr_t[i] = np.corrcoef(lf, rf)[0, 1]

phase_mean = corr_t.mean()
phase_min  = corr_t.min()
n_danger = np.sum(corr_t < 0.3)
print(f"\n── STEREO PHASE ───────────────────────────────")
print(f"  Mean correlation : {phase_mean:.3f}")
print(f"  Min  correlation : {phase_min:.3f}")
print(f"  Frames < 0.3 (phase danger): {n_danger} / {n_phase}")

# ════════════════════════════════════════════════════
#  5. CLIPPING / SATURATION CHECK
# ════════════════════════════════════════════════════
CLIP_THRESH = 0.99
clips = np.sum(np.abs(mono) >= CLIP_THRESH)
clip_pct = 100 * clips / N_FULL
print(f"\n── CLIPPING ───────────────────────────────────")
print(f"  Samples >= {CLIP_THRESH}: {clips} ({clip_pct:.3f}%)")
if clip_pct > 0.01:
    print("  ⚠️  CLIPPING DETECTED — Hard limiter hit!")
elif clip_pct > 0.001:
    print("  ⚠️  Minor saturation peaks")
else:
    print("  ✓  Clean — no hard clipping")

# ════════════════════════════════════════════════════
#  6. LIBROSA: Spectral Centroid, Rolloff, ZCR
# ════════════════════════════════════════════════════
if HAS_LIBROSA:
    y = mono.astype(np.float32)
    sc = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr, roll_percent=0.85)[0]
    zcr = librosa.feature.zero_crossing_rate(y)[0]
    t_lib = librosa.times_like(sc, sr=sr)

    print(f"\n── SPECTRAL FEATURES (librosa) ─────────────")
    print(f"  Centroid mean : {sc.mean():.0f} Hz")
    print(f"  Centroid std  : {sc.std():.0f} Hz")
    print(f"  Rolloff85 mean: {rolloff.mean():.0f} Hz")
    print(f"  ZCR mean      : {zcr.mean():.4f}")
    print(f"  => Brightness : {'BRIGHT' if sc.mean() > 2000 else 'DARK/WARM' if sc.mean() < 1200 else 'BALANCED'}")
else:
    t_lib, sc, rolloff, zcr = None, None, None, None

# ════════════════════════════════════════════════════
#  7. HIGH-RES HF TAIL (8k–20k Hz) — air shelf check
# ════════════════════════════════════════════════════
hf_mask = (freqs >= 8000) & (freqs <= 20000)
hf_db = db_smooth[hf_mask]
hf_freqs = freqs[hf_mask]
# Linear fit — slope of HF roll-off
if len(hf_freqs) > 10:
    log_hf = np.log10(hf_freqs)
    slope, intercept = np.polyfit(log_hf, hf_db, 1)
    print(f"\n── HIGH FREQ SHELF (8k–20k) ────────────────")
    print(f"  HF slope: {slope:.1f} dB/decade")
    if slope < -10:
        print("  ⚠️  Very dark — air shelf missing or suppressed")
    elif slope < -5:
        print("  ▸  Moderate roll-off — gentle warming OK")
    else:
        print("  ✓  Healthy air presence")

# ════════════════════════════════════════════════════
#  8. RESONANCE HUNTER (narrow peaks in spectrum)
# ════════════════════════════════════════════════════
print(f"\n── RESONANCE HUNTER ────────────────────────")
# Work in 100–5000 Hz range with fine bins
res_mask = (freqs >= 100) & (freqs <= 5000)
res_db = db_raw[res_mask]
res_f  = freqs[res_mask]
# Smooth baseline, find spikes above baseline
from scipy.ndimage import uniform_filter1d
baseline = uniform_filter1d(res_db, size=500)
peaks_above = res_db - baseline
peak_thresh = 8  # dB above local average
spike_idx = np.where(peaks_above > peak_thresh)[0]
if len(spike_idx) > 0:
    # cluster consecutive indices
    groups = []
    g = [spike_idx[0]]
    for idx in spike_idx[1:]:
        if idx - g[-1] < 50:
            g.append(idx)
        else:
            groups.append(g)
            g = [idx]
    groups.append(g)
    resonances = []
    for g in groups:
        center = g[np.argmax(peaks_above[g])]
        resonances.append((res_f[center], peaks_above[center]))
    resonances.sort(key=lambda x: -x[1])
    print(f"  Found {len(resonances)} resonance spike(s) >+{peak_thresh}dB above local baseline:")
    for fr, amp in resonances[:10]:
        print(f"    {fr:6.0f} Hz  +{amp:.1f} dB  ← {'LOW-MID MUD' if fr < 400 else 'NASAL/BOX' if fr < 1200 else 'PRESENCE BITE' if fr < 3000 else 'SIBILANCE'}")
else:
    print("  ✓  No severe resonance spikes found")

# ════════════════════════════════════════════════════
#  PLOT — 4-panel dark dashboard
# ════════════════════════════════════════════════════
BG, PL = "#0d0d0d", "#1a1a1a"
GR = "#2a2a2a"
C1, C2, C3, C4 = "#7ec8e3", "#c084fc", "#f59e0b", "#34d399"

fig = plt.figure(figsize=(16, 14), facecolor=BG)
fig.suptitle("Slow Piano Jazz v1 — Deep Frequency & Dynamics Autopsy", 
             color="#e0e0e0", fontsize=15, fontweight="bold", y=0.98)
gs = gridspec.GridSpec(3, 2, figure=fig, hspace=0.45, wspace=0.35)

# ── Panel 1: Full spectrum ─────────────────────────
ax1 = fig.add_subplot(gs[0, :])
ax1.set_facecolor(PL)
ax1.grid(True, color=GR, lw=0.5)
mask_all = (freqs >= 20) & (freqs <= 20000)
ax1.semilogx(freqs[mask_all], db_smooth[mask_all], color=C1, lw=1.5, label="Smoothed spectrum", alpha=0.9)
ax1.semilogx(freqs[mask_all], db_raw[mask_all], color=C1, lw=0.3, alpha=0.2)
# Band markers
zone_colors = ['#ef4444','#f59e0b','#84cc16','#22d3ee','#818cf8','#f472b6']
zone_ranges = [(20,60),(60,200),(200,800),(800,3000),(3000,8000),(8000,20000)]
zone_names  = ["Sub","Bass","Low-mid","Mid","Hi-mid","Air"]
for (lo, hi), zc, zn in zip(zone_ranges, zone_colors, zone_names):
    ax1.axvspan(lo, hi, color=zc, alpha=0.05)
    ax1.text((lo*hi)**0.5, ax1.get_ylim()[0]+3 if ax1.get_ylim()[0] > -200 else -100, zn, 
             color=zc, fontsize=7, ha='center', alpha=0.7)
# Resonance spikes
if len(spike_idx) > 0:
    for fr, amp in resonances[:5]:
        ax1.axvline(fr, color='#ef4444', lw=0.7, linestyle='--', alpha=0.6)
        ax1.text(fr, db_smooth[np.argmin(np.abs(freqs-fr))]+2, f"{fr:.0f}Hz", 
                 color='#ef4444', fontsize=6, rotation=90, va='bottom', ha='right')
ax1.set_xlim(20, 20000)
TICKS = [20,50,100,200,400,800,1000,2000,4000,8000,16000,20000]
TLABS = ["20","50","100","200","400","800","1k","2k","4k","8k","16k","20k"]
ax1.set_xticks(TICKS); ax1.set_xticklabels(TLABS, fontsize=8)
[l.set_color("#888") for l in ax1.get_xticklabels()+ax1.get_yticklabels()]
ax1.spines[:].set_color(GR)
ax1.set_xlabel("Frequency (Hz)", color="#888", fontsize=9)
ax1.set_ylabel("Level (dB)", color="#888", fontsize=9)
ax1.set_title("Full Spectrum (20Hz–20kHz) — Smoothed + Raw", color="#ccc", fontsize=10)
ax1.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=8)

# ── Panel 2: RMS Dynamics Envelope ────────────────
ax2 = fig.add_subplot(gs[1, 0])
ax2.set_facecolor(PL)
ax2.grid(True, color=GR, lw=0.5)
ax2.plot(t_env, rms_env_db, color=C2, lw=0.8, alpha=0.9)
ax2.fill_between(t_env, rms_env_db, rms_env_db.min(), color=C2, alpha=0.15)
ax2.axhline(np.percentile(rms_env_db, 95), color=C4, lw=1, linestyle='--', alpha=0.6, label=f"P95={np.percentile(rms_env_db,95):.1f}dB")
ax2.axhline(np.percentile(rms_env_db, 10), color=C3, lw=1, linestyle='--', alpha=0.6, label=f"P10={np.percentile(rms_env_db,10):.1f}dB")
[l.set_color("#888") for l in ax2.get_xticklabels()+ax2.get_yticklabels()]
ax2.spines[:].set_color(GR)
ax2.set_xlabel("Time (s)", color="#888", fontsize=9)
ax2.set_ylabel("RMS (dBFS)", color="#888", fontsize=9)
ax2.set_title(f"Dynamics Envelope  [DR={dr:.1f} dB]", color="#ccc", fontsize=10)
ax2.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=8)

# ── Panel 3: Stereo Phase Correlation ────────────
ax3 = fig.add_subplot(gs[1, 1])
ax3.set_facecolor(PL)
ax3.grid(True, color=GR, lw=0.5)
ax3.plot(t_phase, corr_t, color=C3, lw=1.0, alpha=0.9)
ax3.fill_between(t_phase, corr_t, 0, where=(corr_t < 0.3), color='#ef4444', alpha=0.3, label="Phase danger (<0.3)")
ax3.axhline(0.3, color='#ef4444', lw=1, linestyle='--', alpha=0.5)
ax3.axhline(0.7, color=C4,       lw=1, linestyle='--', alpha=0.4, label="Safe zone (>0.7)")
ax3.set_ylim(-0.5, 1.1)
[l.set_color("#888") for l in ax3.get_xticklabels()+ax3.get_yticklabels()]
ax3.spines[:].set_color(GR)
ax3.set_xlabel("Time (s)", color="#888", fontsize=9)
ax3.set_ylabel("L/R Correlation", color="#888", fontsize=9)
ax3.set_title(f"Stereo Phase Correlation  [mean={phase_mean:.2f}]", color="#ccc", fontsize=10)
ax3.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=8)

# ── Panel 4: Band Energy Bar Chart ────────────────
ax4 = fig.add_subplot(gs[2, 0])
ax4.set_facecolor(PL)
ax4.grid(True, color=GR, lw=0.5, axis='x')
band_names_short = ["Sub\n20-60", "Bass\n60-200", "Lo-mid\n200-800", "Mid\n800-3k", "Hi-mid\n3-8k", "Air\n8-20k"]
vals = list(band_vals.values())
bar_colors = ['#ef4444','#f59e0b','#84cc16','#22d3ee','#818cf8','#f472b6']
bars = ax4.barh(band_names_short, vals, color=bar_colors, alpha=0.8, edgecolor="#333")
for bar, v in zip(bars, vals):
    ax4.text(v+0.5, bar.get_y()+bar.get_height()/2, f"{v:+.1f}dB", 
             va='center', color='#ccc', fontsize=8)
[l.set_color("#888") for l in ax4.get_xticklabels()+ax4.get_yticklabels()]
ax4.spines[:].set_color(GR)
ax4.set_xlabel("Band RMS (dB)", color="#888", fontsize=9)
ax4.set_title("Band Energy Profile", color="#ccc", fontsize=10)

# ── Panel 5: Spectral Centroid / Rolloff over time ─
ax5 = fig.add_subplot(gs[2, 1])
ax5.set_facecolor(PL)
ax5.grid(True, color=GR, lw=0.5)
if HAS_LIBROSA and sc is not None:
    ax5.plot(t_lib, sc, color=C1, lw=0.8, alpha=0.9, label=f"Centroid (mean={sc.mean():.0f}Hz)")
    ax5.plot(t_lib, rolloff, color=C4, lw=0.8, alpha=0.7, label=f"Rolloff85 (mean={rolloff.mean():.0f}Hz)")
    ax5.axhline(sc.mean(), color=C1, lw=0.6, linestyle='--', alpha=0.4)
    [l.set_color("#888") for l in ax5.get_xticklabels()+ax5.get_yticklabels()]
    ax5.spines[:].set_color(GR)
    ax5.set_xlabel("Time (s)", color="#888", fontsize=9)
    ax5.set_ylabel("Hz", color="#888", fontsize=9)
    ax5.set_title("Spectral Centroid & Rolloff (Brightness over time)", color="#ccc", fontsize=10)
    ax5.legend(facecolor="#222", edgecolor="#444", labelcolor="#ccc", fontsize=8)
else:
    ax5.text(0.5, 0.5, "librosa not available\n(install librosa for centroid/rolloff)", 
             ha='center', va='center', color="#888", transform=ax5.transAxes)
    ax5.set_title("Spectral Centroid & Rolloff", color="#ccc", fontsize=10)
    ax5.spines[:].set_color(GR)

# ─── Annotation box with key findings ─────────────
issues = []
if clip_pct > 0.01:  issues.append(f"⚡ CLIPPING: {clip_pct:.3f}%")
if lufs_val is not None:
    if lufs_val > -8: issues.append(f"🔴 Over-limited LUFS={lufs_val:.1f}")
    elif lufs_val > -12: issues.append(f"🟡 Hot master LUFS={lufs_val:.1f}")
    else: issues.append(f"✅ LUFS={lufs_val:.1f} (streaming OK)")
if dr < 6: issues.append(f"⚡ Very compressed DR={dr:.1f}dB")
elif dr < 10: issues.append(f"🟡 Moderate DR={dr:.1f}dB")
else: issues.append(f"✅ Dynamic DR={dr:.1f}dB")
if phase_mean < 0.5: issues.append(f"⚡ Phase issues mean={phase_mean:.2f}")
if HAS_LIBROSA and sc is not None:
    if sc.mean() < 1200: issues.append(f"🔵 Dark/warm centroid={sc.mean():.0f}Hz")
    elif sc.mean() > 2500: issues.append(f"🟡 Bright/harsh centroid={sc.mean():.0f}Hz")
if len(spike_idx) > 0:
    top_res = resonances[0]
    issues.append(f"⚠️  Top resonance: {top_res[0]:.0f}Hz (+{top_res[1]:.1f}dB)")

summary_text = "\n".join(issues) if issues else "No critical issues"
fig.text(0.5, 0.01, summary_text, ha='center', va='bottom', 
         fontsize=9, color="#e0e0e0", 
         bbox=dict(facecolor="#1a1a2e", edgecolor="#444", alpha=0.8, pad=6))

# ─── Save ─────────────────────────────────────────
out_path = OUT / "Slow_Piano_Jazz_v1_deep_analysis.png"
plt.savefig(str(out_path), dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
plt.close()
print(f"\n[DONE] Chart saved: {out_path}")

# ════════════════════════════════════════════════════
#  FINAL TEXT REPORT
# ════════════════════════════════════════════════════
print("\n" + "="*60)
print("  DIAGNOSIS SUMMARY")
print("="*60)
print(f"  File          : Slow piano Jazz v 1.wav")
print(f"  Duration      : {dur_sec:.1f}s  ({dur_sec/60:.1f} min)")
print(f"  Sample Rate   : {sr} Hz")
print(f"  True Peak     : {peak_dbfs:+.2f} dBFS")
print(f"  RMS           : {rms_db:+.2f} dBFS")
print(f"  Crest Factor  : {crest:.1f} dB")
if lufs_val is not None:
    print(f"  LUFS          : {lufs_val:.2f}")
print(f"  Dynamic Range : {dr:.1f} dB (P95-P10)")
print(f"  Phase mean    : {phase_mean:.3f}")
print(f"  Clip samples  : {clips} ({clip_pct:.4f}%)")
if HAS_LIBROSA and sc is not None:
    print(f"  Sp. Centroid  : {sc.mean():.0f} Hz")
    print(f"  HF Rolloff85  : {rolloff.mean():.0f} Hz")
print(f"\n  Band breakdown:")
for name, val in band_vals.items():
    print(f"    {name}: {val:+.1f} dB")
print(f"\n  HF slope (8k-20k): {slope:.1f} dB/decade" if len(spike_idx) >= 0 and 'slope' in dir() else "")
if len(spike_idx) > 0:
    print(f"\n  Resonance spikes (top {min(5,len(resonances))}):")
    for fr, amp in resonances[:5]:
        zone = 'LOW-MID MUD' if fr < 400 else 'NASAL/BOX' if fr < 1200 else 'PRESENCE BITE' if fr < 3000 else 'SIBILANCE'
        print(f"    {fr:6.0f} Hz  +{amp:.1f} dB  [{zone}]")
print("="*60)
