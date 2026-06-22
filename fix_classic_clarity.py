import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import scipy.signal as signal
import soundfile as sf
from pathlib import Path


def fix_clarity_master(input_file, output_file, low_shelf_gain_db=1.5, mid_bell_gain_db=2.0):
    """
    Корректирует баланс версии Clarity: возвращает вес нижнему регистру и плотность середине.

    low_shelf_gain_db: на сколько дБ поднять самый низ (опора фагота/левой руки пианино)
    mid_bell_gain_db: на сколько дБ поднять нижнюю середину (тело инструментов, 200-250 Гц)
    """
    # 1. Читаем исходный WAV файл
    data, fs = sf.read(input_file)

    # Если файл стерео, обрабатываем каждый канал отдельно
    if len(data.shape) > 1:
        channels = data.shape[1]
    else:
        channels = 1
        data = data.reshape(-1, 1)

    output_data = np.zeros_like(data)

    # 2. Настройка частот фильтрации
    # Low Shelf для самого низа (до 100 Гц)
    f_low = 100.0
    # Bell-фильтр для возвращения "тела" в нижнюю середину (около 220 Гц)
    f_mid = 220.0
    Q_mid = 1.0  # Достаточно широкая полоса, чтобы подъем звучал естественно

    for ch in range(channels):
        ch_data = data[:, ch]

        # --- ШАГ 1: Применяем Low Shelf фильтр ---
        A_low = 10 ** (low_shelf_gain_db / 40)
        omega_low = 2 * np.pi * f_low / fs
        sn = np.sin(omega_low)
        cs = np.cos(omega_low)

        b_low = np.array([
            A_low * ((A_low + 1) - (A_low - 1) * cs + 2 * np.sqrt(A_low) * sn),
            2 * A_low * ((A_low - 1) - (A_low + 1) * cs),
            A_low * ((A_low + 1) - (A_low - 1) * cs - 2 * np.sqrt(A_low) * sn)
        ])
        a_low = np.array([
            (A_low + 1) + (A_low - 1) * cs + 2 * np.sqrt(A_low) * sn,
            -2 * ((A_low - 1) + (A_low + 1) * cs),
            (A_low + 1) + (A_low - 1) * cs - 2 * np.sqrt(A_low) * sn
        ])

        inter_data = signal.lfilter(b_low, a_low, ch_data)

        # --- ШАГ 2: Применяем пиковый Bell фильтр на нижнюю середину ---
        A_mid = 10 ** (mid_bell_gain_db / 40)
        omega_mid = 2 * np.pi * f_mid / fs
        alpha_mid = np.sin(omega_mid) / (2 * Q_mid)

        b_mid = np.array([1 + alpha_mid * A_mid, -2 * np.cos(omega_mid), 1 - alpha_mid * A_mid])
        a_mid = np.array([1 + alpha_mid / A_mid, -2 * np.cos(omega_mid), 1 - alpha_mid / A_mid])

        final_ch_data = signal.lfilter(b_mid, a_mid, inter_data)

        output_data[:, ch] = final_ch_data

    # 3. Нормализация, чтобы избежать клиппинга после подъема частот
    max_val = np.max(np.abs(output_data))
    if max_val > 1.0:
        output_data = output_data / max_val
        print("[WARNING] Limiter triggered — output normalized to prevent clipping.")

    # 4. Сохраняем исправленный файл
    sf.write(output_file, output_data, fs)
    print(f"[DONE] Track saved to: {output_file}")


# --- Запуск в рамках проекта AIMusicMasteringFactory ---
ROOT = Path(__file__).parent

input_name  = str(ROOT / "Viola da Gamba v7 Clarity.wav")
output_name = str(ROOT / "sound" / "wav_output" / "Viola da Gamba v7 Clarity_middle.wav")

fix_clarity_master(input_name, output_name, low_shelf_gain_db=1.5, mid_bell_gain_db=2.2)