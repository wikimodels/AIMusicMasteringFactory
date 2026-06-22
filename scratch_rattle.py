import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import soundfile as sf
import matplotlib.pyplot as plt
from pathlib import Path
import scipy.signal as sg

INPUT = Path("Felt Piano & Jazz v 1.2.wav")
data, fs = sf.read(str(INPUT))
mono = (data[:,0] + data[:,1])/2

# Извлекаем кусок с 1:40 по 2:00
start_samp = int(100 * fs)  # 1:40 = 100s
end_samp = int(120 * fs)    # 2:00 = 120s
segment = mono[start_samp:end_samp]

plt.figure(figsize=(12, 6))
f, t, Sxx = sg.spectrogram(segment, fs, nperseg=4096, noverlap=2048)
plt.pcolormesh(t + 100, f, 10 * np.log10(Sxx + 1e-12), shading='gouraud', cmap='inferno')
plt.ylim(100, 1000)
plt.colorbar(label='Intensity [dB]')
plt.title("Spectrogram 1:40 - 2:00 (100Hz - 1000Hz)")
plt.xlabel("Time [s]")
plt.ylabel("Frequency [Hz]")
plt.savefig("analysis/rattle_1_45.png")
print("[CHART] analysis/rattle_1_45.png")

# Посмотрим средний спектр именно в этом куске
sp = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
fr = np.fft.rfftfreq(len(segment), 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
db_s = np.convolve(db, np.ones(100)/100, mode='same')

plt.figure(figsize=(10, 4))
plt.semilogx(fr, db_s, color='red')
plt.xlim(100, 2000)
plt.grid(True)
plt.title("Spectrum of 1:40 - 2:00")
plt.savefig("analysis/rattle_spectrum.png")
print("[CHART] analysis/rattle_spectrum.png")
