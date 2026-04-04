"""
Скрипт для инъекции SEO-метаданных (RIFF INFO) в финальные WAV файлы.
Использует pytaglib для корректной записи тегов в WAV (ffmpeg и mutagen делают это ненадёжно).

Требования:
pip install pytaglib
"""

import os
import json
import taglib

# Настройки
ALBUM_NAME = "Level_0_Infinite_Carpet"
META_JSON = os.path.join("metadata", ALBUM_NAME, "metakeys.json")
WAV_OUTPUT_DIR = "sound/wav_output/"

def main():
    if not os.path.exists(META_JSON):
        print(f"❌ Ошибка: Не найден файл {META_JSON}")
        return
        
    with open(META_JSON, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    album     = meta.get("album", "")
    artist    = meta.get("artist", "")
    year      = meta.get("year", "")
    copyright = meta.get("copyright", "")
    genre     = meta.get("genre", "")
    comment_tpl = meta.get("comment_template", "{TRACK_VIBE}")
    
    vibes = meta.get("track_vibes", {})
    
    if not os.path.exists(WAV_OUTPUT_DIR):
        print(f"❌ Папка {WAV_OUTPUT_DIR} не найдена. Сначала выполните suno-mastering.py")
        return

    processed = 0
    
    # Итерируемся по файлам в выходной директории
    for idx, fname in enumerate(sorted(os.listdir(WAV_OUTPUT_DIR)), 1):
        if not fname.endswith(".wav"):
            continue
            
        base_name = os.path.splitext(fname)[0]
        file_path = os.path.join(WAV_OUTPUT_DIR, fname)
        
        try:
            f = taglib.File(file_path)
            
            # Заполняем RIFF INFO чанки
            f.tags["TITLE"] = [base_name.replace("_", " ")]
            if artist:    f.tags["ARTIST"] = [artist]
            if album:     f.tags["ALBUM"] = [album]
            if year:      f.tags["DATE"] = [year]
            if copyright: f.tags["COPYRIGHT"] = [copyright]
            if genre:     f.tags["GENRE"] = [genre]
            
            f.tags["TRACKNUMBER"] = [str(idx)]
            
            # Формируем Comment из vibe конкретного трека
            vibe = vibes.get(base_name, "Liminal phonk track.")
            comment = comment_tpl.replace("{TRACK_VIBE}", vibe)
            f.tags["COMMENT"] = [comment]
            
            # Сохраняем теги
            f.save()
            f.close()
            
            print(f"✅ Протегирован: {fname}")
            processed += 1
            
        except Exception as e:
            print(f"⚠️ Ошибка при тегировании {fname}: {e}")
            
    print(f"\n🎉 Завершено! Успешно протегировано: {processed} WAV файлов.")

if __name__ == "__main__":
    main()
