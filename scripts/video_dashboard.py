"""
Video Drops Dashboard Backend & Frontend v2
Запускает локальный веб-сервер с поддержкой перемотки видео (HTTP 206),
разделением на вертикальные и горизонтальные, и переименованием.
"""

import os
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote
import threading
import webbrowser
import sys
import traceback

PORT = 8890
VIDEO_DIR = os.getenv("VIDEO_DIR", "D:/VideoFootage")
RATINGS_FILE = os.path.join(VIDEO_DIR, "video_ratings.json")
METADATA_FILE = os.path.join(VIDEO_DIR, "video_metadata.json")

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

def load_video_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_video_metadata(metadata):
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

def get_video_orientation(filepath):
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', filepath]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8').strip()
        dims = result.split('x')
        if len(dims) == 2:
            w, h = int(dims[0]), int(dims[1])
            return "vertical" if w < h else "horizontal"
    except Exception as e:
        print(f"ffprobe error for {filepath}: {e}")
    return "horizontal" # fallback

os.makedirs(VIDEO_DIR, exist_ok=True)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AIMusic - Video Gallery</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        :root {
            --primary: #1DB954;
            --primary-variant: #1ed760;
            --secondary: #b3b3b3;
            --background: #000000;
            --surface: #181818;
            --error: #e91429;
            --text-primary: #ffffff;
            --text-secondary: #b3b3b3;
            --elevation-2: 0px 4px 6px rgba(0,0,0,0.4);
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
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }

        .btn {
            background-color: var(--primary);
            color: #000000;
            border: none;
            padding: 0 16px;
            height: 36px;
            border-radius: 18px;
            font-weight: 700;
            font-size: 13px;
            text-transform: uppercase;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            transition: 0.2s;
        }

        .btn:hover { background-color: var(--primary-variant); }
        .btn-error {
            background-color: transparent;
            color: var(--error);
            border: 1px solid var(--error);
        }
        .btn-error:hover { background-color: var(--error); color: #fff; border-color: transparent; }
        .btn:disabled { background-color: #282828; color: #555; cursor: not-allowed; border-color: transparent; }

        .btn-save-all {
            background-color: var(--primary);
            color: #000;
        }
        .btn-save-all:hover {
            transform: scale(1.05);
        }

        .track-list {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
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
            border: 1px solid transparent;
            min-width: 0; /* Фиксит баг Grid, когда элемент больше колонки */
            box-sizing: border-box;
        }
        .track-card:hover { background-color: #282828; }

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
            margin-top: 4px;
        }

        .track-info {
            flex-grow: 1;
            overflow: hidden;
        }

        .rename-input {
            background: rgba(255,255,255,0.05);
            border: 1px solid #444;
            color: var(--text-primary);
            width: 100%;
            font-size: 14px;
            font-weight: 500;
            font-family: inherit;
            padding: 5px 8px;
            margin-bottom: 4px;
            border-radius: 4px;
            transition: all 0.2s;
            box-sizing: border-box;
        }

        .rename-input.changed {
            border-color: #ffbb33;
            background: rgba(255, 187, 51, 0.1);
        }

        .rename-input:focus {
            outline: none;
            border-color: var(--primary);
            background: rgba(255,255,255,0.1);
        }

        .track-meta {
            font-size: 12px;
            color: var(--text-secondary);
            margin: 0;
            display: flex;
            gap: 6px;
            align-items: center;
        }

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
            opacity: 0.4;
            transition: all 0.2s;
        }

        .rating-dot:hover { opacity: 1; transform: scale(1.2); }
        .rating-dot.active { opacity: 1; border-color: white; box-shadow: 0 0 8px currentColor; }
        .dot-1 { background-color: #ff4444; color: #ff4444; }
        .dot-2 { background-color: #ffbb33; color: #ffbb33; }
        .dot-3 { background-color: #666666; color: #666666; }
        .dot-4 { background-color: #99cc00; color: #99cc00; }
        .dot-5 { background-color: #00C851; color: #00C851; }

        .header-stats {
            display: flex;
            align-items: center;
            gap: 20px;
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

        .stat-dot { width: 10px; height: 10px; border-radius: 50%; }

        .empty-state {
            grid-column: 1 / -1;
            text-align: center;
            padding: 64px 0;
            color: var(--text-secondary);
        }
        
        .empty-state .material-icons { font-size: 64px; margin-bottom: 16px; color: #555; }
        
        .section-title {
            font-size: 16px; 
            color: var(--primary); 
            margin: 0; 
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .search-box {
            position: relative;
            display: flex;
            align-items: center;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 4px 12px;
            transition: all 0.2s ease;
            width: 250px;
            margin-right: 20px;
            margin-left: 30px;
        }

        .search-box:focus-within {
            background: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 1px var(--primary);
            width: 300px;
        }

        .search-icon {
            color: #b3b3b3;
            font-size: 20px !important;
            margin-right: 8px;
        }

        .search-input {
            background: transparent;
            border: none;
            color: white;
            font-size: 14px;
            width: 100%;
            outline: none;
            font-family: inherit;
        }

        .search-input::placeholder {
            color: #888;
        }

        .search-clear {
            color: #b3b3b3;
            font-size: 18px !important;
            cursor: pointer;
            visibility: hidden;
        }

        .search-clear:hover {
            color: white;
        }
    </style>
</head>
<body>

    <div class="header">
        <div class="header-content">
            <h1><span class="material-icons">movie</span> Video Gallery</h1>
            
            <div class="search-box">
                <span class="material-icons search-icon">search</span>
                <input type="text" id="searchInput" class="search-input" placeholder="Поиск видео..." oninput="handleSearch()">
                <span class="material-icons search-clear" id="searchClear" onclick="clearSearch()">close</span>
            </div>

            <div class="header-stats" id="navbarStats">
                <div class="stat-item">Всего: <span id="stat_total">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-1" style="opacity:1"></div> <span id="stat_1">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-2" style="opacity:1"></div> <span id="stat_2">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-3" style="opacity:1"></div> <span id="stat_3">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-4" style="opacity:1"></div> <span id="stat_4">0</span></div>
                <div class="stat-item"><div class="stat-dot dot-5" style="opacity:1"></div> <span id="stat_5">0</span></div>
            </div>
            <div style="display: flex; align-items: center; gap: 16px;">
                <button id="deleteBtn" class="btn btn-error" disabled>
                    <span class="material-icons" style="font-size: 18px;">delete</span>
                    Удалить (<span id="selCount">0</span>)
                </button>
                <div id="status" style="font-size: 14px; font-weight: 400; opacity: 0.9; color: #b3b3b3;">Ready</div>
                <button class="btn btn-save-all" onclick="saveAllChanges()">
                    <span class="material-icons" style="font-size: 18px;">save</span> 
                    Сохранить изменения
                </button>
            </div>
        </div>
    </div>

    <div class="container">
        <div class="actions">
            <div style="display: flex; align-items: center; gap: 32px;">
                <div>
                    <input type="checkbox" id="selectAll" class="track-checkbox" style="margin-right: 12px; transform: scale(1.2);">
                    <label for="selectAll" style="font-weight: 500; cursor: pointer;">Выделить все на странице</label>
                </div>
                
                <h2 class="section-title" id="vertHeaderMain" style="display:none;"><span class="material-icons">crop_portrait</span> Вертикальные видео (<span id="vertCount">0</span>)</h2>
                <h2 class="section-title" id="horizHeaderMain" style="display:none;"><span class="material-icons">crop_landscape</span> Горизонтальные видео (<span id="horizCount">0</span>)</h2>
            </div>
        </div>
        
        <!-- Пустой стейт -->
        <div id="emptyContainer" style="display: none;">
            <div class="empty-state">
                <span class="material-icons">video_library</span>
                <h2>Нет видео</h2>
                <p>В выбранной папке ничего не найдено.</p>
            </div>
        </div>

        <div style="width: 100%;" id="verticalContainer">
            <div class="track-list" id="verticalList"></div>
        </div>

        <div style="width: 100%; margin-top: 32px;" id="horizontalContainer">
            <div class="track-list" id="horizontalList"></div>
        </div>
    </div>

    <script>
        const verticalListEl = document.getElementById('verticalList');
        const horizontalListEl = document.getElementById('horizontalList');
        const selectAllEl = document.getElementById('selectAll');
        const deleteBtn = document.getElementById('deleteBtn');
        const selCountEl = document.getElementById('selCount');
        const statusEl = document.getElementById('status');
        let tracks = [];
        let searchQuery = "";

        function handleSearch() {
            const input = document.getElementById('searchInput');
            const clearBtn = document.getElementById('searchClear');
            searchQuery = input.value.toLowerCase().trim();
            
            clearBtn.style.visibility = searchQuery.length > 0 ? 'visible' : 'hidden';
            renderTracks();
        }

        function clearSearch() {
            const input = document.getElementById('searchInput');
            input.value = "";
            handleSearch();
            input.focus();
        }

        function showStatus(text, color="#b3b3b3", timeout=3000) {
            statusEl.textContent = text;
            statusEl.style.color = color;
            if(timeout) setTimeout(() => { statusEl.textContent = 'Ready'; statusEl.style.color = "#b3b3b3"; }, timeout);
        }

        async function loadTracks() {
            try {
                const res = await fetch('/api/videos');
                tracks = await res.json();
                renderTracks();
                updateNavbarStats();
            } catch (err) {
                console.error(err);
                showStatus('Ошибка загрузки видео', 'var(--error)', 0);
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

        function markChanged(inputEl) {
            const orig = inputEl.dataset.originalFilename;
            const currentTrack = tracks.find(t => t.filename === orig);
            if (currentTrack && currentTrack.name !== inputEl.value.trim()) {
                inputEl.classList.add('changed');
            } else {
                inputEl.classList.remove('changed');
            }
        }

        function buildCardHtml(track, i) {
            return `
                <div class="track-card">
                    <div class="track-card-header">
                        <input type="checkbox" class="track-checkbox" data-filename="${track.filename}" id="chk_${i}">
                        <div class="track-info">
                            <input type="text" class="rename-input name-input-field" 
                                   data-original-filename="${track.filename}" 
                                   value="${track.name}" 
                                   oninput="markChanged(this)"
                                   onkeydown="if(event.key === 'Enter') saveAllChanges();" 
                                   title="Отредактируйте и нажмите 'Сохранить изменения' наверху">
                            <p class="track-meta">
                                <span class="material-icons" style="font-size: 14px;">insert_drive_file</span> ${track.size} MB
                            </p>
                        </div>
                    </div>
                    
                    <video controls preload="metadata" src="/${track.filepath}" style="width: 100%; max-height: 400px; border-radius: 6px; margin-top: 4px; background: #000;"></video>
                    
                    <div class="rating-bar" data-filename="${track.filename}">
                        <div class="rating-dot dot-1 ${track.rating == 1 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 1)"></div>
                        <div class="rating-dot dot-2 ${track.rating == 2 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 2)"></div>
                        <div class="rating-dot dot-3 ${track.rating == 3 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 3)"></div>
                        <div class="rating-dot dot-4 ${track.rating == 4 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 4)"></div>
                        <div class="rating-dot dot-5 ${track.rating == 5 ? 'active' : ''}" onclick="rateTrack('${track.filename}', 5)"></div>
                    </div>
                </div>
            `;
        }

        function renderTracks() {
            const displayTracks = searchQuery 
                ? tracks.filter(t => t.name.toLowerCase().includes(searchQuery))
                : tracks;

            if (displayTracks.length === 0) {
                document.getElementById('emptyContainer').style.display = 'block';
                document.getElementById('verticalContainer').style.display = 'none';
                document.getElementById('horizontalContainer').style.display = 'none';
                document.getElementById('vertHeaderMain').style.display = 'none';
                document.getElementById('horizHeaderMain').style.display = 'none';
                updateSelection();
                return;
            }
            
            document.getElementById('emptyContainer').style.display = 'none';

            const vertTracks = displayTracks.filter(t => t.orientation === 'vertical');
            const horizTracks = displayTracks.filter(t => t.orientation === 'horizontal');

            document.getElementById('vertCount').textContent = vertTracks.length;
            document.getElementById('horizCount').textContent = horizTracks.length;

            if (vertTracks.length > 0) {
                document.getElementById('verticalContainer').style.display = 'block';
                document.getElementById('vertHeaderMain').style.display = 'flex';
                verticalListEl.innerHTML = vertTracks.map((t) => buildCardHtml(t, t.id)).join('');
            } else {
                document.getElementById('verticalContainer').style.display = 'none';
                document.getElementById('vertHeaderMain').style.display = 'none';
            }

            if (horizTracks.length > 0) {
                document.getElementById('horizontalContainer').style.display = 'block';
                document.getElementById('horizHeaderMain').style.display = 'flex';
                horizontalListEl.innerHTML = horizTracks.map((t) => buildCardHtml(t, t.id)).join('');
            } else {
                document.getElementById('horizontalContainer').style.display = 'none';
                document.getElementById('horizHeaderMain').style.display = 'none';
            }

            document.querySelectorAll('.track-checkbox[id^="chk_"]').forEach(chk => {
                chk.addEventListener('change', updateSelection);
            });
            updateSelection();
        }

        async function saveAllChanges() {
            showStatus('Сохранение всех...', 'white', 0);
            const inputs = document.querySelectorAll('.rename-input.changed');
            
            if (inputs.length === 0) {
                showStatus('Уже сохранено', '#b3b3b3');
                return;
            }

            let savedAny = false;
            let errs = [];

            // Сохраняем по очереди, чтобы не спамить API сильно
            for (let i = 0; i < inputs.length; i++) {
                const inputEl = inputs[i];
                const originalFilename = inputEl.dataset.originalFilename;
                const newName = inputEl.value.trim();
                
                if (!newName) continue;
                
                try {
                    const res = await fetch('/api/rename', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ original: originalFilename, newName: newName })
                    });
                    
                    if (res.ok) {
                        savedAny = true;
                        inputEl.classList.remove('changed');
                    } else {
                        const errText = await res.text();
                        errs.push(errText);
                    }
                } catch (e) {
                    errs.push(e.message);
                }
            }

            if (errs.length > 0) {
                showStatus('Ошибки: ' + errs[0], 'var(--error)', 5000);
            } else if (savedAny) {
                showStatus('Все изменения сохранены ✅', 'var(--primary)');
                await loadTracks();
            }
        }

        async function rateTrack(filename, score) {
            try {
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
                    const track = tracks.find(t => t.filename === filename);
                    if (track) track.rating = score;
                    updateNavbarStats();
                }
            } catch (e) {
                console.error(e);
                showStatus('Ошибка сети при сохранении', 'var(--error)');
            }
        }

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
            if (!confirm(`Удалить ${checked.length} видео навсегда?`)) return;

            deleteBtn.disabled = true;
            showStatus('Удаление...', 'white', 0);

            try {
                const res = await fetch('/api/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ files: checked })
                });

                if (res.ok) {
                    showStatus(`Удалено ${checked.length} видео`, 'var(--primary)');
                    await loadTracks();
                } else {
                    showStatus('Ошибка удаления', 'var(--error)');
                }
            } catch(e) {
                showStatus('Ошибка сети', 'var(--error)');
            }
        });

        loadTracks();
    </script>
</body>
</html>
"""

class VideoDashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Отключаем спам логов
        pass

    def translate_path(self, path):
        unquoted_path = unquote(path)
        if unquoted_path.startswith('/video/'):
            rel_path = unquoted_path[len('/video/'):]
            return os.path.join(VIDEO_DIR, rel_path)
        return super().translate_path(path)
        
    def send_head(self):
        """
        Кастомная имплементация send_head с поддержкой HTTP 206 Partial Content (Range requests)
        Специально для поддержки потокового видео в браузере.
        """
        path = self.translate_path(self.path)
        f = None
        if os.path.isdir(path):
            return super().send_head()
            
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        file_size = os.fstat(f.fileno()).st_size
        
        # Разрешаем Range
        if 'Range' in self.headers:
            try:
                range_str = self.headers['Range'].replace('bytes=', '')
                start_str, end_str = range_str.split('-')
                start = int(start_str) if start_str else 0
                end = int(end_str) if end_str else file_size - 1
                
                if start >= file_size or end >= file_size:
                    self.send_error(416, "Requested Range Not Satisfiable")
                    f.close()
                    return None
                    
                length = end - start + 1
                self.send_response(206)
                self.send_header('Content-Type', ctype)
                self.send_header('Accept-Ranges', 'bytes')
                self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                self.send_header('Content-Length', str(length))
                self.end_headers()
                
                f.seek(start)
                self.copyfile_range = length
                return f
            except Exception as e:
                pass

        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self.copyfile_range = None
        return f

    def copyfile(self, source, outputfile):
        """ Кастомный copyfile, который пишет только запрошенный Range байт """
        if hasattr(self, 'copyfile_range') and self.copyfile_range is not None:
            left = self.copyfile_range
            while left > 0:
                buf = source.read(min(left, 65536))
                if not buf:
                    break
                try:
                    outputfile.write(buf)
                except Exception:
                    # Сокет закрыт пользователем
                    break
                left -= len(buf)
        else:
            super().copyfile(source, outputfile)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
            return
            
        elif self.path == '/api/videos':
            files_data = []
            ratings = load_ratings()
            metadata_cache = load_video_metadata()
            metadata_dirty = False
            
            if os.path.exists(VIDEO_DIR):
                valid_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                files = [f for f in os.listdir(VIDEO_DIR) if f.lower().endswith(valid_exts)]
                
                for i, f in enumerate(files):
                    full_path = os.path.join(VIDEO_DIR, f)
                    size_mb = round(os.path.getsize(full_path) / (1024 * 1024), 2)
                    display_name = os.path.splitext(f)[0]
                    
                    if f not in metadata_cache:
                        orientation = get_video_orientation(full_path)
                        metadata_cache[f] = {"orientation": orientation}
                        metadata_dirty = True
                    else:
                        orientation = metadata_cache[f].get("orientation", "horizontal")
                    
                    files_data.append({
                        "id": i,
                        "filename": f,
                        "name": display_name,
                        "filepath": f"video/{f}",
                        "size": size_mb,
                        "rating": ratings.get(f, 0),
                        "orientation": orientation
                    })
            if metadata_dirty:
                save_video_metadata(metadata_cache)
                
            files_data.sort(key=lambda x: x["name"].lower())
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps(files_data).encode('utf-8'))
            return

        # Иначе используем стандартный обработчик (для стриминга видеофайлов)
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
                
                metadata_cache = load_video_metadata()
                meta_dirty = False
                
                for f in files_to_delete:
                    if "/" not in f and "\\" not in f:
                        file_path = os.path.join(VIDEO_DIR, f)
                        if os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                delete_rating(f)
                                if f in metadata_cache:
                                    del metadata_cache[f]
                                    meta_dirty = True
                                deleted_count += 1
                                print(f"🗑️ Удалено: {f}")
                            except Exception as e:
                                pass
                                
                if meta_dirty:
                    save_video_metadata(metadata_cache)
                
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
                if filename and score is not None:
                    save_rating(filename, score)
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "ok", "rating": score}).encode('utf-8'))
                    return
                self.send_response(400)
                self.end_headers()
                return

            elif self.path == '/api/rename':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data.decode('utf-8'))
                
                original = data.get('original')
                new_name = data.get('newName')
                
                if original and new_name:
                    if "/" not in original and "\\" not in original and "/" not in new_name and "\\" not in new_name:
                        old_path = os.path.join(VIDEO_DIR, original)
                        ext = os.path.splitext(original)[1]
                        new_filename = f"{new_name}{ext}"
                        new_path = os.path.join(VIDEO_DIR, new_filename)
                        
                        if original == new_filename:
                            self.send_response(200)
                            self.end_headers()
                            self.wfile.write(b'{"status":"ok"}')
                            return
                        
                        if os.path.exists(old_path) and not os.path.exists(new_path):
                            try:
                                os.rename(old_path, new_path)
                                # Обновляем ключ в рейтингах
                                ratings = load_ratings()
                                if original in ratings:
                                    score = ratings[original]
                                    del ratings[original]
                                    ratings[new_filename] = score
                                    os.makedirs(os.path.dirname(RATINGS_FILE), exist_ok=True)
                                    with open(RATINGS_FILE, "w", encoding="utf-8") as f:
                                        json.dump(ratings, f, indent=4, ensure_ascii=False)
                                
                                # Обновляем ключ в метаданных
                                metadata_cache = load_video_metadata()
                                if original in metadata_cache:
                                    meta = metadata_cache[original]
                                    del metadata_cache[original]
                                    metadata_cache[new_filename] = meta
                                    save_video_metadata(metadata_cache)
                                    
                                self.send_response(200)
                                self.send_header('Content-type', 'application/json')
                                self.end_headers()
                                self.wfile.write(json.dumps({"status": "ok", "new_filename": new_filename}).encode('utf-8'))
                                return
                            except Exception as e:
                                self.send_response(500)
                                self.end_headers()
                                self.wfile.write(str(e).encode('utf-8'))
                                return
                        else:
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write("Файл не найден или имя уже занято".encode('utf-8'))
                            return
                            
                self.send_response(400)
                self.end_headers()
                return

        except Exception as e:
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode('utf-8'))

def run_server():
    server_address = ('', PORT)
    import socket
    class ReusableTCPServer(HTTPServer):
        allow_reuse_address = True

    httpd = ReusableTCPServer(server_address, VideoDashboardHandler)
    print(f"\n🎬 Video Gallery Dashboard v2 запущен!")
    print(f"📁 Папка с видео: {VIDEO_DIR}")
    print(f"🚀 HTTP 206 Range (Плеер) и FFprobe сканирование активированы.")
    print(f"🔗 Открой в браузере: http://localhost:{PORT}")
    print(f"🛑 Для остановки нажми Ctrl+C\n")
    httpd.serve_forever()

if __name__ == '__main__':
    threading.Timer(1.0, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    try:
        run_server()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
