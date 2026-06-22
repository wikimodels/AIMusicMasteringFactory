import os
import urllib.request
import zipfile
from pathlib import Path
from rich.console import Console

console = Console(legacy_windows=False)

PROJECT_DIR = Path("D:/GitHub/AIMusicMasteringFactory")
BIN_DIR = PROJECT_DIR / "bin"
BIN_DIR.mkdir(exist_ok=True)

URL = "https://github.com/GyanD/codexffmpeg/releases/download/8.1/ffmpeg-8.1-full_build.zip"
ZIP_PATH = BIN_DIR / "ffmpeg_full.zip"

def download_and_extract():
    if not (BIN_DIR / "ffmpeg.exe").exists():
        console.print(f"[cyan]Скачиваем полную сборку FFmpeg (подождите минутку)...[/cyan]")
        urllib.request.urlretrieve(URL, ZIP_PATH)
        
        console.print("[yellow]Распаковываем...[/yellow]")
        with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
            # Ищем ffmpeg.exe внутри архива
            for file_info in zip_ref.filelist:
                if file_info.filename.endswith("ffmpeg.exe"):
                    # Читаем файл из архива и пишем напрямую в bin/
                    data = zip_ref.read(file_info.filename)
                    with open(BIN_DIR / "ffmpeg.exe", "wb") as f:
                        f.write(data)
                    break
        
        # Удаляем архив
        ZIP_PATH.unlink()
        console.print("[green]Успешно! Полный ffmpeg.exe помещен в папку bin/[/green]")
    else:
        console.print("[green]ffmpeg.exe уже в папке bin/[/green]")

if __name__ == "__main__":
    download_and_extract()
