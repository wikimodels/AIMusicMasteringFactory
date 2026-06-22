import numpy as np
from pydub import AudioSegment
from scipy.signal import butter, sosfilt, iirpeak
import warnings
warnings.filterwarnings('ignore')

def apply_sos_filter(data, sos):
    """Применяет SOS фильтр — стабильнее чем lfilter"""
    return sosfilt(sos, data.astype(np.float64))

def high_shelf_cut(data, fs, freq=10000, gain_db=-9, order=2):
    """High-shelf EQ: плавно режет всё выше freq на gain_db"""
    nyq = fs / 2
    w0 = freq / nyq
    # High shelf через bilinear transform
    from scipy.signal import butter
    sos = butter(order, w0, btype='low', output='sos')
    # Миксуем оригинал и фильтрованный для shelf эффекта
    gain_linear = 10 ** (gain_db / 20)
    filtered = sosfilt(sos, data.astype(np.float64))
    # Shelf = original + (filtered - original) * (1 - gain)
    return data + (filtered - data) * (1 - gain_linear)

def notch_filter(data, fs, freq=12000, Q=2.0):
    """Notch: режет только узкую полосу вокруг freq (hi-hat пик)"""
    w0 = freq / (fs / 2)
    b, a = iirpeak(w0, Q)
    from scipy.signal import tf2sos
    sos = tf2sos(b, a)
    # Инвертируем notch → peak → subtract
    filtered = sosfilt(sos, data.astype(np.float64))
    return data - filtered * 0.6  # 0.6 = глубина среза (0.0–1.0)

def peak_normalize(samples, headroom_db=-0.3):
    """Нормализация до заданного headroom"""
    peak = np.max(np.abs(samples))
    if peak == 0:
        return samples
    target = 10 ** (headroom_db / 20) * 32767
    return samples * (target / peak)

def clean_suno_hihats(input_file, output_file, 
                       notch_freq=12000,    # центр пика hi-hat (Hz)
                       notch_q=1.5,         # Q: уже = точнее
                       shelf_freq=11000,    # где начинается shelf
                       shelf_db=-6,         # насколько режем верха
                       normalize=True):
    
    audio = AudioSegment.from_file(input_file)
    fs = audio.frame_rate
    samples = np.array(audio.get_array_of_samples(), dtype=np.float64)
    
    if audio.channels == 2:
        left  = samples[0::2].copy()
        right = samples[1::2].copy()
        
        # 1. Notch на проблемный пик hi-hat
        left  = notch_filter(left,  fs, notch_freq, notch_q)
        right = notch_filter(right, fs, notch_freq, notch_q)
        
        # 2. Мягкий high-shelf для общего потемнения верхов
        left  = high_shelf_cut(left,  fs, shelf_freq, shelf_db)
        right = high_shelf_cut(right, fs, shelf_freq, shelf_db)
        
        # 3. Нормализация
        if normalize:
            left  = peak_normalize(left)
            right = peak_normalize(right)
        
        out = np.empty_like(samples)
        out[0::2] = left
        out[1::2] = right
    else:
        out = notch_filter(samples, fs, notch_freq, notch_q)
        out = high_shelf_cut(out, fs, shelf_freq, shelf_db)
        if normalize:
            out = peak_normalize(out)
    
    new_audio = audio._spawn(out.astype(np.int16).tobytes())
    new_audio.export(output_file, format="wav")
    print(f"✅ Готово: notch@{notch_freq}Hz, shelf@{shelf_freq}Hz ({shelf_db}dB) → {output_file}")

# === ПРИМЕНЕНИЕ ===

# Базовый вариант (начни с этого):
# clean_suno_hihats("track.mp3", "clean.wav")

# Если уц-уц очень агрессивное (характерно для Suno V4):
# clean_suno_hihats("track.mp3", "clean.wav", notch_freq=13000, notch_q=1.0, shelf_db=-9)

# Если хочешь только shelf без notch (мягче):
# clean_suno_hihats("track.mp3", "clean.wav", notch_q=0.0, shelf_db=-8)

# Для джаза (твой трек) — максимально тёмный звук:
# clean_suno_hihats("track.mp3", "clean.wav", 
#                    notch_freq=12000, notch_q=2.0,
#                    shelf_freq=10000, shelf_db=-8)