# Audio Similarity Checker — Dashboard & CLI

## Установка

```bash
cd D:\GitHub\AIMusicMasteringFactory
poetry install
# Всё уже установлено через pyproject.toml корня
```

## Запуск дашборда

```bash
cd audio_similarity_check
poetry run python dashboard.py
```

Откроется на **http://127.0.0.1:5050**

## Возможности дашборда

1. **Множественные пути к каталогам** — добавьте сколько угодно папок с треками (локальные, сетевые, внешние диски)
2. **Два режима работы:**
   - **Новый трек** — проверка одного трека против всего каталога (линейная сложность)
   - **Полная пересборка** — сравнение всех пар внутри каталога (O(n²), запускать периодически)
3. **Прогресс в реальном времени** — Server-Sent Events, видно этапы: сканирование, загрузка признаков, построение baseline, сравнение
4. **Результаты в таблице** — фильтрация по RED/YELLOW/GREEN, экспорт CSV/JSON
5. **История запусков** — сохраняется в памяти сессии

## CLI (прямой запуск v4)

```bash
# Проверить новый трек
poetry run python catalog_similarity_v4.py --catalog ../Felt Piano Jazz --new ../new_track.wav

# Полная пересборка каталога
poetry run python catalog_similarity_v4.py --catalog ../Felt Piano Jazz --rebuild-all

# Создать конфиг
poetry run python catalog_similarity_v4.py --init-config similarity_config.yaml
```

## Конфигурация (similarity_config.yaml)

```yaml
sr: 22050
segment_duration: 30
n_segments: 5
n_fft: 4096
hop_length: 512
n_mels: 128
n_mfcc: 20
top_k: 10
cache_dirname: ".features_cache"
config_version: "4.0"
red_percentile: 99.0
yellow_percentile: 95.0
min_pairs_for_calibration: 30
workers: 0  # 0 = auto (all CPUs)
use_gpu: false
log_level: "INFO"
early_exit_threshold: 0.995
```

## Архитектура

- `catalog_similarity_v3.py` — исходная версия (референс)
- `catalog_similarity_v4.py` — production версия:
  - Параллельный baseline (ProcessPoolExecutor)
  - Кэш с версионированием (авто-инвалидация при смене конфига)
  - Структурированные numpy-массивы (нет object dtype)
  - Опциональный GPU через CuPy
  - Type hints, dataclasses, чистые функции
- `dashboard.py` — Flask веб-интерфейс
- `templates/index.html` — SPA интерфейс

## Кэширование

Признаки сохраняются в `.features_cache/` в каждой папке каталога.
Ключ кэша включает `config_version` — при изменении параметров кэш автоматически пересоздаётся.

## GPU ускорение (опционально)

```bash
# Определите версию CUDA
nvcc --version

# Установите соответствующий cupy
poetry run pip install cupy-cuda12x  # для CUDA 12.x
```

В конфиге: `use_gpu: true`

## Структура отчёта

| Уровень | Значение |
|---------|----------|
| 🔴 RED | Трек в топ-1% самых похожих пар вашего каталога — проверить вручную |
| 🟡 YELLOW | Трек в топ-5% — стоит послушать, но не критично |
| 🟢 GREEN | В пределах нормального фона каталога |

Пороги вычисляются автоматически из распределения сходства внутри **вашего** каталога (self-calibrating).