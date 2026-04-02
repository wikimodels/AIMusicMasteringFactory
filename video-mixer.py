import os
import sys
import io
import json
import subprocess
from pathlib import Path

# Фикс Windows консоли для корректной печати эмодзи
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

CONFIG_FILE = Path("mix_config.json")
VIDEO_DIR = Path("video_output")
AUDIO_DIR = Path("output_mp3_drops")
OUT_DIR = Path("final_mixes")

OUT_DIR.mkdir(exist_ok=True)

def process_mix(project_name: str, mix_data: dict):
    print(f"\n🎬 Старт проекта: {project_name}")
    
    videos = mix_data.get("videos", [])
    audio_name = mix_data.get("audio", "")
    
    if not videos or not audio_name:
        print("   ❌ Ошибка: В конфиге не указаны видео или аудио.")
        return
        
    audio_path = AUDIO_DIR / audio_name
    if not audio_path.exists():
        print(f"   ❌ Аудио файл не найден: {audio_path}")
        return

    # Проверяем существование всех видео
    valid_videos = []
    for v in videos:
        vp = VIDEO_DIR / v
        if vp.exists():
            valid_videos.append(vp)
        else:
            print(f"   ⚠️ Видео не найдено и будет пропущено: {vp}")
            
    if not valid_videos:
        print("   ❌ Ни одного видео не найдено для сшивки.")
        return

    # Создаем файл-инструкцию для FFmpeg (concat demuxer)
    # Используем абсолютные пути, чтобы у ffmpeg не было проблем с путями в Windows
    concat_txt = OUT_DIR / f"{project_name}_concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for vp in valid_videos:
            # Формат: file 'C:\path\to\file.mp4'
            f.write(f"file '{vp.absolute().resolve()}'\n")

    out_file = OUT_DIR / f"{project_name}_READY.mp4"
    
    # FFmpeg Магия:
    # 1. -stream_loop -1 : зациклить блок видео (из concat.txt) бесконечно
    # 2. -f concat -safe 0 : формат склейки (демуксер без перекодирования исходников)
    # 3. -i audio_path : наш MP3 дроп (основа по времени)
    # 4. -shortest : хирургически обрезать видео ряд ровно в момент окончания MP3
    #
    # Почему мы используем -c:v libx264, а не -c copy?
    # Зацикливание H264 без перекодировки ломает Timecodes (PTS/DTS), из-за чего
    # видео зависает на стыке цикла в TikTok, Reels и Spotify Canvas.
    # Поэтому мы перерендериваем картинку (-crf 18 - высочайшее качество).
    
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", 
        "-f", "concat", "-safe", "0", "-i", str(concat_txt),
        "-i", str(audio_path),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "copy",
        "-shortest",
        str(out_file)
    ]
    
    print(f"   ⏳ Сборка и рендер... (Видео-кусочков: {len(valid_videos)}, Звук: {audio_name})")
    success = subprocess.run(cmd).returncode == 0
    
    # Очистка мусорных файлов
    if concat_txt.exists():
        concat_txt.unlink()
        
    if success:
        print(f"   ✅ ГОТОВО! Сохранено: final_mixes/{out_file.name}")
    else:
        print("   ❌ Ошибка FFmpeg при рендере конкатенации.")

def main():
    print("🛸 INFINITE VIDEO-AUDIO MIXER (TikTok/Reels/Shorts)")
    if not CONFIG_FILE.exists():
        print(f"❌ Файл {CONFIG_FILE.name} не найден!")
        return

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        print(f"❌ Ошибка чтения конфига: {e}")
        return
        
    for project_name, data in config.items():
        process_mix(project_name, data)

if __name__ == "__main__":
    main()
