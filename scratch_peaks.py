import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import numpy as np
import soundfile as sf
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d

data, fs = sf.read("Felt Piano Jazz/Felt Piano & Jazz v 2.2.wav")
mono = (data[:,0] + data[:,1])/2
segment = mono[int(35*fs):int(45*fs)]
sp = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))
fr = np.fft.rfftfreq(len(segment), 1.0/fs)
db = 20 * np.log10(sp + 1e-12)
db_s = np.convolve(db, np.ones(100)/100, mode='same')
baseline = uniform_filter1d(db_s, size=400)
diff = db_s - baseline

mask = (fr > 300) & (fr < 5000)
peaks, _ = find_peaks(diff[mask], height=5, distance=100)
peaks += np.where(mask)[0][0]
for p in sorted(peaks, key=lambda x: -diff[x])[:5]:
    print(f"Peak at {fr[p]:.1f} Hz: +{diff[p]:.1f} dB")
