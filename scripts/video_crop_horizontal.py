import sys
import os
import subprocess
import time
from pathlib import Path
import requests
from dotenv import load_dotenv

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

# Фикс кирилических символов в Windows-консоли
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ==============================================================================
# НАСТРОЙКИ — МЕНЯЙ ТОЛЬКО ЗДЕСЬ
# ==============================================================================

INPUT_DIR  = r"video\video_input_horizontal"   # Папка с исходниками (горизонтальные)
OUTPUT_DIR = r"video\video_output_horizontal"  # Папка для готовых видео (горизонтальные)

# Целевое разрешение HD для горизонтального видео (YouTube / Twitch / VK)
# Примеры: (1920, 1080) — Full HD горизонталь, (1280, 720) — HD горизонталь
TARGET_W = 1920
TARGET_H = 1080

# Сколько процентов срезать с каждой стороны (убираем watermark / черные полосы)
# 0.04 = 4%, 0.05 = 5% — подбирается под конкретный исходник
CROP_PERCENT = 0.04

# Сохранять ли оригинальный звук из видео?
# True  → звук копируется в финальный файл без пережатия ("-c:a copy")
# False → финальное видео будет НЕМЫМ ("-an"), готово для наложения трека отдельно
KEEP_AUDIO = False

# ==============================================================================

Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)


def get_resolution(filepath: Path) -> tuple[int, int]:
    """Получает оригинальное разрешение видео через ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0',
        str(filepath.absolute())
    ]
    output = subprocess.check_output(cmd).decode('utf-8').strip()
    w, h = map(int, output.split('x'))
    return w, h


def build_audio_args() -> list[str]:
    """Возвращает аргументы FFmpeg для обработки звука в зависимости от KEEP_AUDIO."""
    if KEEP_AUDIO:
        return ['-c:a', 'copy']  # Без пережатия — просто копируем поток
    else:
        return ['-an']           # Убираем звуковой поток полностью


def process_video(video_path: Path, index: int, total: int) -> None:
    filename = video_path.name
    output_path = Path(OUTPUT_DIR) / filename

    print(f"[{index}/{total}] 🎬 Рендер: {filename}")

    # Узнаём исходное разрешение
    src_w, src_h = get_resolution(video_path)

    # Считаем кроп-прямоугольник
    crop_w = int(src_w * (1 - CROP_PERCENT * 2))
    crop_h = int(src_h * (1 - CROP_PERCENT * 2))
    crop_x = int(src_w * CROP_PERCENT)
    crop_y = int(src_h * CROP_PERCENT)

    # Высота и ширина должны быть кратны 2 — требование видеокодеков
    crop_w -= crop_w % 2
    crop_h -= crop_h % 2
    crop_x -= crop_x % 2
    crop_y -= crop_y % 2

    # Финальный vf-фильтр:
    # crop=  → обрезает ватермарки/полосы
    # scale= → растягивает результат до целевого HD-разрешения (Lanczos — лучший алгоритм)
    vf_filter = (
        f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},"
        f"scale={TARGET_W}:{TARGET_H}:"
        f"flags=lanczos"
    )

    audio_mode = "🔊 со звуком" if KEEP_AUDIO else "🔇 немое"
    print(f"         Исходник: {src_w}×{src_h}  →  Кроп: {crop_w}×{crop_h}  →  Финал: {TARGET_W}×{TARGET_H}  [{audio_mode}]")

    cmd = [
        'ffmpeg',
        '-y',                      # Перезаписывать существующий файл
        '-i', str(video_path),
        '-vf', vf_filter,
        '-c:v', 'libx264',         # Кодек H.264 — стандарт совместимости
        '-preset', 'slow',         # slow даёт лучшее качество при том же crf
        '-crf', '18',              # 18 = визуально lossless (23 — стандарт, 18 — близко к макс. качеству)
        '-pix_fmt', 'yuv420p',     # Совместимость с iOS / YouTube / VK
        *build_audio_args(),
        str(output_path)
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )
    print(f"         ✅ Готово → {output_path}")


# ==============================================================================
# MAIN
# ==============================================================================

video_files = sorted(Path(INPUT_DIR).glob("*.mp4"))
total = len(video_files)

if total == 0:
    print(f"❌ Нет .mp4 файлов в папке: {INPUT_DIR}")
else:
    print(f"Найдено роликов для обработки: {total}")

    print(f"Целевое разрешение: {TARGET_W}×{TARGET_H}  |  Кроп: {int(CROP_PERCENT*100)}% с каждой стороны  |  Звук: {'сохраняется' if KEEP_AUDIO else 'удаляется'}")
    print("-" * 60)

    errors = 0
    for idx, vp in enumerate(video_files, 1):
        try:
            process_video(vp, idx, total)
        except Exception as e:
            print(f"         ❌ Ошибка: {e}")
            errors += 1

    print("-" * 60)
    if errors == 0:
        print("🏁 Пакетная обработка завершена без ошибок. Можно заливать!")
        tg(f"🎬 <b>Video Crop Horizontal Complete</b>\n"
           f"✅ Successfully processed {total} videos.")
    else:
        print(f"🏁 Завершено с {errors} ошибкам(и). Проверь логи выше.")
        tg(f"🎬 <b>Video Crop Horizontal Complete</b>\n"
           f"⚠️ Processed with {errors} errors.")
