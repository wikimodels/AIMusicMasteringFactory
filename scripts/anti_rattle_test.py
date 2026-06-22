import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import subprocess
from pathlib import Path
from rich.console import Console

console = Console(legacy_windows=False)

SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
INPUT_DIR = (PROJECT_DIR / "sound" / "wav_input").resolve()
OUTPUT_DIR = (PROJECT_DIR / "sound" / "wav_output").resolve()

# Ищем наш проблемный файл. Можно просто взять первый попавшийся Original_*.wav или просто первый файл
input_file = list(INPUT_DIR.glob("*.wav"))[0]

# Базовая цепочка v11, НО с ослабленным шумоподавителем (s=1) чтобы он не добавлял бульканья
BASE_FILTERS = [
    "anlmdn=s=1:p=0.002:r=0.002:m=15",
    "highpass=f=40:poles=2",
    "equalizer=f=8000:t=q:w=1.0:g=-2",
    "equalizer=f=10500:t=q:w=0.8:g=-5",
    "equalizer=f=12000:t=q:w=1.0:g=-4",
    "equalizer=f=16000:t=q:w=1.0:g=-8",
    "lowpass=f=18000:poles=2",
]

FINAL_LIMITER = [
    "loudnorm=I=-16:TP=-1.5:LRA=11",
    "alimiter=level_in=1:level_out=0.95:limit=0.95:attack=5:release=50:asc=1"
]

TEST_CASES = {
    "notch_150hz": [
        # Узкий вырез в гудящем низе
        "equalizer=f=150:t=q:w=2.0:g=-8"
    ],
    "notch_300hz": [
        # Узкий вырез нижней середины (где часто рвется фаза)
        "equalizer=f=300:t=q:w=2.0:g=-8"
    ],
    "notch_2500hz": [
        # Вырез в зоне "песка" и роботизированного скрежета
        "equalizer=f=2500:t=q:w=2.0:g=-8"
    ],
    "notch_4000hz": [
        # Вырез высокой цифровой грязи
        "equalizer=f=4000:t=q:w=2.0:g=-8"
    ]
}

def process_test(name, extra_filters):
    out_file = OUTPUT_DIR / f"{input_file.stem}_{name}.wav"
    
    # Собираем фильтры: БАЗА -> ЛЕКАРСТВО -> ЛИМИТЕР
    all_filters = BASE_FILTERS + extra_filters + FINAL_LIMITER
    
    # Ищем путь к скачанному ffmpeg
    ffmpeg_exe = PROJECT_DIR / "bin" / "ffmpeg.exe"
    if not ffmpeg_exe.exists():
        ffmpeg_exe = "ffmpeg" # fallback
        
    cmd = [
        str(ffmpeg_exe), "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(input_file),
        "-af", ",".join(all_filters),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s24le",
        str(out_file)
    ]
    
    console.print(f"[yellow]Генерируем {name}...[/yellow]")
    subprocess.run(cmd)
    console.print(f"[green]Готово: {out_file.name}[/green]")

def main():
    console.print(f"\n[cyan]🔍 ДИАГНОСТИКА: Дребезжание Suno ({input_file.name})[/cyan]")
    for name, filters in TEST_CASES.items():
        process_test(name, filters)
    console.print("\n[bold white]Все три версии в sound/wav_output. Слушать 21-23 сек![/bold white]")

if __name__ == "__main__":
    main()
