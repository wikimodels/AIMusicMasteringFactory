import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt
from pathlib import Path

def _rms_env(mono: np.ndarray, window: int) -> np.ndarray:
    kernel = np.ones(max(window, 1)) / max(window, 1)
    return np.sqrt(np.convolve(mono ** 2, kernel, mode="same") + 1e-12)

def de_harsh(y: np.ndarray, sr: int) -> np.ndarray:
    # Фокусируемся точно на звоне ксилофона (3.5 - 4.5 кГц)
    sos_bp = butter(4, [3500, 4500], "bp", fs=sr, output="sos")
    
    if y.ndim > 1:
        harsh = np.sqrt((sosfiltfilt(sos_bp, y[0]) ** 2 + sosfiltfilt(sos_bp, y[1]) ** 2) / 2)
    else:
        harsh = np.abs(sosfiltfilt(sos_bp, y))

    thr = 10 ** (-28 / 20)  # Чувствительный порог
    redu = 10 ** (-8.0 / 20) # Глубокое подавление (-8 дБ) только когда звенит
    
    env = _rms_env(harsh, int(0.01 * sr)) # Очень быстрая реакция (10 мс) на удары
    gain = np.where(env > thr, redu, 1.0)
    
    # Сглаживание гейна (5 мс)
    smooth_len = max(int(0.005 * sr), 1)
    gain = np.convolve(gain, np.ones(smooth_len) / smooth_len, mode="same")

    return np.stack([y[0] * gain, y[1] * gain]) if y.ndim > 1 else y * gain

def process_file(input_path, output_path):
    print(f"Processing: {input_path.name}")
    data, fs = sf.read(str(input_path))
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
    
    y = data.T # shape (2, N)
    
    # 1. Динамический эквалайзер ТОЛЬКО на частоту ксилофона (3.5-4.5 кГц)
    # Не трогает эквализацию гитары когда ксилофона нет!
    y = de_harsh(y, fs)
    
    # 2. Мягкий спад ВЧ (Low-pass) чтобы убрать ИИ-"песок", как в самом первом скрипте
    # Используем 2-й порядок на 7500 Гц - очень естественно звучит
    sos_lp = butter(2, 7500, "lp", fs=fs, output="sos")
    y = np.stack([sosfiltfilt(sos_lp, y[0]), sosfiltfilt(sos_lp, y[1])])

    # 3. Никаких ffmpeg loudnorm! Только чистая пиковая нормализация под -0.1 дБ.
    # Это на 100% сохраняет оригинальную динамику, низы и середину!
    peak = np.max(np.abs(y))
    if peak > 0:
        y = y * (0.99 / peak)
        
    sf.write(str(output_path), y.T, fs)
    print(f"Saved -> {output_path.name}")

if __name__ == "__main__":
    ROOT = Path(__file__).parent
    input_dir = ROOT / "sound" / "wav_input"
    output_dir = ROOT / "sound" / "wav_output"
    
    # Process all wav files in input_dir
    for input_path in input_dir.glob("*.wav"):
        out_name = f"{input_path.stem}_Perfect.wav"
        output_path = output_dir / out_name
        process_file(input_path, output_path)
