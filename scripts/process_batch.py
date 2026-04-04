"""
process_batch.py — переименование WAV + перемещение TXT в metadata/<Album>

ИНСТРУКЦИЯ:
1. Заполни ALBUM_NAME и RENAME_MAP
2. Запусти: python scripts/process_batch.py
"""

import os, re, shutil
from datetime import datetime

# ══════════════════════════════════════════════════════════════
# НАСТРОЙКИ — заполнить перед запуском
# ══════════════════════════════════════════════════════════════

WAV_INPUT = r"D:\GitHub\AIMusicMasteringFactory\sound\wav_input"
META_ROOT = r"D:\GitHub\AIMusicMasteringFactory\metadata"

# Имя папки альбома в metadata/ (создаётся автоматически если нет)
ALBUM_NAME = "Level_0_Infinite_Carpet"   # ← менять под альбом

# UUID (полный) → (Title для TXT, Filename без расширения)
# Title: Title Case, предлоги строчные если не первое слово
# Filename: слова через _, без спецсимволов (апостроф, !, /, ?)
RENAME_MAP = {
    # Пример — замени на актуальный маппинг после апрува таблицы:
    # "acc08cfe-76cf-4457-8c1a-5f7ab9f2225c": ("Cave Echo Anemoia", "Cave_Echo_Anemoia"),
}

# ══════════════════════════════════════════════════════════════
# ЛОГИКА — не менять
# ══════════════════════════════════════════════════════════════

def find_file(folder: str, uuid: str, ext: str) -> str | None:
    """Найти файл с UUID в имени и нужным расширением."""
    for f in os.listdir(folder):
        if uuid in f and f.lower().endswith(ext.lower()):
            return os.path.join(folder, f)
    return None


def safe_meta_path(meta_dir: str, filename: str) -> str:
    """Если файл уже существует в meta_dir — добавить дату-время к имени."""
    target = os.path.join(meta_dir, filename)
    if os.path.exists(target):
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{stamp}{ext}"
        target = os.path.join(meta_dir, filename)
        print(f"  [CONFLICT] -> сохранён как {filename}")
    return target


def update_txt_content(path: str, old_wav_name: str, new_wav_name: str, new_title: str):
    """Обновить строки 'Metadata for:' и 'Title:' в TXT-файле."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace(
        f"Metadata for: {old_wav_name}",
        f"Metadata for: {new_wav_name}"
    )
    content = re.sub(r"(?m)^Title: .*", f"Title: {new_title}", content)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def check_uniqueness(meta_dir: str, proposed_filenames: set[str]) -> set[str]:
    """Вернуть набор имён, уже занятых в альбоме."""
    if not os.path.isdir(meta_dir):
        return set()
    existing = {os.path.splitext(f)[0] for f in os.listdir(meta_dir)}
    return proposed_filenames & existing


def main():
    if not RENAME_MAP:
        print("[ERROR] RENAME_MAP пуст. Заполни маппинг UUID->Title/Filename.")
        return

    meta_dir = os.path.join(META_ROOT, ALBUM_NAME)
    os.makedirs(meta_dir, exist_ok=True)

    # ── Проверка уникальности внутри альбома ──────────────────
    proposed = {fn for _, fn in RENAME_MAP.values()}
    conflicts = check_uniqueness(meta_dir, proposed)
    if conflicts:
        print("[WARN] Конфликты с существующими треками альбома:")
        for c in sorted(conflicts):
            print(f"  - {c}")
        print("Уточни имена в RENAME_MAP и перезапусти.")
        return

    # ── Обработка треков ──────────────────────────────────────
    ok = 0
    missing = []

    for uuid, (title, file_base) in RENAME_MAP.items():
        new_wav = file_base + ".wav"
        new_txt = file_base + ".txt"

        wav_path = find_file(WAV_INPUT, uuid, ".wav")
        txt_path = find_file(WAV_INPUT, uuid, ".txt")

        if not wav_path:
            missing.append(uuid)
            print(f"  [MISS] {uuid}")
            continue

        old_wav_name = os.path.basename(wav_path)

        # Обновить и переместить TXT
        if txt_path:
            update_txt_content(txt_path, old_wav_name, new_wav, title)
            dest_txt = safe_meta_path(meta_dir, new_txt)
            shutil.move(txt_path, dest_txt)

        # Переименовать WAV (на месте)
        new_wav_path = os.path.join(WAV_INPUT, new_wav)
        os.rename(wav_path, new_wav_path)

        print(f"  OK  {title}")
        ok += 1

    # ── Итог ──────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"Renamed: {ok}/{len(RENAME_MAP)}")

    if missing:
        print("\nNot found (UUID):")
        for m in missing:
            print(f"  {m}")

    wav_files = sorted(f for f in os.listdir(WAV_INPUT) if f.endswith(".wav"))
    print(f"\nWAV in wav_input ({len(wav_files)}):")
    for f in wav_files:
        print(f"  {f}")

    txt_files = sorted(os.listdir(meta_dir))
    print(f"\nTXT in metadata/{ALBUM_NAME} ({len(txt_files)}):")
    for f in txt_files:
        print(f"  {f}")


if __name__ == "__main__":
    main()
