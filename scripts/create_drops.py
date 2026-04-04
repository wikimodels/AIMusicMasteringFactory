"""
Создание коротких превью-нарезок (Drops) из готовых отмастеренных WAV файлов.
Вырезает самый энергичный (RMS) кусок, делает fade in/out и жмёт в 320kbps MP3.
"""

import os
import subprocess
import time
from pathlib import Path
import json

import numpy as np
import librosa
import soundfile as sf
import requests
from dotenv import load_dotenv

# =============================================================================
# ⚙️ TELEGRAM & НАСТРОЙКИ НАРЕЗКИ 
# =============================================================================
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")

def tg(text: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=8,
        )
    except Exception:
        pass

# =============================================================================
# ⚙️ НАСТРОЙКИ НАРЕЗКИ (ДРАМАТУРГИЯ)
# ВАЖНО: БОТ ОБЯЗАН СПРОСИТЬ У ПОЛЬЗОВАТЕЛЯ, НЕ ХОЧЕТ ЛИ ОН ИЗМЕНИТЬ ЭТИ ПУНКТЫ.
# =============================================================================

SLICE_DURATION   = 32  # Общая длина нарезки (в секундах). Изначально было 35, ставим 30.
PRE_DROP_TENSION = 6   # Сколько секунд тишины/разгона захватить ДО самого пика взрыва.

# =============================================================================
# ПУТИ
# =============================================================================
INPUT_DIR  = Path("sound/wav_output")
OUTPUT_DIR = Path("sound/mp3_drops_output")
META_FILE  = Path("metadata.json") # запасной fallback, но лучше вытаскивать теги позже, если надо. Для дропов это не критично.

def find_best_drop_logic(y: np.ndarray, sr: int) -> tuple:
    """Математически вычисляет самый громкий кусок и откатывает назад на PRE_DROP_TENSION."""
    rms = librosa.feature.rms(y=y)[0]
    frames_per_sec = sr / 512
    window_length  = int(5 * frames_per_sec) 
    smoothed_rms   = np.convolve(rms, np.ones(window_length)/window_length, mode='valid')
    drop_frame     = np.argmax(smoothed_rms)
    drop_time_sec  = librosa.frames_to_time(drop_frame, sr=sr)
    
    start_time_sec = max(0, drop_time_sec - PRE_DROP_TENSION)
    end_time_sec   = start_time_sec + SLICE_DURATION
    
    # Если нарезка упирается в конец трека
    total_sec = len(y) / sr
    if end_time_sec > total_sec:
        end_time_sec = total_sec
        start_time_sec = max(0, end_time_sec - SLICE_DURATION)
        
    return start_time_sec, SLICE_DURATION


def create_drop_snippet(master_wav: Path, out_mp3: Path, start: float, dur: float) -> bool:
    """Вызов FFmpeg для создания MP3 вырезки с плавным фейдом 2 сек."""
    fade_out_start = dur - 2.0
    filter_str = f"afade=t=in:ss=0:d=2,afade=t=out:st={fade_out_start:.3f}:d=2"
    
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        # Сначала указываем позицию для быстрого и точного обрезания ДО фильтров
        "-ss", str(start), 
        "-t", str(dur),
        "-i", str(master_wav),
        "-map_metadata", "-1",
        "-af", filter_str, # Используем простой аудиофильтр (-af) вместо complex
        "-b:a", "320k",
        str(out_mp3)
    ]
    return subprocess.run(cmd).returncode == 0

def main():
    print(f"\n🚀 НАЧИНАЕТСЯ СОЗДАНИЕ ДРОПОВ (НАРЕЗОК)")
    print(f"⚙️  Настройки: Длина = {SLICE_DURATION} сек | До дропа = {PRE_DROP_TENSION} сек\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    files = sorted([f for f in INPUT_DIR.glob("*.wav")])
    if not files:
        print(f"📭 Папка {INPUT_DIR} пуста. Сначала выполни мастеринг!")
        return

    tg(f"✂️ <b>Drop Sniper started</b>\n{len(files)} track(s) in queue\n"
       f"Config: {SLICE_DURATION}s length, {PRE_DROP_TENSION}s tension.")

    start_all = time.time()
    ok_count = 0
    
    for idx, wav_path in enumerate(files, 1):
        stem = wav_path.stem
        out_mp3 = OUTPUT_DIR / f"{stem}_DROP.mp3"
        
        # Проверка на то, что дроп уже нарезан
        if out_mp3.exists():
            print(f"[{idx}/{len(files)}] ⏭️ Пропускаю трек: {wav_path.name} (уже нарезан)")
            ok_count += 1
            continue
            
        print(f"[{idx}/{len(files)}] 🎧 Режу трек: {wav_path.name}")
        t0 = time.time()
        
        try:
            # Читаем исходный WAV (22050 хватит для быстрого анализа)
            y, sr = librosa.load(str(wav_path), sr=22050)
            
            # Считаем тайминг дропа
            start_sec, dur_sec = find_best_drop_logic(y, sr)
            
            # Делаем снайперский выстрел FFmpeg-ом
            if create_drop_snippet(wav_path, out_mp3, start_sec, dur_sec):
                t1 = time.time()
                print(f"   ✅ Готово (320k MP3)! Дроп на {start_sec + PRE_DROP_TENSION:.1f}с. Время: {t1-t0:.1f} сек.")
                ok_count += 1
            else:
                print(f"   ❌ FFmpeg завершился с ошибкой для {wav_path.name}")
                
        except Exception as e:
            print(f"   ❌ Ошибка при обработке {wav_path.name}: {e}")

    total_time = time.time() - start_all
    print(f"\n🎉 ГОТОВО! {ok_count} из {len(files)} треков успешно нарезаны за {total_time:.1f} секунд.")
    print(f"📂 Забирай в: {OUTPUT_DIR}")

    tg(f"✂️ <b>Drop Sniper complete</b>\n"
       f"{ok_count}/{len(files)} tracks successfully exported to MP3.\n"
       f"⏱ Total time: {total_time:.1f}s")

if __name__ == "__main__":
    main()
