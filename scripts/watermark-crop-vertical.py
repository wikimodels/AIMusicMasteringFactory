import os
import sys
import io
import subprocess
from pathlib import Path

# Fix Windows console UTF-8 encoding issues with emojis
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

INPUT_DIR = Path("video_input")
OUTPUT_DIR = Path("video_output")

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Процент обрезки (настроено под логотип Veo в правом нижнем углу)
# Мы обрезаем 4% снизу, и по 2% с боков, чтобы сохранить пропорцию 9:16.
CROP_PERCENT = 0.04

def crop_watermark(input_path: Path, output_path: Path):
    print(f"\n🎬 Обработка видео: {input_path.name}")
    
    # ffprobe для получения исходных размеров видео
    cmd_probe = [
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0",
        str(input_path)
    ]
    
    try:
        result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split('x'))
    except Exception as e:
        print(f"❌ Ошибка при чтении файла {input_path.name}: {e}")
        return

    # Высчитываем новые размеры (идеальное сохранение пропорций 9:16)
    new_height = int(height * (1.0 - CROP_PERCENT))
    new_width = int(width * (1.0 - CROP_PERCENT))
    
    # Центрируем по горизонтали и прижимаем к самому верху (отрезаем весь низ)
    x_offset = int((width - new_width) / 2)
    y_offset = 0  # 0 означает старт с самого верха, весь обрезок уходит в нижнюю часть

    # Убеждаемся, что новые размеры четные (требование H.264 кодека)
    new_width = new_width if new_width % 2 == 0 else new_width - 1
    new_height = new_height if new_height % 2 == 0 else new_height - 1

    crop_filter = f"crop={new_width}:{new_height}:{x_offset}:{y_offset}"

    print(f"   Исходный размер: {width}x{height}")
    print(f"   Новый размер: {new_width}x{new_height} (Smart Crop 9:16)")
    
    # Команда FFMPEG
    # -an: полностью удаляет звуковую дорожку
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(input_path),
        "-vf", crop_filter,
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-an",
        str(output_path)
    ]

    success = subprocess.run(cmd).returncode == 0
    if success:
        print(f"✅ Готово! Сохранено без звука и логотипа: {output_path.name}")
    else:
        print(f"❌ Ошибка вырезки у файла {input_path.name}")

def main():
    print("✂️ SMART CROP 9:16 (Veo Logo Remover)")
    print("Ищем видео в папке 'video_input'...\n")
    
    files = [f for f in INPUT_DIR.glob("*") if f.suffix.lower() in [".mp4", ".mov", ".avi"]]
    
    if not files:
        print(f"Ни одного видео не найдено в {INPUT_DIR.absolute()}")
        return
        
    for f in files:
        out_f = OUTPUT_DIR / f"{f.stem}_cropped.mp4"
        crop_watermark(f, out_f)

if __name__ == "__main__":
    main()
