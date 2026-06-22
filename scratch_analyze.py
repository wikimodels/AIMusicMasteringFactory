import numpy as np
import soundfile as sf
import sys
from pathlib import Path
from scipy.signal import find_peaks

def analyze_peaks(fpath):
    data, sr = sf.read(fpath)
    mono = data.mean(axis=1) if data.ndim > 1 else data
    n = 131072
    w = np.hanning(min(n, len(mono)))
    sig = mono[:len(w)] * w
    sp = np.abs(np.fft.rfft(sig, n=n))
    freqs = np.fft.rfftfreq(n, 1 / sr)
    db = 20 * np.log10(sp + 1e-9)
    k = np.ones(100) / 100
    db_s = np.convolve(db, k, mode='same')
    
    print(f"\n--- {Path(fpath).name} ---")
    
    # Check zones
    zones = [
        ("Boxy", 200, 300),
        ("Mud/Honk", 300, 600),
        ("Plastic/Nasal", 800, 2500),
        ("Harshness", 3000, 5000)
    ]
    
    for name, low, high in zones:
        mask = (freqs >= low) & (freqs <= high)
        if np.any(mask):
            max_db = np.max(db_s[mask])
            max_freq = freqs[mask][np.argmax(db_s[mask])]
            print(f"Zone {name} ({low}-{high} Hz): Peak at {max_freq:.1f} Hz ({max_db:.1f} dB)")

if __name__ == "__main__":
    analyze_peaks('sound/wav_input/Stained Concrete.wav')
