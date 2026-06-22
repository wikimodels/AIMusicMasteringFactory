import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pathlib import Path
import scipy.signal as sg

INPUT = Path("Guitar Jazz/Guitar & Jazz v 1.1.wav")
data, fs = sf.read(str(INPUT))

start_samp = int(90 * fs) # 1:30
end_samp = int(100 * fs)  # 1:40
segment = data[start_samp:end_samp]
mono = (segment[:,0] + segment[:,1])/2

win_size = int(0.5 * fs)
hop_size = int(0.1 * fs)
corrs = []
rmss = []
times = []
for i in range(0, len(segment) - win_size, hop_size):
    l = segment[i:i+win_size, 0]
    r = segment[i:i+win_size, 1]
    c = np.mean(l*r) / (np.sqrt(np.mean(l**2)*np.mean(r**2)) + 1e-12)
    corrs.append(c)
    rmss.append(20*np.log10(np.sqrt(np.mean(((l+r)/2)**2)) + 1e-12))
    times.append(90 + i/fs)

plt.figure(figsize=(10, 6))
plt.subplot(2,1,1)
plt.plot(times, corrs, color='blue')
plt.title("Stereo Correlation (1:30 - 1:40)")
plt.ylim(-1, 1)
plt.grid()

plt.subplot(2,1,2)
plt.plot(times, rmss, color='green')
plt.title("RMS Volume (Mono) [dB]")
plt.grid()
plt.tight_layout()
Path("analysis").mkdir(exist_ok=True)
plt.savefig("analysis/guitar_wobble_stats.png")
print("[CHART] analysis/guitar_wobble_stats.png")

plt.figure(figsize=(12, 6))
f, t, Sxx = sg.spectrogram(mono, fs, nperseg=4096, noverlap=3000)
plt.pcolormesh(t + 90, f, 10 * np.log10(Sxx + 1e-12), shading='gouraud', cmap='inferno')
plt.ylim(100, 1500)
plt.title("Spectrogram (Pitch Wobble Check) 1:30 - 1:40")
plt.colorbar()
plt.savefig("analysis/guitar_wobble_spec.png")
print("[CHART] analysis/guitar_wobble_spec.png")
