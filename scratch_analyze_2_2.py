import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pathlib import Path
import scipy.signal as sg

INPUT = Path("Felt Piano Jazz/Felt Piano & Jazz v 2.2.wav")
data, fs = sf.read(str(INPUT))
if data.ndim > 1:
    mono = (data[:,0] + data[:,1])/2
else:
    mono = data

start_samp = int(35 * fs)
end_samp = int(45 * fs)
segment = mono[start_samp:end_samp]

plt.figure(figsize=(12, 6))
f, t, Sxx = sg.spectrogram(segment, fs, nperseg=4096, noverlap=2048)
plt.pcolormesh(t + 35, f, 10 * np.log10(Sxx + 1e-12), shading='gouraud', cmap='inferno')
plt.ylim(100, 3000)
plt.colorbar(label='Intensity [dB]')
plt.title("Spectrogram 35s - 45s (Felt Piano v 2.2)")
plt.xlabel("Time [s]")
plt.ylabel("Frequency [Hz]")
Path("analysis").mkdir(exist_ok=True)
plt.savefig("analysis/anomaly_35_45.png")
print("[CHART] analysis/anomaly_35_45.png")

sp = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
fr = np.fft.rfftfreq(len(segment), 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
db_s = np.convolve(db, np.ones(100)/100, mode='same')

plt.figure(figsize=(10, 4))
plt.semilogx(fr, db_s, color='red')
plt.xlim(100, 5000)
plt.grid(True)
plt.title("Spectrum of 35s - 45s (Felt Piano v 2.2)")
plt.savefig("analysis/anomaly_spectrum.png")
print("[CHART] analysis/anomaly_spectrum.png")
