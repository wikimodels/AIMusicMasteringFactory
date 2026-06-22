import os
import sys
import io
import numpy as np
import scipy.signal as signal
import soundfile as sf
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def make_bell(f0, Q, gain_db, fs):
    """Вспомогательная функция для создания Bell-фильтра"""
    A = 10**(gain_db / 40)
    w0 = 2 * np.pi * f0 / fs
    alpha = np.sin(w0) / (2 * Q)
    b = np.array([1 + alpha * A, -2 * np.cos(w0), 1 - alpha * A])
    a = np.array([1 + alpha / A, -2 * np.cos(w0), 1 - alpha / A])
    return b, a

def dark_jazz_mastering(input_file, output_file):
    """
    Финальный мастеринг для всего проекта "Dark Jazz" (Пианино + Гитара).
    Вырезает пластиковый реверб, дребезг и цифровой песок.
    Сохраняет 100% оригинальную динамику (без компрессоров).
    """
    data, fs = sf.read(input_file)
    if len(data.shape) > 1:
        channels = data.shape[1]
    else:
        channels = 1
        data = data.reshape(-1, 1)
        
    output_data = np.zeros_like(data)
    
    # --- НАСТРОЙКА ФИЛЬТРОВ ---
    # 1. Срез инфра-низа (High-Pass 40 Гц, 2 порядок)
    b_hp, a_hp = signal.butter(2, 40.0, btype='high', fs=fs)
    
    # 2. Убираем "коробку" корпуса (220 Гц, -3 дБ)
    b_box, a_box = make_bell(220.0, 1.2, -3.0, fs)
    
    # 3. Убираем ПЛАСТИКОВЫЙ РЕВЕРБ нейросети (400 Гц и 520 Гц)
    b_plast1, a_plast1 = make_bell(400.0, 1.5, -4.0, fs)
    b_plast2, a_plast2 = make_bell(520.0, 1.5, -3.0, fs)
    
    # 4. Убираем ядовитый ИИ-дребезг (широкий вырез на 3500 Гц, -3 дБ, захватывает и гитару, и пианино)
    b_harsh, a_harsh = make_bell(3500.0, 1.0, -3.0, fs)
    
    # 5. Срез цифрового песка (Low-Pass 6500 Гц, 2 порядок - даёт мягкий бархатный верх)
    b_lp, a_lp = signal.butter(2, 6500.0, btype='low', fs=fs)

    # --- ОБРАБОТКА ---
    for ch in range(channels):
        ch_data = data[:, ch]
        
        step1 = signal.lfilter(b_hp, a_hp, ch_data)
        step2 = signal.lfilter(b_box, a_box, step1)
        step3 = signal.lfilter(b_plast1, a_plast1, step2)
        step4 = signal.lfilter(b_plast2, a_plast2, step3)
        step5 = signal.lfilter(b_harsh, a_harsh, step4)
        final_ch = signal.lfilter(b_lp, a_lp, step5)
        
        output_data[:, ch] = final_ch

    # --- ФИКС ПЛАВАНИЯ (Mid/Side монофонизация баса + сужение стерео) ---
    if channels == 2:
        mid = (output_data[:, 0] + output_data[:, 1]) / 2.0
        side = (output_data[:, 0] - output_data[:, 1]) / 2.0
        
        # Узкое винтажное стерео: сужаем базу всего трека на 50% для борьбы с ИИ-плаванием
        side = side * 0.5
        
        # И полностью срезаем низкие частоты (до 250 Гц) из бокового канала (бас в моно)
        sos_side_hp = signal.butter(4, 250.0, 'high', fs=fs, output='sos')
        side = signal.sosfiltfilt(sos_side_hp, side)
        
        # Собираем обратно
        output_data[:, 0] = mid + side
        output_data[:, 1] = mid - side

    # Максимальная нормализация пиков (-0.1 дБ) без плющенья
    max_val = np.max(np.abs(output_data))
    if max_val > 0:
        output_data = output_data * (0.99 / max_val)

    sf.write(output_file, output_data, fs)

if __name__ == "__main__":
    ROOT = Path(__file__).parent
    input_folder = ROOT / "sound" / "wav_input"
    output_folder = ROOT / "sound" / "wav_output"

    if not output_folder.exists():
        output_folder.mkdir(parents=True)

    if input_folder.exists():
        files = list(input_folder.glob("*.wav"))
        print(f"Найдено файлов для обработки: {len(files)}")
        
        for file_path in files:
            out_path = output_folder / f"{file_path.stem}_DarkJazz_Master.wav"
            dark_jazz_mastering(str(file_path), str(out_path))
            print(f"Обработан: {file_path.name}")
        print("\n[ВЕСЬ АЛЬБОМ УСПЕШНО ОЧИЩЕН!]")
    else:
        print(f"Папка не найдена: {input_folder}")