import os
import sys
import io
import numpy as np
import scipy.signal as signal
import soundfile as sf
from pathlib import Path

# Убеждаемся, что консоль не упадет из-за кодировок Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def make_bell(f0, Q, gain_db, fs):
    """Создает коэффициенты для Bell (Peak) EQ фильтра."""
    A = 10**(gain_db / 40)
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * Q)
    b = np.array([1 + alpha * A, -2 * np.cos(w0), 1 - alpha * A])
    a = np.array([1 + alpha / A, -2 * np.cos(w0), 1 - alpha / A])
    return b, a

def find_peak_in_zone(mono_data, fs, low_f, high_f):
    """Анализирует спектр трека и находит самую выпирающую частоту в заданном диапазоне."""
    n = 65536
    w = np.hanning(min(n, len(mono_data)))
    sig = mono_data[:len(w)] * w
    sp = np.abs(np.fft.rfft(sig, n=n))
    freqs = np.fft.rfftfreq(n, 1 / fs)
    db = 20 * np.log10(sp + 1e-9)
    k = np.ones(50) / 50
    db_s = np.convolve(db, k, mode='same')
    
    mask = (freqs >= low_f) & (freqs <= high_f)
    if not np.any(mask):
        return (low_f + high_f) / 2 
    
    peak_idx = np.argmax(db_s[mask])
    return freqs[mask][peak_idx]

def _rms_env(mono: np.ndarray, window: int) -> np.ndarray:
    kernel = np.ones(max(window, 1)) / max(window, 1)
    return np.sqrt(np.convolve(mono ** 2, kernel, mode="same") + 1e-12)

def de_harsh(y: np.ndarray, sr: int, thr_db=-24, redu_db=-4.0) -> np.ndarray:
    """Динамический эквалайзер: слушает 3.5 - 4.5 кГц и давит звон только в момент атаки."""
    sos_bp = signal.butter(4, [3500, 4500], "bp", fs=sr, output="sos")
    
    if y.ndim > 1:
        harsh = np.sqrt((signal.sosfiltfilt(sos_bp, y[0]) ** 2 + signal.sosfiltfilt(sos_bp, y[1]) ** 2) / 2)
    else:
        harsh = np.abs(signal.sosfiltfilt(sos_bp, y))

    thr = 10 ** (thr_db / 20)  # Порог срабатывания
    redu = 10 ** (redu_db / 20) # Максимальное подавление
    
    env = _rms_env(harsh, int(0.01 * sr))
    gain = np.where(env > thr, redu, 1.0)
    
    smooth_len = max(int(0.005 * sr), 1)
    gain = np.convolve(gain, np.ones(smooth_len) / smooth_len, mode="same")

    return np.stack([y[0] * gain, y[1] * gain]) if y.ndim > 1 else y * gain

def process_felt_piano(y, mono, fs):
    """
    Акустический профиль для Felt Piano (Скрываем детонацию и звон, сохраняем объем).
    """
    channels = y.shape[0]
    boxy_freq = find_peak_in_zone(mono, fs, 150, 300)
    mud_freq = find_peak_in_zone(mono, fs, 350, 600)
    
    # 1. Мягкая эквализация (Не убиваем "дерево")
    # Используем широкий (Q=0.7) и неглубокий срез (-1.5 дБ)
    b_boxy, a_boxy = make_bell(boxy_freq, 0.7, -1.5, fs) 
    b_mud, a_mud = make_bell(mud_freq, 1.0, -1.5, fs)
    
    # 2. Радикальный Low-Pass (Накрываем "ватным одеялом" чтобы скрыть цифровой зуд и жесткие атаки)
    # Срез начинается уже с 4000 Гц!
    sos_lp = signal.butter(2, 4000, "lp", fs=fs, output="sos")
    
    y_filtered = np.zeros_like(y)
    for ch in range(channels):
        step1 = signal.lfilter(b_boxy, a_boxy, y[ch])
        step2 = signal.lfilter(b_mud, a_mud, step1)
        y_filtered[ch] = signal.sosfiltfilt(sos_lp, step2)
        
    # Мы НАМЕРЕННО НЕ сужаем стереобазу и НЕ переводим бас в моно.
    # Широкая сцена маскирует фазовый лаг и детонацию, делая звук гипнотическим.
    
    return y_filtered

def process_guitar(y, mono, fs):
    """
    Акустический профиль для Гитары (Хирургическая чистота, фикс фазы, de-harsh).
    """
    channels = y.shape[0]
    boxy_freq = find_peak_in_zone(mono, fs, 200, 300)
    mud_freq = find_peak_in_zone(mono, fs, 350, 600)
    
    # 1. Жесткая хирургическая эквализация "коробки"
    b_boxy, a_boxy = make_bell(boxy_freq, 1.5, -4.0, fs)
    b_mud, a_mud = make_bell(mud_freq, 1.5, -3.0, fs)
    
    # Легкий винтажный срез (Tape Roll-off) - поднимаем до 10000 Гц для воздуха гитары
    sos_lp = signal.butter(2, 10000, "lp", fs=fs, output="sos")
    
    y_filtered = np.zeros_like(y)
    for ch in range(channels):
        step1 = signal.lfilter(b_boxy, a_boxy, y[ch])
        step2 = signal.lfilter(b_mud, a_mud, step1)
        y_filtered[ch] = signal.sosfiltfilt(sos_lp, step2)
        
    # 2. Динамический De-Harsh (очень деликатно, чтобы не смазать атаку)
    y_filtered = de_harsh(y_filtered, fs, thr_db=-22, redu_db=-3.0)
    
    # 3. Фикс стерео и моно-бас
    mid = (y_filtered[0] + y_filtered[1]) / 2.0
    side = (y_filtered[0] - y_filtered[1]) / 2.0
    
    sos_side_hp = signal.butter(4, 250.0, 'high', fs=fs, output='sos')
    side = signal.sosfiltfilt(sos_side_hp, side)
    side = side * 0.7 
    
    y_final = np.zeros_like(y_filtered)
    y_final[0] = mid + side
    y_final[1] = mid - side
    
    return y_final

def process_track(input_path, output_path):
    name_lower = input_path.stem.lower()
    print(f"\n--- Анализ и обработка: {input_path.name} ---")
    
    data, fs = sf.read(str(input_path))
    if data.ndim == 1:
        data = np.stack([data, data], axis=1)
        
    y = data.T # shape (2, N)
    mono = data.mean(axis=1)
    
    is_piano = "piano" in name_lower or "felt" in name_lower or "jubilee" in name_lower
    
    if is_piano:
        print("[Профиль] Выбран: FELT PIANO (Маскировка артефактов, мягкость, широкое стерео)")
        y_final = process_felt_piano(y, mono, fs)
    else:
        print("[Профиль] Выбран: GUITAR / GENERAL (Хирургическая очистка, de-harsh, фикс фазы)")
        y_final = process_guitar(y, mono, fs)
        
    # Нормализация (сохраняем оригинальную динамику без компрессии)
    peak = np.max(np.abs(y_final))
    if peak > 0:
        y_final = y_final * (0.99 / peak)
        
    sf.write(str(output_path), y_final.T, fs)
    print(f"✅ Успешно сохранен: {output_path.name}")

if __name__ == "__main__":
    ROOT = Path(__file__).parent.parent
    input_dir = ROOT / "sound" / "wav_input"
    output_dir = ROOT / "sound" / "wav_output"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    files = list(input_dir.glob("*.wav"))
    if not files:
        print("В папке wav_input нет файлов WAV!")
        sys.exit(0)
        
    for input_path in files:
        out_name = f"{input_path.stem}_SmartMaster.wav"
        output_path = output_dir / out_name
        process_track(input_path, output_path)
    
    print("\n[УМНЫЙ МАСТЕРИНГ ЗАВЕРШЕН]")
