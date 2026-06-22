import os
import sys
import subprocess
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

# Фикс кирилических символов в Windows-консоли
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

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

INPUT_DIR = Path(r"video\video_with_sound")
OUTPUT_DIR = Path(r"video\video_no_sound")

def main():
    print("🔇 AUDIO REMOVER UTILITY")
    
    # Так как папка video — это Junction, новые папки автоматически создадутся на диске G:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = [f for f in INPUT_DIR.glob("*") if f.suffix.lower() in [".mp4", ".mov", ".avi", ".mkv"]]
    total = len(videos)

    if total == 0:
        print(f"❌ Нет видео файлов в папке: {INPUT_DIR.absolute()}")
        print(f"📂 Пожалуйста, закиньте исходники в {INPUT_DIR.absolute()} и запустите снова.")
        return

    print(f"🎬 Найдено видео для удаления звука: {total}")
    print("⚡ Копирование видеопотока идёт без потерь качества (lossless) и очень быстро.\n")
    print("-" * 60)
    
    start_time = time.time()
    errors = 0

    for idx, vp in enumerate(videos, 1):
        out_p = OUTPUT_DIR / vp.name
        print(f"[{idx}/{total}] Очищаю: {vp.name}")
        
        # Команда ffmpeg
        # -c:v copy — копирует видео без пережатия (работает мгновенно)
        # -an — удаляет все аудио-потоки
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(vp.absolute()),
            "-c:v", "copy",
            "-an",
            str(out_p.absolute())
        ]
        
        try:
            result = subprocess.run(cmd)
            if result.returncode == 0:
                print(f"         ✅ Без звука -> {out_p.name}")
            else:
                print(f"         ❌ Ошибка FFmpeg")
                errors += 1
        except Exception as e:
            print(f"         ❌ Сбой: {e}")
            errors += 1

    total_time = time.time() - start_time
    print("-" * 60)
    
    if errors == 0:
        print(f"🏁 Готово! Все {total} видео мгновенно лишены голоса за {total_time:.1f} сек.")
        tg(f"🔇 <b>Audio Remover Complete</b>\n✅ Processed {total} files without audio.\n⏱ Time: {total_time:.1f}s")
    else:
        print(f"🏁 Завершено с ошибками: {errors}/{total}.")
        tg(f"🔇 <b>Audio Remover Complete</b>\n⚠️ Processed with {errors} errors.")

if __name__ == "__main__":
    main()
