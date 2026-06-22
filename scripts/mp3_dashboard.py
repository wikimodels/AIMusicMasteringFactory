"""
🎵 MP3 Drops Dashboard — Аудио-аудит нарезок
═══════════════════════════════════════════════════════
Назначение:
    Просмотр, прослушивание и удаление MP3-нарезок (дропов),
    сгенерированных скриптом create_drops.py.

Читает файлы из:   sound/mp3_drops_output/
Порт:              http://localhost:8888

Возможности:
    - Кастомный аудиоплеер с прогресс-баром для каждого трека
    - Рейтинг треков (1–5 цветных точек)
    - Выделение чекбоксами + пакетное удаление
    - Авто-форматирование имён (артикли, апострофы)

Запуск: poetry run python scripts/mp3_dashboard.py
"""

import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import threading
import webbrowser
import sys
import traceback

PORT = 8888
DROPS_DIR = "sound/mp3_drops_output"
RATINGS_FILE = os.path.join(DROPS_DIR, "ratings.json")

def load_ratings():
    if os.path.exists(RATINGS_FILE):
        try:
            with open(RATINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_rating(filename, score):
    ratings = load_ratings()
    ratings[filename] = score
    os.makedirs(os.path.dirname(RATINGS_FILE), exist_ok=True)
    with open(RATINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(ratings, f, indent=4, ensure_ascii=False)

def delete_rating(filename):
    ratings = load_ratings()
    if filename in ratings:
        del ratings[filename]
        os.makedirs(os.path.dirname(RATINGS_FILE), exist_ok=True)
        with open(RATINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(ratings, f, indent=4, ensure_ascii=False)
# Ensure directory exists
os.makedirs(DROPS_DIR, exist_ok=True)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIMusic - Drops Dashboard [v16:53]</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        :root {
            --primary: #1DB954; /* Spotify Green */
            --primary-variant: #1ed760;
            --secondary: #b3b3b3;
            --background: #000000;
            --surface: #181818;
            --error: #e91429;
            --text-primary: #ffffff;
            --text-secondary: #b3b3b3;
            --elevation-2: 0px 4px 6px rgba(0,0,0,0.4);
            --elevation-8: 0px 8px 16px rgba(0,0,0,0.6);
        }

        body {
            font-family: 'Roboto', sans-serif;
            background-color: var(--background);
            color: var(--text-primary);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .header {
            width: 100%;
            background-color: #121212;
            color: white;
            padding: 20px 0;
            border-bottom: 1px solid #282828;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header-content {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 24px;
        }

        h1 {
            margin: 0;
            font-size: 22px;
            font-weight: 500;
            letter-spacing: 0.15px;
            display: flex;
            align-items: center;
            gap: 12px;
            color: var(--primary);
        }

        .container {
            max-width: 1400px;
            width: 100%;
            padding: 32px 24px;
            box-sizing: border-box;
        }

        .actions {
            margin-bottom: 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .btn {
            background-color: var(--primary);
            color: #000000;
            border: none;
            padding: 0 16px;
            height: 36px;
            border-radius: 18px;
            font-family: 'Roboto', sans-serif;
            font-weight: 700;
            font-size: 13px;
            letter-spacing: 1px;
            text-transform: uppercase;
            cursor: pointer;
            box-shadow: var(--elevation-2);
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn:hover {
            background-color: var(--primary-variant);
            transform: scale(1.02);
        }

        .btn-error {
            background-color: transparent;
            color: var(--error);
            border: 1px solid var(--error);
            box-shadow: none;
        }
        
        .btn-error:hover {
            background-color: var(--error);
            color: #ffffff;
            border-color: transparent;
        }

        .btn:disabled {
            background-color: #282828;
            color: #555555;
            border: none;
            box-shadow: none;
            cursor: not-allowed;
            transform: none;
        }

        .track-list {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
            gap: 16px;
        }

        .track-card {
            background: var(--surface);
            border-radius: 6px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            transition: background-color 0.2s;
            position: relative;
            border: 1px solid transparent;
        }

        .track-card:hover {
            background-color: #282828;
        }

        .track-card-header {
            display: flex;
            align-items: flex-start;
            gap: 12px;
            width: 100%;
        }

        .track-checkbox {
            width: 18px;
            height: 18px;
            accent-color: var(--primary);
            cursor: pointer;
            margin-top: 2px;
        }

        .track-info {
            flex-grow: 1;
            overflow: hidden;
        }

        .track-title {
            font-size: 14px;
            font-weight: 500;
            margin: 0 0 4px 0;
            color: var(--text-primary);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .track-meta {
            font-size: 12px;
            color: var(--text-secondary);
            margin: 0;
            display: flex;
            gap: 6px;
            align-items: center;
        }

        .custom-audio {
            display: flex;
            align-items: center;
            gap: 10px;
            width: 100%;
            background: #222222;
            padding: 8px 12px;
            border-radius: 20px;
            box-sizing: border-box;
            margin-top: 4px;
        }

        .play-btn {
            background: var(--primary);
            color: #000;
            border: none;
            width: 28px;
            height: 28px;
            min-width: 28px;
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            cursor: pointer;
            padding: 0;
            transition: transform 0.1s;
        }

        .play-btn:hover {
            transform: scale(1.1);
            background: var(--primary-variant);
        }

        .play-btn .material-icons {
            font-size: 18px;
            margin-left: 1px; /* оптическое выравнивание треугольника */
        }

        .progress-wrapper {
            flex-grow: 1;
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 11px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        .progress-bar {
            flex-grow: 1;
            height: 16px; /* Широкая область клика */
            -webkit-appearance: none;
            background: transparent;
            outline: none;
            cursor: pointer;
            margin: 0;
            padding: 0;
        }

        .progress-bar::-webkit-slider-runnable-track {
            width: 100%;
            height: 4px;
            background: #444;
            border-radius: 2px;
        }

        .progress-bar::-webkit-slider-thumb {
            -webkit-appearance: none;
            height: 12px;
            width: 12px;
            border-radius: 50%;
            background: var(--primary);
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0,0,0,0.5);
            transition: transform 0.1s;
            margin-top: -4px; /* (12px высота кружка - 4px высота полосы) / 2 = 4px отступ */
        }

        .progress-bar::-webkit-slider-thumb:hover {
            transform: scale(1.2);
        }

        /* Рейтинг-бар */
        .rating-bar {
            display: flex;
            justify-content: center;
            gap: 8px;
            margin-top: 4px;
            padding: 4px;
            border-top: 1px solid #222;
        }

        .rating-dot {
            width: 14px;
            height: 14px;
            border-radius: 50%;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.2s;
            opacity: 0.4;
        }

        .rating-dot:hover {
            opacity: 1;
            transform: scale(1.2);
        }

        .rating-dot.active {
            opacity: 1;
            border-color: white;
            box-shadow: 0 0 8px currentColor;
        }

        .dot-1 { background-color: #ff4444; color: #ff4444; }
        .dot-2 { background-color: #ffbb33; color: #ffbb33; }
        .dot-3 { background-color: #666666; color: #666666; }
        .dot-4 { background-color: #99cc00; color: #99cc00; }
        .dot-5 { background-color: #00C851; color: #00C851; }

        .hidden-audio {
            display: none;
        }

        .header-content h1 {
            color: var(--primary);
            flex-shrink: 0;
        }

        .header-stats {
            display: flex;
            align-items: center;
            gap: 20px;
            margin-right: 40px;
            flex-grow: 1;
            justify-content: center;
        }

        .stat-item {
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 14px;
            font-weight: 500;
        }

        .stat-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
        }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 64px 0;
            color: var(--text-secondary);
        }
        
        .empty-state .material-icons {
            font-size: 64px;
            margin-bottom: 16px;
            color: #555;
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="header-content">
            <h1><span class="material-icons">graphic_eq</span> MP3 Drops Dashboard <span style="font-size:10px; opacity:0.5; vertical-align:middle;">v16:53</span></h1>
            
            <div class="header-stats" id="navbarStats">
                <div class="stat-item">Всего: <span id="stat_total">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-1" style="opacity:1"></div> <span id="stat_1">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-2" style="opacity:1"></div> <span id="stat_2">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-3" style="opacity:1"></div> <span id="stat_3">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-4" style="opacity:1"></div> <span id="stat_4">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-5" style="opacity:1"></div> <span id="stat_5">0</span></div>
            </div>

            <div id="status" style="font-size: 14px; font-weight: 400; opacity: 0.9; flex-shrink: 0;">Ready</div>
        </div>
    </div>

    <div class="container">
        <div class="actions">
            <div>
                <input type="checkbox" id="selectAll" class="track-checkbox" style="margin-right: 12px; transform: scale(1.2);">
                <label for="selectAll" style="font-weight: 500; cursor: pointer;">Выделить все</label>
            </div>
            <button id="deleteBtn" class="btn btn-error" disabled>
                <span class="material-icons" style="font-size: 18px;">delete</span>
                Удалить выбранные (<span id="selCount">0</span>)
            </button>
        </div>

        <div class="track-list" id="trackList">
            <!-- Треки будут загружены через JS -->
        </div>
    </div>

    <script>
        const trackListEl = document.getElementById('trackList');
        const selectAllEl = document.getElementById('selectAll');
        const deleteBtn = document.getElementById('deleteBtn');
        const selCountEl = document.getElementById('selCount');
        const statusEl = document.getElementById('status');

        let tracks = [];

        async function loadTracks() {
            try {
                const res = await fetch('/api/tracks');
                tracks = await res.json();
                renderTracks();
                updateNavbarStats();
            } catch (err) {
                console.error(err);
                statusEl.textContent = 'Ошибка загрузки треков';
            }
        }

        function updateNavbarStats() {
            document.getElementById('stat_total').textContent = tracks.length;
            const counts = {1:0, 2:0, 3:0, 4:0, 5:0};
            tracks.forEach(t => {
                if(t.rating >= 1 && t.rating <= 5) counts[t.rating]++;
            });
            for(let i=1; i<=5; i++) {
                document.getElementById(`stat_${i}`).textContent = counts[i];
            }
        }

        function renderTracks() {
            if (tracks.length === 0) {
                trackListEl.innerHTML = `
                    <div class="empty-state">
                        <span class="material-icons">library_music</span>
                        <h2>Нет треков</h2>
                        <p>Нарезки из папки sound/mp3_drops_output/ не найдены.</p>
                    </div>`;
                updateSelection();
                return;
            }

            trackListEl.innerHTML = tracks.map((track, i) => `
                <div class="track-card">
                    <div class="track-card-header">
                        <input type="checkbox" class="track-checkbox" data-filename="${track.filename}" id="chk_${i}">
                        <div class="track-info">
                            <h3 class="track-title" title="${track.name}">${track.name}</h3>
                            <p class="track-meta">
                                <span class="material-icons" style="font-size: 14px;">insert_drive_file</span> ${track.size} MB
                            </p>
                        </div>
                    </div>
                    <div class="custom-audio">
                        <button class="play-btn" onclick="togglePlay(this)">
                            <span class="material-icons">play_arrow</span>
                        </button>
                        <div class="progress-wrapper">
                            <span class="time-current">0:00</span>
                            <input type="range" class="progress-bar" value="0" max="100" oninput="seekTrack(this)">
                            <span class="time-total">0:00</span>
                        </div>
                        <audio class="hidden-audio" preload="metadata" src="/${track.filepath}"></audio>
                    </div>
                    <div class="rating-bar" data-filename="${track.filename}">
                        <div class="rating-dot dot-1 ${track.rating == 1 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 1)" title="Ужасно"></div>
                        <div class="rating-dot dot-2 ${track.rating == 2 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 2)" title="Плохо"></div>
                        <div class="rating-dot dot-3 ${track.rating == 3 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 3)" title="Средне"></div>
                        <div class="rating-dot dot-4 ${track.rating == 4 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 4)" title="Хорошо"></div>
                        <div class="rating-dot dot-5 ${track.rating == 5 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 5)" title="Отлично!"></div>
                    </div>
                </div>
            `).join('');

            // Навешиваем слушателей на чекбоксы
            document.querySelectorAll('.track-checkbox[id^="chk_"]').forEach(chk => {
                chk.addEventListener('change', updateSelection);
            });
            
            // Навешиваем слушателей на кастомные плееры
            document.querySelectorAll('.custom-audio').forEach(container => {
                const audio = container.querySelector('.hidden-audio');
                const progress = container.querySelector('.progress-bar');
                const tCurr = container.querySelector('.time-current');
                const tTot = container.querySelector('.time-total');
                const icon = container.querySelector('.material-icons');

                audio.addEventListener('timeupdate', () => {
                    if (!audio.duration) return;
                    progress.value = (audio.currentTime / audio.duration) * 100;
                    tCurr.textContent = formatTime(audio.currentTime);
                });

                audio.addEventListener('loadedmetadata', () => {
                    if (audio.duration && !isNaN(audio.duration)) {
                        tTot.textContent = formatTime(audio.duration);
                    }
                });
                
                audio.addEventListener('ended', () => {
                    icon.textContent = 'play_arrow';
                    progress.value = 0;
                    tCurr.textContent = "0:00";
                    if (currentAudio === audio) {
                        currentAudio = null;
                        currentPlayingBtn = null;
                    }
                });
            });

            updateSelection();
        }

        // --- Custom Player Logic ---
        let currentPlayingBtn = null;
        let currentAudio = null;

        function togglePlay(btn) {
            const container = btn.closest('.custom-audio');
            const audio = container.querySelector('.hidden-audio');
            const icon = btn.querySelector('.material-icons');

            // При запуске нового трека останавливаем старый
            if (currentAudio && currentAudio !== audio) {
                currentAudio.pause();
                if (currentPlayingBtn) currentPlayingBtn.querySelector('.material-icons').textContent = 'play_arrow';
            }

            if (audio.paused) {
                audio.play();
                icon.textContent = 'pause';
                currentAudio = audio;
                currentPlayingBtn = btn;
            } else {
                audio.pause();
                icon.textContent = 'play_arrow';
                currentAudio = null;
                currentPlayingBtn = null;
            }
        }

        function seekTrack(input) {
            const container = input.closest('.custom-audio');
            const audio = container.querySelector('.hidden-audio');
            if (audio.duration && !isNaN(audio.duration)) {
                audio.currentTime = (input.value / 100) * audio.duration;
            }
        }

        function formatTime(s) {
            if (isNaN(s)) return "0:00";
            let m = Math.floor(s / 60);
            let sec = Math.floor(s % 60);
            return `${m}:${sec < 10 ? '0' : ''}${sec}`;
        }

        async function rateTrack(filename, score) {
            try {
                // Визуальный отклик сразу
                const bar = document.querySelector(`.rating-bar[data-filename="${filename}"]`);
                if (bar) {
                    bar.querySelectorAll('.rating-dot').forEach(d => d.classList.remove('active'));
                    bar.querySelector(`.dot-${score}`).classList.add('active');
                }

                const res = await fetch('/api/rate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filename, score })
                });
                
                if (res.ok) {
                    // Обновляем локальные данные трека
                    const track = tracks.find(t => t.filename === filename);
                    if (track) track.rating = score;
                    
                    updateNavbarStats();
                    // Больше не выводим назойливое "Оценка сохранена"
                    statusEl.textContent = 'Ready';
                } else {
                    const errText = await res.text();
                    statusEl.textContent = 'Ошибка сохранения: ' + errText;
                }
            } catch (e) {
                console.error(e);
                statusEl.textContent = 'Ошибка сети при сохранении';
            }
        }
        // ---------------------------

        function updateSelection() {
            const checked = document.querySelectorAll('.track-checkbox[id^="chk_"]:checked');
            const total = document.querySelectorAll('.track-checkbox[id^="chk_"]');
            
            selCountEl.textContent = checked.length;
            deleteBtn.disabled = checked.length === 0;
            
            if (total.length > 0) {
                selectAllEl.checked = checked.length === total.length;
                selectAllEl.indeterminate = checked.length > 0 && checked.length < total.length;
            } else {
                selectAllEl.checked = false;
                selectAllEl.indeterminate = false;
            }
        }

        selectAllEl.addEventListener('change', (e) => {
            document.querySelectorAll('.track-checkbox[id^="chk_"]').forEach(chk => {
                chk.checked = e.target.checked;
            });
            updateSelection();
        });

        deleteBtn.addEventListener('click', async () => {
            const checked = Array.from(document.querySelectorAll('.track-checkbox[id^="chk_"]:checked'))
                                .map(chk => chk.dataset.filename);
            
            if (checked.length === 0) return;
            if (!confirm(`Удалить ${checked.length} треков навсегда?`)) return;

            deleteBtn.disabled = true;
            statusEl.textContent = 'Удаление...';

            try {
                const res = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: checked })
                });

                if (res.ok) {
                    statusEl.textContent = `Удалено ${checked.length} треков`;
                    await loadTracks();
                } else {
                    statusEl.textContent = 'Ошибка удаления';
                }
            } catch(e) {
                statusEl.textContent = 'Ошибка сети';
            }
            
            setTimeout(() => statusEl.textContent = 'Ready', 3000);
        });

        // Запуск
        loadTracks();
    </script>
</body>
</html>
"""

class DashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Включаем логирование для отладки
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          format % args))

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
            
        elif self.path == '/api/tracks':
            import re
            files_data = []
            ratings = load_ratings()
            
            if os.path.exists(DROPS_DIR):
                for f in os.listdir(DROPS_DIR):
                    if f.lower().endswith(".mp3"):
                        full_path = os.path.join(DROPS_DIR, f)
                        size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
                        
                        # Роскошное форматирование имени для дашборда
                        display_name = f.replace('_', ' ').replace('.mp3', '')
                        
                        # 1) Удаление начальных артиклей (The, A, An)
                        display_name = re.sub(r'^(?:The|A|An)\s+', '', display_name, flags=re.IGNORECASE)
                        
                        # 2) Исправление популярных сокращений (Youve -> You've и т.д.)
                        contractions = {
                            r'\bYouve\b': "You've",
                            r'\bDoesnt\b': "Doesn't",
                            r'\bDont\b': "Don't",
                            r'\bCant\b': "Can't",
                            r'\bIm\b': "I'm",
                            r'\bIve\b': "I've",
                            r'\bIsnt\b': "Isn't",
                            r'\bArent\b': "Aren't",
                            r'\bWont\b': "Won't",
                            r'\bWouldnt\b': "Wouldn't",
                            r'\bCouldnt\b': "Couldn't",
                            r'\bShouldnt\b': "Shouldn't",
                            r'\bWasnt\b': "Wasn't",
                            r'\bWerent\b': "Weren't"
                        }
                        for pattern, repl in contractions.items():
                            display_name = re.sub(pattern, repl, display_name)
                        
                        files_data.append({
                            "filename": f,
                            "name": display_name.strip(),
                            "filepath": full_path.replace("\\", "/"),
                            "size": size_mb,
                            "rating": ratings.get(f, 0)
                        })
                        
            # Сортируем по алфавиту
            files_data.sort(key=lambda x: x["name"])
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(files_data).encode('utf-8'))
            return

        # Иначе используем стандартный обработчик (для отдачи MP3 файлов по путям)
        self.path = unquote(self.path)
        super().do_GET()

    def do_POST(self):
        try:
            if self.path == '/api/delete':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                files_to_delete = data.get('files', [])
                deleted_count = 0
                
                for f in files_to_delete:
                    if "/" not in f and "\\" not in f:
                        file_path = os.path.join(DROPS_DIR, f)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                delete_rating(f) # Удаляем рейтинг из JSON при удалении файла
                                deleted_count += 1
                                print(f"🗑️ Удален: {f} (и его рейтинг)")
                            except Exception as e:
                                print(f"❌ Ошибка удаления {f}: {e}")
                                
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "deleted": deleted_count}).encode('utf-8'))
                return

            elif self.path == '/api/rate':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                filename = data.get('filename')
                score = data.get('score')
                
                print(f"⭐ Rating attempt: {filename} = {score}") # Отладка
                
                if filename and score is not None: # score может быть 0, если рейтинг сброшен (хотя у нас 1-5)
                    save_rating(filename, score)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "rating": score}).encode('utf-8'))
                    return
                
                self.send_response(400)
                self.end_headers()
                return
        except Exception as e:
            print(f"🔥 Ошибка в do_POST: {e}")
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, DashboardHandler)
    print(f"\n🎨 Angular Material Dashboard запущен!")
    print(f"🔗 Открой в браузере: http://localhost:{PORT}")
    print(f"🛑 Для остановки нажми Ctrl+C\n")
    httpd.serve_forever()

if __name__ == '__main__':
    # Автоматически открываем браузер
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
