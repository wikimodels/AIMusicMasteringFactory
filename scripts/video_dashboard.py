"""
🎬 Video Dashboard — Галерея исходных видео
═══════════════════════════════════════════════════════
Nazwanie:
    Браузер исходных видео-футажей для отбора материала.
    Позволяет просмотреть, оценить и отобрать нужные видео перед отправкой
    в обрабатывающий pipeline.

Читает видео из:   VIDEO_DIR (см. ниже) — ваша папка с сырьём
Порт:              http://localhost:8890

Возможности:
    - Просмотр видео встроенным плеером прямо в браузере
    - Автоопределение ориентации (вертикальное / горизонтальное) через ffprobe
    - Разделение видео па секциям: вертикальные / горизонтальные
    - Рейтинг файлов (1–5 цветных точек), переименование в UI
    - Пакетное удаление выбранных файлов
    - Кнопка "Копировать в video_input" — отправляет отобранные в pipeline
    - Подпапки (проекты) в сайдбаре слева

НАСТРОЙКА:
    VIDEO_DIR — измени на свою папку с сырым видео-футажем.
    COPY_TARGET_VERTICAL / COPY_TARGET_HORIZONTAL — куда копируются
    выбранные видео по ориентации.

Запуск: poetry run python scripts/video_dashboard.py
"""

import os
import json
import subprocess
import threading
import webbrowser
import shutil
import traceback
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

# --- CONFIGURATION ---
# Измени VIDEO_DIR на папку своего сырого видео-футажа (не video_input проекта!)
VIDEO_DIR = "G:/VideoFootage"
PORT = 8890
# Куда копируются видео по кнопке "Копировать в video_input" (по ориентации)
COPY_TARGET_VERTICAL   = r"D:\GitHub\AIMusicMasteringFactory\video\video_input_vertical"
COPY_TARGET_HORIZONTAL = r"D:\GitHub\AIMusicMasteringFactory\video\video_input_horizontal"
COPY_TARGET_REMOVE_SOUND = r"D:\GitHub\AIMusicMasteringFactory\video\video_with_sound"
RATINGS_FILE = os.path.join(VIDEO_DIR, "video_ratings.json")
METADATA_FILE = os.path.join(VIDEO_DIR, "video_metadata.json")

def load_ratings():
    if os.path.exists(RATINGS_FILE):
        try:
            with open(RATINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
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
        with open(RATINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(ratings, f, indent=4, ensure_ascii=False)

def load_video_metadata():
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_video_metadata(metadata):
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4, ensure_ascii=False)

def get_video_orientation(filepath):
    # Убеждаемся, что путь корректен для Windows (ffprobe может капризничать)
    clean_path = os.path.normpath(filepath)
    try:
        cmd = ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', clean_path]
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5).decode('utf-8').strip()
        dims = result.split('x')
        if len(dims) == 2:
            w, h = int(dims[0]), int(dims[1])
            return "vertical" if w < h else "horizontal"
    except Exception as e:
        print(f"[ERROR] ffprobe error on {clean_path}: {e}")
    return None

os.makedirs(VIDEO_DIR, exist_ok=True)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Gallery Dashboard v2</title>
    <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">
    <style>
        :root {
            --primary: #1DB954;
            --primary-variant: #1ed760;
            --secondary: #b3b3b3;
            --background: #000000;
            --surface: #121212;
            --surface-hover: #282828;
            --error: #e91429;
            --text-primary: #ffffff;
            --text-secondary: #b3b3b3;
            --amber: #FFBF00;
        }

        body {
            font-family: 'Roboto', sans-serif;
            background-color: var(--background);
            color: var(--text-primary);
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
            overflow: hidden;
        }

        /* LAYOUT */
        .header {
            background-color: rgba(0,0,0,0.85);
            backdrop-filter: blur(10px);
            padding: 12px 32px;
            border-bottom: 1px solid #282828;
            z-index: 1000;
            flex-shrink: 0;
        }

        .header-content {
            display: flex;
            align-items: center;
            justify-content: space-between;
            max-width: 100%;
            gap: 40px;
        }

        .main-layout {
            display: flex;
            flex: 1;
            overflow: hidden;
        }

        .sidebar {
            width: 260px;
            background-color: #000000;
            border-right: 1px solid #282828;
            display: flex;
            flex-direction: column;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            overflow-y: auto;
            flex-shrink: 0;
        }

        .sidebar.hidden {
            width: 0;
            opacity: 0;
            pointer-events: none;
        }

        .container {
            flex: 1;
            padding: 24px;
            overflow-y: auto;
            background-color: var(--background);
            box-sizing: border-box;
        }

        /* NAVBAR ELEMENTS */
        h1 { margin: 0; font-size: 18px; font-weight: 700; display: flex; align-items: center; gap: 8px; white-space: nowrap;}
        
        .sidebar-toggle {
            background: transparent; border: none; color: white; cursor: pointer;
            padding: 8px; border-radius: 50%; display: flex; align-items: center; transition: 0.2s;
            margin-right: 12px;
        }
        .sidebar-toggle:hover { background: rgba(255,255,255,0.1); }

        .search-box {
            background: rgba(255,255,255,0.1); border-radius: 20px; padding: 6px 16px;
            display: flex; align-items: center; gap: 8px; width: 300px; margin: 0 40px;
        }
        .search-input { background: transparent; border: none; color: white; outline: none; width: 100%; font-size: 14px; }
        .search-clear { cursor: pointer; color: #888; font-size: 18px !important; }

        .header-stats { display: flex; gap: 40px; font-size: 13px; color: var(--text-secondary); }
        .stat-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; }

        .btn {
            border: none; border-radius: 18px; padding: 0 16px; height: 32px; font-size: 11px; font-weight: 700;
            cursor: pointer; display: flex; align-items: center; gap: 8px; transition: all 0.2s;
            text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
        }
        .btn-save { background-color: var(--primary); color: black; }
        .btn-save:hover { background-color: var(--primary-variant); transform: scale(1.02); }
        .btn-error { background-color: transparent; color: var(--error); border: 1px solid var(--error); }
        .btn-error:hover { background-color: var(--error); color: white; }
        .btn-error:disabled { opacity: 0.3; cursor: default; border-color: #333; color: #555; }
        .btn-move { background-color: var(--amber); color: black; }
        .btn-move:disabled { opacity: 0.3; cursor: default; }
        .btn-nosound { background-color: #33b5e5; color: black; }
        .btn-nosound:disabled { opacity: 0.3; cursor: default; }

        /* SIDEBAR ITEMS */
        .sidebar-header { padding: 24px 16px 12px; font-size: 12px; font-weight: 700; color: #888; text-transform: uppercase; }
        .folder-item { 
            padding: 12px 16px; display: flex; align-items: center; gap: 12px; cursor: pointer;
            color: var(--text-secondary); transition: 0.2s; font-size: 14px;
        }
        .folder-item:hover { background: var(--surface-hover); color: white; }
        .folder-item.active { background: rgba(29, 185, 84, 0.1); color: var(--primary); }

        /* GRID */
        .track-list {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 24px;
            width: 100%;
        }

        .track-card {
            background-color: var(--surface);
            padding: 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .track-card:hover { background-color: var(--surface-hover); transform: translateY(-4px); }

        video { 
            width: 100%; border-radius: 6px; background: #000; 
            max-height: 400px; object-fit: contain;
        }

        .track-checkbox {
            position: absolute;
            top: 26px;
            left: 26px;
            width: 20px;
            height: 20px;
            cursor: pointer;
            z-index: 10;
            accent-color: var(--primary);
            box-shadow: 0 0 10px rgba(0,0,0,0.8);
            border-radius: 4px;
            transition: transform 0.2s;
        }
        .track-checkbox:hover {
            transform: scale(1.1);
        }

        .track-info { margin-top: 12px; }
        .track-name-input {
            width: 100%; background: transparent; border: none; border-bottom: 1px solid transparent;
            color: white; font-size: 15px; font-weight: 600; padding: 4px 0; margin-bottom: 8px;
            outline: none;
        }
        .track-name-input:focus { border-bottom-color: var(--primary); }
        .track-name-input.changed { color: var(--amber); }

        .track-meta { display: flex; justify-content: space-between; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }

        /* RATING */
        .rating-bar { display: flex; gap: 4px; }
        .rating-dot { 
            width: 12px; height: 12px; border-radius: 50%; cursor: pointer;
            border: 1px solid #444; transition: 0.2s;
        }
        .dot-1 { background-color: #ff4444; } .dot-2 { background-color: #ffbb33; } 
        .dot-3 { background-color: #00C851; } .dot-4 { background-color: #33b5e5; } .dot-5 { background-color: #aa66cc; }
        .rating-dot:not(.active) { opacity: 0.2; }
        .rating-dot.active { transform: scale(1.2); box-shadow: 0 0 8px currentColor; }

        .section-title { font-size: 14px; color: var(--primary); border-bottom: 1px solid #222; padding-bottom: 4px; margin: 12px 0 16px; display: none; align-items: center; gap: 8px; }
        .chip { background: rgba(255,255,255,0.05); padding: 4px 12px; border-radius: 16px; font-size: 12px; color: var(--text-secondary); display: flex; align-items: center; gap: 6px; border: 1px solid #333;}
        .chip b { color: var(--primary); }
        
        .action-bar {
            position: sticky;
            top: -24px;
            background: rgba(0,0,0,0.8);
            backdrop-filter: blur(20px);
            padding: 16px 4px;
            margin-bottom: 32px;
            z-index: 100;
            display: flex;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
            border-bottom: 1px solid #1a1a1a;
        }

        /* STATUS */
        #status { font-size: 13px; color: #33b5e5; font-weight: 500; margin-left: 40px; }
        .empty-state { text-align: center; padding: 80px 0; color: #555; }
        .empty-state .material-icons { font-size: 80px; margin-bottom: 16px; }

        /* CUSTOM SCROLLBAR */
        ::-webkit-scrollbar { width: 10px; }
        ::-webkit-scrollbar-track { background: #121212; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 5px; }
        ::-webkit-scrollbar-thumb:hover { background: #444; }
    </style>
</head>
<body>

    <div class="header">
        <div class="header-content">
            <div style="display: flex; align-items: center;">
                <button class="sidebar-toggle" onclick="toggleSidebar()">
                    <span class="material-icons">menu</span>
                </button>
                <h1><span class="material-icons">movie</span> Video Gallery</h1>
            </div>

            <div class="search-box">
                <span class="material-icons" style="font-size: 20px; color: #888;">search</span>
                <input type="text" id="searchInput" class="search-input" placeholder="Поиск видео..." oninput="handleSearch()">
                <span class="material-icons search-clear" id="searchClear" onclick="clearSearch()" style="display:none">close</span>
            </div>

            <div class="header-stats">
                <span>Total: <b id="stat_total">0</b></span>
                <span><span class="stat-dot dot-1"></span> <b id="stat_1">0</b></span>
                <span><span class="stat-dot dot-2"></span> <b id="stat_2">0</b></span>
                <span><span class="stat-dot dot-3"></span> <b id="stat_3">0</b></span>
                <span><span class="stat-dot dot-4"></span> <b id="stat_4">0</b></span>
                <span><span class="stat-dot dot-5"></span> <b id="stat_5">0</b></span>
            </div>

            <div style="display: flex; align-items: center; gap: 32px;">
                <div id="status">Ready</div>
                <button id="deleteBtn" class="btn btn-error" onclick="deleteBatch()" disabled>
                    <span class="material-icons">delete</span> (<span id="selCountDirect">0</span>)
                </button>
                <button class="btn btn-save" onclick="saveAllChanges()">
                    <span class="material-icons">save</span> Сохранить изменения
                </button>
            </div>
        </div>
    </div>

    <div class="main-layout">
        <div class="sidebar" id="sidebar">
            <div class="sidebar-header">Проекты</div>
            <div id="folderList"></div>
        </div>

        <div class="container" id="mainContainer">
            <div class="action-bar">
                <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 13px; font-weight: 500; white-space: nowrap; background: rgba(255,255,255,0.05); padding: 6px 14px; border-radius: 18px; border: 1px solid #333; transition: 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">
                    <input type="checkbox" id="selectAll" style="width: 18px; height: 18px; cursor: pointer; accent-color: var(--primary);">
                    ВЫДЕЛИТЬ ВСЕ
                </label>

                <button id="removeSoundBtn" class="btn btn-nosound" onclick="removeSoundBatch()" disabled>
                    <span class="material-icons" style="font-size: 18px;">volume_off</span> REMOVE SOUND
                </button>

                <div id="vertChip" class="chip" style="display:none">
                    <span class="material-icons" style="font-size: 16px; color: var(--primary);">crop_portrait</span> ВЕРТИКАЛЬНЫЕ: <b id="count_vert">0</b>
                </div>

                <div id="horizChip" class="chip" style="display:none">
                    <span class="material-icons" style="font-size: 16px; color: var(--primary);">crop_landscape</span> ГОРИЗОНТАЛЬНЫЕ: <b id="count_horiz">0</b>
                </div>
            </div>

            <div id="emptyState" class="empty-state" style="display:none">
                <span class="material-icons">video_library</span>
                <h2>Нет видео</h2>
                <p>В этой папке пока пусто</p>
            </div>

            <div id="verticalSection" style="display:none">
                <div class="section-title"><span class="material-icons">crop_portrait</span> Вертикальные (<span id="count_vert">0</span>)</div>
                <div class="track-list" id="verticalList"></div>
            </div>

            <div id="horizontalSection" style="display:none">
                <div class="section-title"><span class="material-icons">crop_landscape</span> Горизонтальные (<span id="count_horiz">0</span>)</div>
                <div class="track-list" id="horizontalList"></div>
            </div>
        </div>
    </div>

    <script>
        const statusEl = document.getElementById('status');
        let tracks = [];
        let folders = [];
        let currentFolder = "";
        let searchQuery = "";

        // UI Persistence
        if (localStorage.getItem('sidebarHidden') === 'true') {
            document.getElementById('sidebar').classList.add('hidden');
        }

        function toggleSidebar() {
            const el = document.getElementById('sidebar');
            el.classList.toggle('hidden');
            localStorage.setItem('sidebarHidden', el.classList.contains('hidden'));
        }

        async function loadTracks(folder = "") {
            try {
                currentFolder = folder;
                showStatus('Загрузка...', '#1DB954', 0);
                const url = folder ? `/api/videos?folder=${encodeURIComponent(folder)}` : '/api/videos';
                const res = await fetch(url);
                const data = await res.json();
                
                tracks = data.files;
                folders = data.folders;
                
                renderFolders();
                renderTracks();
                updateStats();
                showStatus('Ready');

                document.getElementById('selectAll').checked = false;
                updateSelection();
            } catch (err) {
                console.error(err);
                showStatus('Ошибка загрузки', '#e91429', 0);
            }
        }

        function renderFolders() {
            const list = document.getElementById('folderList');
            let html = `<div class="folder-item ${currentFolder === '' ? 'active' : ''}" onclick="loadTracks('')">
                <span class="material-icons">home</span> Все видео (Root)
            </div>`;
            
            folders.forEach(f => {
                html += `<div class="folder-item ${currentFolder === f ? 'active' : ''}" onclick="loadTracks('${f}')">
                    <span class="material-icons">folder</span> ${f}
                </div>`;
            });
            list.innerHTML = html;
        }

        function renderTracks() {
            const vertList = document.getElementById('verticalList');
            const horizList = document.getElementById('horizontalList');
            const empty = document.getElementById('emptyState');
            
            vertList.innerHTML = '';
            horizList.innerHTML = '';
            
            const filtered = tracks.filter(t => t.name.toLowerCase().includes(searchQuery));
            
            if (filtered.length === 0) {
                empty.style.display = 'block';
                document.getElementById('verticalSection').style.display = 'none';
                document.getElementById('horizontalSection').style.display = 'none';
                return;
            }

            empty.style.display = 'none';
            let vCount = 0, hCount = 0;

            filtered.forEach(t => {
                const card = createTrackCard(t);
                if (t.orientation === 'vertical') {
                    vertList.appendChild(card);
                    vCount++;
                } else {
                    horizList.appendChild(card);
                    hCount++;
                }
            });

            document.getElementById('verticalSection').style.display = vCount > 0 ? 'block' : 'none';
            document.getElementById('horizontalSection').style.display = hCount > 0 ? 'block' : 'none';
            document.getElementById('vertChip').style.display = vCount > 0 ? 'flex' : 'none';
            document.getElementById('horizChip').style.display = hCount > 0 ? 'flex' : 'none';
            document.getElementById('count_vert').textContent = vCount;
            document.getElementById('count_horiz').textContent = hCount;
        }

        function createTrackCard(t) {
            const div = document.createElement('div');
            div.className = 'track-card';
            div.innerHTML = `
                <input type="checkbox" class="track-checkbox" data-filename="${t.filename}" onchange="updateSelection()">
                <video src="${t.filepath}" controls preload="metadata"></video>
                <div class="track-info">
                    <input type="text" class="track-name-input" value="${t.name}" 
                           data-original-filename="${t.filename}" 
                           oninput="this.classList.add('changed')">
                    <div class="track-meta">
                        <span>${t.size} MB</span>
                        <span>${t.orientation}</span>
                    </div>
                    <div class="rating-bar" data-filename="${t.filename}">
                        ${[1,2,3,4,5].map(s => `
                            <div class="rating-dot dot-${s} ${t.rating >= s ? 'active' : ''}" 
                                 onclick="rateTrack('${t.filename}', ${s})"></div>
                        `).join('')}
                    </div>
                </div>
            `;
            return div;
        }

        async function rateTrack(filename, score) {
            try {
                const res = await fetch('/api/rate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({filename, score})
                });
                if (res.ok) {
                    const t = tracks.find(x => x.filename === filename);
                    if (t) t.rating = score;
                    renderTracks();
                    updateStats();
                }
            } catch (err) { console.error(err); }
        }

        async function saveAllChanges() {
            const inputs = document.querySelectorAll('.track-name-input.changed');
            if (inputs.length === 0) {
                showStatus('Нет изменений для сохранения');
                return;
            }
            showStatus('Сохранение...', '#1DB954', 0);
            let errors = 0;
            for (let input of inputs) {
                try {
                    const res = await fetch('/api/rename', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            original: input.dataset.originalFilename,
                            newName: input.value.trim()
                        })
                    });
                    if (!res.ok) errors++;
                } catch { errors++; }
            }
            if (errors > 0) showStatus(`Ошибки при сохранении: ${errors}`, '#e91429');
            else {
                showStatus('Все сохранено! ✅');
                loadTracks(currentFolder);
            }
        }

        async function deleteBatch() {
            const checked = Array.from(document.querySelectorAll('.track-checkbox:checked')).map(c => c.dataset.filename);
            if (checked.length === 0 || !confirm(`Удалить ${checked.length} файлов?`)) return;
            
            showStatus('Удаление...', '#e91429', 0);
            try {
                const res = await fetch('/api/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({files: checked})
                });
                if (res.ok) {
                    showStatus('Удалено');
                    loadTracks(currentFolder);
                }
            } catch (err) { showStatus('Ошибка сети', '#e91429'); }
        }

        async function copyBatch() {
            const checked = Array.from(document.querySelectorAll('.track-checkbox:checked')).map(c => c.dataset.filename);
            if (checked.length === 0) return;
            
            showStatus('Копирование...', '#FFBF00', 0);
            try {
                const res = await fetch('/api/copy', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({files: checked})
                });
                if (res.ok) {
                    showStatus('Скопировано в video_input ✅', '#1DB954');
                    document.querySelectorAll('.track-checkbox:checked').forEach(c => c.checked = false);
                    updateSelection();
                }
            } catch (err) { showStatus('Ошибка сети', '#e91429'); }
        }

        function updateSelection() {
            const chks = document.querySelectorAll('.track-checkbox');
            const checked = document.querySelectorAll('.track-checkbox:checked');
            const count = checked.length;
            
            if (document.getElementById('selCountDirect')) {
                document.getElementById('selCountDirect').textContent = count;
            }
            
            document.getElementById('deleteBtn').disabled = count === 0;
            document.getElementById('removeSoundBtn').disabled = count === 0;
            
            if (chks.length > 0) {
                document.getElementById('selectAll').checked = count === chks.length;
                document.getElementById('selectAll').indeterminate = count > 0 && count < chks.length;
            }
        }

        async function removeSoundBatch() {
            const checked = Array.from(document.querySelectorAll('.track-checkbox:checked')).map(c => c.dataset.filename);
            if (checked.length === 0) return;
            
            showStatus('Копирование...', '#33b5e5', 0);
            try {
                const res = await fetch('/api/remove_sound', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({files: checked})
                });
                if (res.ok) {
                    showStatus('Скопировано в video_with_sound ✅', '#1DB954');
                    document.querySelectorAll('.track-checkbox:checked').forEach(c => c.checked = false);
                    updateSelection();
                }
            } catch (err) { showStatus('Ошибка сети', '#e91429'); }
        }

        document.getElementById('selectAll').addEventListener('change', (e) => {
            document.querySelectorAll('.track-checkbox').forEach(c => c.checked = e.target.checked);
            updateSelection();
        });

        function handleSearch() {
            searchQuery = document.getElementById('searchInput').value.toLowerCase().trim();
            document.getElementById('searchClear').style.display = searchQuery ? 'block' : 'none';
            renderTracks();
        }

        function clearSearch() {
            document.getElementById('searchInput').value = "";
            handleSearch();
        }

        function updateStats() {
            document.getElementById('stat_total').textContent = tracks.length;
            const c = {1:0, 2:0, 3:0, 4:0, 5:0};
            tracks.forEach(t => { if(t.rating) c[t.rating]++; });
            for(let i=1; i<=5; i++) document.getElementById(`stat_${i}`).textContent = c[i];
        }

        function showStatus(text, color="#b3b3b3", timeout=3000) {
            statusEl.textContent = text;
            statusEl.style.color = color;
            
            // Если статус "Ready", скрываем его, чтобы не мешал
            statusEl.style.opacity = (text === 'Ready') ? '0' : '1';
            
            if (timeout && text !== 'Ready') {
                // Для финальных сообщений показываем только alert
                // А в статус-баре сразу сбрасываем в Ready (который теперь скрыт)
                let title = "🔔 VIDEO DASHBOARD";
                if (color === '#1DB954' || color.includes('primary')) title = "✅ SUCCESS";
                if (color === '#e91429' || color.includes('error')) title = "❌ ERROR";
                
                const formattedMsg = `${title}\n\n➤ ${text}`;
                
                setTimeout(() => { alert(formattedMsg); }, 100);

                setTimeout(() => { 
                    statusEl.textContent = 'Ready'; 
                    statusEl.style.color = "#b3b3b3"; 
                    statusEl.style.opacity = '0';
                }, 100); // Сбрасываем быстро, так как есть алерт
            }
        }

        // Initial Load
        loadTracks();
    </script>
</body>
</html>
"""

class VideoDashboardHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass

    def translate_path(self, path):
        up = unquote(path)
        if up.startswith('/video/'):
            return os.path.join(VIDEO_DIR, up[len('/video/'):])
        return super().translate_path(path)

    def send_head(self):
        path = self.translate_path(self.path)
        if os.path.isdir(path): return super().send_head()
        
        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno()).st_size
        if 'Range' in self.headers:
            try:
                r = self.headers['Range'].replace('bytes=', '').split('-')
                start = int(r[0]) if r[0] else 0
                end = int(r[1]) if r[1] else fs - 1
                length = end - start + 1
                self.send_response(206)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Range', f'bytes {start}-{end}/{fs}')
                self.send_header('Content-Length', str(length))
                self.end_headers()
                f.seek(start)
                self.copyfile_range = length
                return f
            except: pass
        
        self.send_response(200)
        self.send_header("Content-type", ctype)
        self.send_header("Content-Length", str(fs))
        self.end_headers()
        self.copyfile_range = None
        return f

    def copyfile(self, source, outputfile):
        if hasattr(self, 'copyfile_range') and self.copyfile_range:
            left = self.copyfile_range
            while left > 0:
                buf = source.read(min(left, 65536))
                if not buf: break
                outputfile.write(buf)
                left -= len(buf)
        else: super().copyfile(source, outputfile)

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode('utf-8'))
        elif self.path.startswith('/api/videos'):
            q = parse_qs(urlparse(self.path).query)
            folder = q.get('folder', [''])[0].strip('/\\').replace('..', '')
            target = os.path.join(VIDEO_DIR, folder)
            
            files_data = []
            folders = []
            ratings = load_ratings()
            metadata = load_video_metadata()
            dirty = False

            if os.path.exists(VIDEO_DIR):
                for e in os.scandir(VIDEO_DIR):
                    if e.is_dir() and not e.name.startswith('.'): folders.append(e.name)
            folders.sort(key=lambda x: x.lower())

            if os.path.exists(target):
                raw_files = [f for f in os.listdir(target) if f.lower().endswith(('.mp4', '.mov', '.avi', '.webm'))]
                ff_limit = 500
                ff_done = 0
                for f in raw_files:
                    rel = os.path.join(folder, f).replace('\\', '/')
                    full = os.path.join(target, f)
                    if rel not in metadata and ff_done < ff_limit:
                        orient = get_video_orientation(full)
                        if orient:
                            metadata[rel] = {"orientation": orient}
                            dirty = True
                            ff_done += 1
                    
                    files_data.append({
                        "filename": rel,
                        "name": os.path.splitext(f)[0],
                        "filepath": f"video/{rel}",
                        "size": round(os.path.getsize(full)/1048576, 2),
                        "rating": ratings.get(rel, 0),
                        "orientation": metadata.get(rel, {}).get("orientation", "horizontal")
                    })
            if dirty: save_video_metadata(metadata)
            files_data.sort(key=lambda x: x["name"].lower())
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"files": files_data, "folders": folders}).encode('utf-8'))
        else: super().do_GET()

    def do_POST(self):
        content_len = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(content_len).decode('utf-8'))
        
        if self.path == '/api/rate':
            save_rating(data['filename'], data['score'])
            res = {"status": "ok"}
        elif self.path == '/api/delete':
            for f in data.get('files', []):
                p = os.path.join(VIDEO_DIR, f.replace('..',''))
                if os.path.exists(p): os.remove(p); delete_rating(f)
            res = {"status": "ok"}
        elif self.path == '/api/copy':
            for f in data.get('files', []):
                p = os.path.join(VIDEO_DIR, f.replace('..',''))
                if os.path.exists(p):
                    # Определяем папку назначения по ориентации файла
                    orientation = metadata.get(f, {}).get("orientation") if isinstance(metadata, dict) else None
                    if orientation is None:
                        orientation = get_video_orientation(p)
                    if orientation == "vertical":
                        dest_dir = COPY_TARGET_VERTICAL
                    else:
                        dest_dir = COPY_TARGET_HORIZONTAL
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(p, os.path.join(dest_dir, os.path.basename(p)))
            res = {"status": "ok"}
        elif self.path == '/api/remove_sound':
            for f in data.get('files', []):
                p = os.path.join(VIDEO_DIR, f.replace('..',''))
                if os.path.exists(p):
                    dest_dir = COPY_TARGET_REMOVE_SOUND
                    os.makedirs(dest_dir, exist_ok=True)
                    shutil.copy2(p, os.path.join(dest_dir, os.path.basename(p)))
            res = {"status": "ok"}
        elif self.path == '/api/rename':
            old_rel = data['original'].replace('..', '')
            new_name = data['newName'].replace('..', '').replace('/','').replace('\\','')
            old_p = os.path.join(VIDEO_DIR, old_rel)
            folder = os.path.dirname(old_rel)
            ext = os.path.splitext(old_rel)[1]
            new_rel = os.path.join(folder, f"{new_name}{ext}").replace('\\', '/')
            new_p = os.path.join(VIDEO_DIR, new_rel)
            
            if os.path.exists(old_p) and not os.path.exists(new_p):
                os.rename(old_p, new_p)
                r = load_ratings()
                if old_rel in r: r[new_rel] = r.pop(old_rel)
                with open(RATINGS_FILE, "w", encoding="utf-8") as f: json.dump(r, f, indent=4, ensure_ascii=False)
                m = load_video_metadata()
                if old_rel in m: m[new_rel] = m.pop(old_rel); save_video_metadata(m)
                res = {"status": "ok"}
            else: res = {"status": "error"}
        else: self.send_error(404); return

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(res).encode('utf-8'))

if __name__ == '__main__':
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{PORT}')).start()
    HTTPServer(('', PORT), VideoDashboardHandler).serve_forever()
