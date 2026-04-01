# =============================================================================
# SUNO V5 DIRECT STEMS → PRO MASTERING (DE-HARSH & SUMMING)
# 💎 Быстрая обработка оригинальных стемов Suno (без Demucs)
# =============================================================================

print("🎛️  Установка зависимостей (Librosa, FFmpeg)...")

!pip install -U librosa soundfile tqdm scipy pyloudnorm -q
!apt-get -qq update && apt-get -qq install -y ffmpeg > /dev/null 2>&1

print("✅ Система готова!")

# =============================================================================
# SETUP
# =============================================================================

from google.colab import files
import os
import shutil
import subprocess
import numpy as np
import librosa
import soundfile as sf
import pyloudnorm as pyln
from scipy.signal import butter, sosfiltfilt
from pathlib import Path

BASE_DIR = '/content/suno_direct_master'
if os.path.exists(BASE_DIR): shutil.rmtree(BASE_DIR)
os.makedirs(f'{BASE_DIR}/stems', exist_ok=True)
os.makedirs(f'{BASE_DIR}/output', exist_ok=True)

print("\n📤 Загрузите ваши СТЕМЫ из Suno (WAV файлы: bass, drums, vocals, etc.)...")
uploaded = files.upload()

for filename in uploaded.keys():
    if filename.lower().endswith('.wav'):
        os.rename(f'/content/{filename}', f'{BASE_DIR}/stems/{filename}')

# =============================================================================
# DSP ФИЛЬТРЫ
# =============================================================================

def apply_lpf(y, sr, cutoff=13000):
    """Срезает цифровой песок на верхах (идеально для Drums/Synths)"""
    sos = butter(4, cutoff, 'lp', fs=sr, output='sos')
    if y.ndim > 1:
        return np.stack([sosfiltfilt(sos, y[0]), sosfiltfilt(sos, y[1])])
    return sosfiltfilt(sos, y)

def apply_hpf(y, sr, cutoff=30):
    """Срезает инфразвуковой мусор"""
    sos = butter(4, cutoff, 'hp', fs=sr, output='sos')
    if y.ndim > 1:
        return np.stack([sosfiltfilt(sos, y[0]), sosfiltfilt(sos, y[1])])
    return sosfiltfilt(sos, y)

def make_mono(y):
    """Строгий моно-сигнал для баса"""
    if y.ndim > 1:
        mono = (y[0] + y[1]) * 0.5
        return np.stack([mono, mono])
    return y

# =============================================================================
# MAIN PIPELINE
# =============================================================================

stem_dir = f'{BASE_DIR}/stems'
stem_files = [f for f in os.listdir(stem_dir) if f.lower().endswith('.wav')]

if not stem_files:
    print("❌ Нет файлов для обработки!")
else:
    print(f"\n🎧 Найдено стемов: {len(stem_files)}")
    print("   🎛️  Применение хирургической эквализации...")

    mix = None
    sr_main = 44100

    for f_name in stem_files:
        name_lower = f_name.lower()
        path = f'{stem_dir}/{f_name}'
        
        # Загружаем стэм
        y, sr = librosa.load(path, sr=sr_main, mono=False)
        
        # Если аудио моно, делаем его стерео для микса
        if y.ndim == 1:
            y = np.stack([y, y])
            
        print(f"      - Обработка: {f_name} ", end='')

        # Умная обработка по названию файла (Suno обычно так и называет файлы)
        if 'bass' in name_lower:
            y = apply_hpf(y, sr, 30)
            y = make_mono(y)
            print("→ [Low-End Focus & Mono]")
            
        elif 'drum' in name_lower:
            y = apply_lpf(y, sr, 12500) # Режем песок на тарелках
            print("→ [De-harsh Highs]")
            
        elif 'vocal' in name_lower:
            y = apply_hpf(y, sr, 80) # Легкий срез низа у голоса для чистоты
            print("→ [Vocal Clarity]")
            
        else:
            # Остальные инструменты (синты, гитары и т.д.)
            y = apply_lpf(y, sr, 14000) 
            y = y * 0.95 # Чуть уводим на задний план
            print("→ [Mix Placement & Smooth Highs]")

        # Суммируем в мастер-микс
        if mix is None:
            mix = y
        else:
            # Выравниваем длину, если стемы чуть отличаются
            min_len = min(mix.shape[1], y.shape[1])
            mix = mix[:, :min_len] + y[:, :min_len]

    # Защита от клиппинга перед финалом
    peak = np.max(np.abs(mix))
    if peak > 0: mix = mix / peak * 0.9

    tmp_path = f'{BASE_DIR}/output/PREMASTER.wav'
    out_path = f'{BASE_DIR}/output/SUNO_PRO_MASTER.wav'
    sf.write(tmp_path, mix.T, sr_main)

    # =========================================================================
    # ФИНАЛЬНЫЙ МАСТЕРИНГ (FFMPEG LOUDNORM)
    # =========================================================================
    print("   🔊 Финальный мастеринг (LUFS -14, True Peak -1dB)...")
    cmd_master = [
        'ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
        '-i', tmp_path,
        '-filter_complex', 'loudnorm=I=-14:TP=-1.0:LRA=11:linear=true',
        '-ar', '44100', '-ac', '2', '-acodec', 'pcm_s16le',
        out_path
    ]
    subprocess.run(cmd_master)
    os.remove(tmp_path)
    print("   ✅ Сведение завершено!")

    # =========================================================================
    # DOWNLOAD
    # =========================================================================
    print("\n📦 Скачивание готового мастера...")
    files.download(out_path)