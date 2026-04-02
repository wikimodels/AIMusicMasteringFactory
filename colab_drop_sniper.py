"""
🔥 AUDIO DROP SNIPER (Colab Edition) 🔥
Инструкция для Google Colab:
1. В Colab уже есть ffmpeg, поэтому ставим только либрозу:
   !pip install librosa soundfile numpy

2. Скопируйте этот код и запустите. Он сам всё очистит, 
   попросит загрузить треки и затем скачает готовый ZIP-архив.
"""

import os
import librosa
import numpy as np
import soundfile as sf
import time
import subprocess
import shutil

# Поддержка встроенного загрузчика в Google Colab
try:
    from google.colab import files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

# ==========================================
# ⚙️ НАСТРОЙКИ НАРЕЗКИ (ДРАМАТУРГИЯ)
# ==========================================
INPUT_DIR = "/content/input_tracks"   # Папка с исходниками
OUTPUT_DIR = "/content/output_drops"  # Папка для готовых нарезок
ZIP_PATH = "/content/drops_archive.zip" # Путь к готовому архиву для скачивания
SLICE_DURATION = 25                   # Общая длина шортса (всего 25 секунд)
PRE_DROP_TENSION = 6                  # "ИНТРИГА" ДО взрыва (6 сек ямы + 19 сек мяса)

def find_best_drop(y, sr):
    rms = librosa.feature.rms(y=y)[0]
    frames_per_sec = sr / 512
    window_length = int(5 * frames_per_sec) 
    smoothed_rms = np.convolve(rms, np.ones(window_length)/window_length, mode='valid')
    drop_frame = np.argmax(smoothed_rms)
    drop_time_sec = librosa.frames_to_time(drop_frame, sr=sr)
    start_time_sec = max(0, drop_time_sec - PRE_DROP_TENSION)
    end_time_sec = start_time_sec + SLICE_DURATION
    start_sample = int(start_time_sec * sr)
    end_sample = int(end_time_sec * sr)
    if end_sample > len(y):
        end_sample = len(y)
        start_sample = max(0, end_sample - int(SLICE_DURATION * sr))
    return start_sample, end_sample, drop_time_sec

def process_folder():
    print("🧹 Шаг 0: Очистка системы от прошлых прогонов...")
    # Полная зачистка перед новым запуском
    if os.path.exists(INPUT_DIR):
        shutil.rmtree(INPUT_DIR)
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    if os.path.exists(ZIP_PATH):
        os.remove(ZIP_PATH)
        
    os.makedirs(INPUT_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Если мы в Colab, вызываем красивое окно загрузки файлов с ПК
    if IN_COLAB:
        print("📥 Шаг 1: Выберите треки на вашем компьютере для загрузки в Colab...")
        uploaded = files.upload()
        for filename in uploaded.keys():
            # Перемещаем загруженные файлы в рабочую папку
            os.rename(filename, os.path.join(INPUT_DIR, filename))
        print("\n✅ Загрузка завершена! Начинаем обработку...\n")

    files_list = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.mp3', '.wav', '.flac', '.m4a'))]
    
    if not files_list:
        print(f"📭 Папка {INPUT_DIR} пуста! Загрузите файлы.")
        return

    print(f"🚀 Шаг 2: Начинаю промышленную разделку {len(files_list)} треков...\n")
    start_all = time.time()

    for idx, filename in enumerate(files_list, 1):
        print(f"[{idx}/{len(files_list)}] 🎧 Режу трек: {filename}")
        in_path = os.path.join(INPUT_DIR, filename)
        
        # На выходе мы ЖЕСТКО требуем только MP3
        name_without_ext = os.path.splitext(filename)[0]
        out_filename = f"{name_without_ext}_DROP.mp3"
        out_path = os.path.join(OUTPUT_DIR, out_filename)
        temp_wav = os.path.join(OUTPUT_DIR, f"temp_{idx}.wav")
        
        t0 = time.time()
        
        try:
            # Читаем абсолютно любой формат аудио (WAV, MP3 и тд)
            y, sr = librosa.load(in_path, sr=22050)
            
            start_idx, end_idx, math_drop = find_best_drop(y, sr)
            y_sliced = y[start_idx:end_idx]
            
            # Сохраняем промежуточный WAV (либроза работает с ним нативно)
            sf.write(temp_wav, y_sliced, sr)
            
            # Врубаем 320 kbps (хардкорное качество CBR 320k)
            subprocess.run(["ffmpeg", "-y", "-i", temp_wav, "-b:a", "320k", out_path], capture_output=True)
            
            # Удаляем промежуточный мусор
            if os.path.exists(temp_wav):
                os.remove(temp_wav)
            
            t1 = time.time()
            print(f"   ✅ Готово (320kbps MP3) за {t1-t0:.1f} сек! (Взрыв на {math_drop:.1f}с)")
            
        except Exception as e:
            print(f"   ❌ Ошибка при обработке {filename}: {e}")

    total_time = time.time() - start_all
    print(f"\n🎉 ВСЕ ТРЕКИ СНАЙПЕРСКИ НАРЕЗАНЫ В 320kbps MP3 ЗА {total_time:.1f} СЕКУНД!")
    
    if IN_COLAB:
        print("📦 Шаг 3: Упаковка готовых файлов в единый ZIP-архив...")
        shutil.make_archive(ZIP_PATH.replace('.zip', ''), 'zip', OUTPUT_DIR)
        print("⬇️ Шаг 4: Начинаю автоматическое скачивание архива на ваш компьютер...")
        files.download(ZIP_PATH)
    else:
        print(f"📁 Забирай в папке: {OUTPUT_DIR}/")

if __name__ == "__main__":
    process_folder()
