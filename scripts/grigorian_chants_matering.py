# =============================================================================
# SUNO SURGICAL CLEANUP v11.0 — Choral / Latin Edition
#
# Оптимизировано для хоралов на латыни (Suno AI):
#   1. anlmdn s=3    — бережное шумоподавление (сибилянты s/c/x сохраняем)
#   2. highpass 40Hz — оставляем нижние голоса и орган
#   3. EQ 8кГц -2dB  — минимально (рядом с сибилянтами)
#   4. EQ 10.5кГц -5dB — "стеклянный" призвук сопрано у Suno (нотч)
#   5. EQ 12кГц -4dB  — мягче: воздух хора живёт здесь
#   6. EQ 16кГц -8dB  — aliasing и цифровой песок
#   7. lowpass 18кГц  — сохраняем купол реверба хора
#   8. loudnorm -16 LUFS — стандарт стриминга (новый шаг)
#   9. alimiter       — защита от клипов на выходе
#
# Изменения v11.0 vs v10.1:
#   - Пути теперь относительны __file__, а не CWD (надёжнее при запуске из любой папки)
#   - Временный файл чистится через finally (bug fix)
#   - FFmpeg stderr перехватывается и отображается через rich
#   - loudnorm I=-16:TP=-1.5:LRA=11 — нормализация по LUFS
#   - Выходной формат: pcm_s24le (24-bit) вместо pcm_s16le (16-bit)
# =============================================================================

import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import os
import subprocess
import time
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

# --- Настройки путей (относительно скрипта, не CWD) ---
SCRIPT_DIR  = Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent
INPUT_DIR   = (PROJECT_DIR / "sound" / "wav_input").resolve()
OUTPUT_DIR  = (PROJECT_DIR / "sound" / "wav_output").resolve()
TEMP_DIR    = (PROJECT_DIR / "tmp").resolve()

OUTPUT_SUFFIX = "_v11_choral"   # bumped: пересоздаём с новыми фильтрами

for p in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR]:
    p.mkdir(parents=True, exist_ok=True)

console = Console(legacy_windows=False)


def surgical_restore(input_file: Path, output_file: Path) -> bool:
    """
    Бережная обработка хоралов Suno на латыни — v11.0.

    anlmdn s=3 (было s=7):
        Латинские сибилянты (s, c, x) живут на 6–9 кГц. s=3 убирает
        нейроартефакты, не трогая согласные.

    highpass f=40:
        Контент органа и низких голосов начинается от 40 Hz.

    equalizer f=8000 g=-2:
        Минимально — рядом с сибилянтами. Было g=-4, это замыливало согласные.

    equalizer f=10500 g=-5 (нотч):
        "Стеклянный" призвук синтетических сопрано Suno. w=0.8 — узкий нотч.

    equalizer f=12000 g=-4:
        Мягче (было -6): воздух и акустика зала хора живут здесь.

    equalizer f=16000 g=-8:
        Aliasing и цифровой песок.

    lowpass f=18000:
        Купол реверба и воздух хора (было 17000 — срезало симулированную акустику).

    loudnorm I=-16:TP=-1.5:LRA=11 (НОВЫЙ):
        Стандарт стриминга. Все треки выйдут с одинаковой громкостью.
        True Peak не выше -1.5 dBTP.

    alimiter — True Peak лимитер. Финальная защита от клипов.

    Выход: pcm_s24le (24-bit) — повышенный динамический диапазон vs 16-bit.
    """
    filters = [
        # Шаг 1: Бережное нейросетевое шумоподавление
        "anlmdn=s=3:p=0.002:r=0.002:m=15",

        # Шаг 2: Инфразвук — 40Hz, оставляем орган и низкие голоса
        "highpass=f=40:poles=2",

        # Шаг 3: EQ — точечная хирургия для хорала
        "equalizer=f=8000:t=q:w=1.0:g=-2",     # минимально: рядом с сибилянтами
        "equalizer=f=10500:t=q:w=0.8:g=-5",    # "стекло" сопрано Suno
        "equalizer=f=12000:t=q:w=1.0:g=-4",    # нейрошипение, мягко
        "equalizer=f=16000:t=q:w=1.0:g=-8",    # aliasing и цифровой песок

        # Шаг 4: Мягкий lowpass — купол реверба хора сохраняем
        "lowpass=f=18000:poles=2",

        # Шаг 5: LUFS нормализация — стандарт стриминга
        "loudnorm=I=-16:TP=-1.5:LRA=11",

        # Шаг 6: True Peak лимитер — финальная защита от клипов
        "alimiter=level_in=1:level_out=0.95:limit=0.95:attack=5:release=50:asc=1",
    ]

    tmp_input = TEMP_DIR / f"local_src_{input_file.name}"

    # Копируем исходник во временную папку
    try:
        shutil.copy2(input_file, tmp_input)
    except Exception as e:
        console.print(f"[red]Не удалось скопировать файл для обработки: {e}[/red]")
        return False

    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(tmp_input),
        "-af", ",".join(filters),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s24le",  # 24-bit PCM
        str(output_file)
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if result.returncode != 0 and result.stderr:
            console.print(f"    [red dim]ffmpeg: {result.stderr.strip()}[/red dim]")
        return result.returncode == 0
    except FileNotFoundError:
        console.print("[red]FFmpeg не найден. Убедитесь, что ffmpeg установлен и доступен в PATH.[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Ошибка subprocess: {e}[/red]")
        return False
    finally:
        # Чистим временный файл в любом случае (даже при crash)
        if tmp_input.exists():
            tmp_input.unlink()


def main():
    files = sorted([
        f for f in INPUT_DIR.glob("*")
        if f.suffix.lower() in (".wav", ".mp3", ".flac")
    ])

    if not files:
        console.print(f"[red]Входная папка пуста:[/red] {INPUT_DIR}")
        return

    console.print(Panel.fit(
        "[bold green]🎼 SUNO SURGICAL CLEANUP v11.0 — Choral / Latin Edition[/bold green]\n"
        "[dim]anlmdn s=3 · highpass 40Hz · EQ 8/10.5/12/16kHz · "
        "lowpass 18k · loudnorm -16 LUFS · alimiter · 24-bit PCM[/dim]",
        border_style="green"
    ))
    console.print(f"[dim]  Вход:  {INPUT_DIR}[/dim]")
    console.print(f"[dim]  Выход: {OUTPUT_DIR}[/dim]\n")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold white]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    )

    with progress:
        overall = progress.add_task("[cyan]Обработка хоралов...", total=len(files))

        for src in files:
            stem = src.stem
            out_wav = OUTPUT_DIR / f"{stem}{OUTPUT_SUFFIX}.wav"
            src_abs = src.resolve()
            out_abs = out_wav.resolve()

            if out_wav.exists():
                console.print(f"  [dim]⏭  {stem} — уже обработан, пропускаем[/dim]")
                progress.advance(overall)
                continue

            task = progress.add_task(f"[yellow]⚙️  {stem}", total=1)

            try:
                start = time.time()
                if surgical_restore(src_abs, out_abs):
                    elapsed = time.time() - start
                    console.print(
                        f"  [green]✅ {stem}[/green] "
                        f"[dim]→ -16 LUFS · 24-bit · артефакты убраны ({elapsed:.1f}s)[/dim]"
                    )
                else:
                    console.print(f"  [red]❌ {stem} — FFmpeg вернул ошибку[/red]")
            except Exception as e:
                console.print(f"  [red]❌ {stem}: {e}[/red]")
            finally:
                progress.update(task, completed=1)
                progress.advance(overall)

    console.print(Panel.fit(
        "[bold white]Готово.[/bold white] Файлы в [cyan]sound/wav_output/[/cyan]\n"
        "[dim]Формат: 24-bit PCM WAV · нормализация -16 LUFS · True Peak ≤ -1.5 dBTP[/dim]\n"
        "[dim]Если сибилянты всё ещё шипят → снизь g на 10.5кГц до -7dB[/dim]\n"
        "[dim]Если звук 'ватный' → снизь s=3 до s=1 в anlmdn[/dim]",
        border_style="dim"
    ))


if __name__ == "__main__":
    main()