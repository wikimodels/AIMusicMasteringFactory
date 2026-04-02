import os
import cv2
import numpy as np
from pathlib import Path
from tqdm import tqdm

INPUT_DIR = Path("video_input")
OUTPUT_DIR = Path("video_output")

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def remove_watermark(input_path: Path, output_path: Path):
    cap = cv2.VideoCapture(str(input_path))
    if not cap.isOpened():
        print(f"[!] Cannot open video {input_path.name}")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # mp4v - стандартный кодек для MP4. ВАЖНО: OpenCV записывает ТОЛЬКО видео (без аудио трека)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

    # === НАСТРОЙКА ЗОНЫ ЛОГОТИПА (MASK) ===
    # Создаем черную маску размером с кадр
    mask = np.zeros((height, width), dtype=np.uint8)
    
    # Логотип "Veo" находится в правом нижнем углу.
    # Для вертикального видео (9:16) берём нижние 7% и правые 25%.
    x_start = int(width * 0.75)  # Начинаем с 75% ширины (правый край)
    x_end = width                # До конца ширины
    y_start = int(height * 0.93) # Начинаем с 93% высоты (самый низ)
    y_end = height               # До конца высоты

    # Рисуем белый прямоугольник на маске (там, где алгоритм должен стирать)
    cv2.rectangle(mask, (x_start, y_start), (x_end, y_end), 255, -1)
    # ======================================

    print(f"\n🎥 Обработка {input_path.name}...")
    print(f"Разрешение: {width}x{height} | Кадров: {total_frames} | Зона лого: X({x_start}-{x_end}), Y({y_start}-{y_end})")

    with tqdm(total=total_frames, unit="кадр", desc=input_path.name) as pbar:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Магия Inpainting: алгоритм Telea
            # inpaintRadius = 5 (сужаем/расширяем захват текстуры)
            restored_frame = cv2.inpaint(frame, mask, inpaintRadius=5, flags=cv2.INPAINT_TELEA)
            
            # Сохраняем восстановленный кадр (звук автоматически удаляется)
            out.write(restored_frame)
            pbar.update(1)

    cap.release()
    out.release()
    print(f"✅ Готово! Сохранено в: {output_path}\n")

def main():
    print("🚀 WATERMARK KILLER (OpenCV Inpainting)")
    print("Поместите видео в папку 'video_input'.\n")
    
    files = [f for f in INPUT_DIR.glob("*") if f.suffix.lower() in [".mp4", ".mov", ".avi"]]
    
    if not files:
        print(f"❌ Видео не найдено в папке: {INPUT_DIR.absolute()}")
        return
        
    for f in files:
        out_f = OUTPUT_DIR / f"{f.stem}_nowatermark.mp4"
        remove_watermark(f, out_f)

if __name__ == "__main__":
    main()
