# -*- coding: utf-8 -*-
"""
Music Sorting Studio - Flask Server
====================================
Requirements: pip install flask
Run: python server.py
Open: http://localhost:5000
"""

import sys
import os
import shutil
import subprocess
import json

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, jsonify, request, send_from_directory
from tinytag import TinyTag

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=BASE_DIR)

SETTINGS_FILE = os.path.join(BASE_DIR, 'settings.json')
settings = {
    'albums': [],
    'active_album': ''
}

def load_settings():
    global settings
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except Exception:
            pass

def save_settings():
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

load_settings()

def get_folders():
    active = settings.get('active_album')
    if not active or not os.path.exists(active):
        return None
    
    sorting_data = os.path.join(active, 'sorting_data')
    folders = {
        'origin': os.path.join(sorting_data, 'origin'),
        'redo':   os.path.join(sorting_data, 'redo'),
        'liked':  os.path.join(sorting_data, 'liked'),
        'disliked': os.path.join(sorting_data, 'disliked'),
        'cuts':   os.path.join(sorting_data, 'cuts'),
    }
    # Ensure all folders exist
    for p in folders.values():
        os.makedirs(p, exist_ok=True)
    return folders


def get_tracks(folder_name):
    folders = get_folders()
    if not folders:
        return []
    folder_path = folders[folder_name]
    files = [f for f in os.listdir(folder_path) if f.lower().endswith(('.mp3', '.wav'))]
    files.sort()
    
    result = []
    for f in files:
        file_path = os.path.join(folder_path, f)
        duration = 0
        try:
            tag = TinyTag.get(file_path)
            if tag.duration:
                duration = tag.duration
        except Exception:
            pass
        result.append({"name": f, "duration": duration})
        
    return result


@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/api/settings', methods=['GET'])
def api_settings_get():
    return jsonify(settings)

@app.route('/api/settings', methods=['POST'])
def api_settings_post():
    data = request.json or {}
    action = data.get('action')
    
    if action == 'add_album':
        path = data.get('path', '').strip()
        if not path or not os.path.isabs(path) or not os.path.exists(path):
            return jsonify({'error': 'Invalid or non-existent absolute path'}), 400
        if path not in settings['albums']:
            settings['albums'].append(path)
        settings['active_album'] = path
        save_settings()
        return jsonify(settings)
        
    elif action == 'set_album':
        path = data.get('path', '').strip()
        if path in settings['albums']:
            settings['active_album'] = path
            save_settings()
            return jsonify(settings)
        return jsonify({'error': 'Album not found in list'}), 400
        
    return jsonify({'error': 'Invalid action'}), 400


@app.route('/api/tracks')
def api_tracks():
    folders = get_folders()
    if not folders:
        # Return empty lists if no active album
        return jsonify({k: [] for k in ['origin', 'redo', 'liked', 'disliked', 'cuts']})
    result = {folder: get_tracks(folder) for folder in folders}
    return jsonify(result)


@app.route('/audio/<folder>/<path:filename>')
def serve_audio(folder, filename):
    folders = get_folders()
    if not folders or folder not in folders:
        return jsonify({'error': 'Invalid folder or no album selected'}), 404
    
    response = send_from_directory(folders[folder], filename)
    response.headers['Accept-Ranges'] = 'bytes'
    return response


@app.route('/api/move', methods=['POST'])
def api_move():
    folders = get_folders()
    if not folders:
        return jsonify({'error': 'No album selected'}), 400

    data = request.json or {}
    filename    = data.get('filename')
    from_folder = data.get('from')
    to_folder   = data.get('to')

    if not filename or from_folder not in folders or to_folder not in folders:
        return jsonify({'error': 'Invalid parameters'}), 400

    src = os.path.join(folders[from_folder], filename)
    if not os.path.exists(src):
        return jsonify({'error': 'Source file not found'}), 404

    dst = os.path.join(folders[to_folder], filename)

    # Resolve name conflicts
    if os.path.exists(dst) and os.path.abspath(src) != os.path.abspath(dst):
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(folders[to_folder], f"{base}_{counter}{ext}")
            counter += 1

    shutil.move(src, dst)
    return jsonify({'success': True, 'new_filename': os.path.basename(dst)})


ALLOWED_EXTENSIONS = {'.mp3', '.wav'}

@app.route('/api/upload', methods=['POST'])
def api_upload():
    folders = get_folders()
    if not folders:
        return jsonify({'error': 'No album selected'}), 400

    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400

    uploaded = request.files.getlist('files')
    results = []

    for f in uploaded:
        if not f or not f.filename:
            continue

        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            results.append({'filename': f.filename, 'success': False, 'error': 'Not allowed extension'})
            continue

        dest_name = f.filename
        dest_path = os.path.join(folders['origin'], dest_name)

        # Resolve name conflicts
        if os.path.exists(dest_path):
            base, extension = os.path.splitext(dest_name)
            counter = 1
            while os.path.exists(dest_path):
                dest_name = f'{base}_{counter}{extension}'
                dest_path = os.path.join(folders['origin'], dest_name)
                counter += 1

        f.save(dest_path)
        results.append({'filename': dest_name, 'success': True})

    return jsonify({'results': results})


@app.route('/api/rename', methods=['POST'])
def api_rename():
    folders = get_folders()
    if not folders:
        return jsonify({'error': 'No album selected'}), 400

    data        = request.json or {}
    old_name    = data.get('old_name')
    new_name    = data.get('new_name', '').strip()
    folder      = data.get('folder')

    if not old_name or not new_name or folder not in folders:
        return jsonify({'error': 'Invalid parameters'}), 400

    # Security: strip path separators and dots that escape the folder
    new_name = os.path.basename(new_name)
    if not new_name:
        return jsonify({'error': 'Empty name'}), 400

    # Preserve extension from original file
    _, orig_ext = os.path.splitext(old_name)
    base_new, new_ext = os.path.splitext(new_name)

    # If user didn't type an extension, keep the original one
    if not new_ext:
        new_name = base_new + orig_ext
    else:
        # Only allow safe audio extensions
        if new_ext.lower() not in ('.mp3', '.wav'):
            return jsonify({'error': 'Extension not allowed'}), 400

    src = os.path.join(folders[folder], old_name)
    if not os.path.exists(src):
        return jsonify({'error': 'Source file not found'}), 404

    dst = os.path.join(folders[folder], new_name)

    # Resolve name conflicts (but allow same name = no-op)
    if os.path.abspath(src) != os.path.abspath(dst) and os.path.exists(dst):
        base, ext = os.path.splitext(new_name)
        counter = 1
        while os.path.exists(dst):
            dst = os.path.join(folders[folder], f"{base}_{counter}{ext}")
            counter += 1

    os.rename(src, dst)
    return jsonify({'success': True, 'new_filename': os.path.basename(dst)})


@app.route('/api/delete', methods=['DELETE'])
def api_delete():
    folders = get_folders()
    if not folders:
        return jsonify({'error': 'No album selected'}), 400

    data = request.json or {}
    filename = data.get('filename')
    folder   = data.get('folder', 'disliked')   # any folder allowed

    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    if folder not in folders:
        return jsonify({'error': 'Invalid folder'}), 400

    file_path = os.path.join(folders[folder], filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    os.remove(file_path)
    return jsonify({'success': True})


@app.route('/api/trim', methods=['POST'])
def api_trim():
    folders = get_folders()
    if not folders:
        return jsonify({'error': 'No album selected'}), 400

    data = request.json or {}
    filename = data.get('filename')
    folder = data.get('folder')
    start_time = data.get('start', 0)
    end_time = data.get('end')

    if not filename or folder not in folders or end_time is None:
        return jsonify({'error': 'Invalid parameters'}), 400

    src = os.path.join(folders[folder], filename)
    if not os.path.exists(src):
        return jsonify({'error': 'Source file not found'}), 404

    base, ext = os.path.splitext(filename)
    dst_name = f"{base}_cut{ext}"
    dst = os.path.join(folders['cuts'], dst_name)

    # Resolve name conflicts
    counter = 1
    while os.path.exists(dst):
        dst_name = f"{base}_cut_{counter}{ext}"
        dst = os.path.join(folders['cuts'], dst_name)
        counter += 1

    duration = float(end_time) - float(start_time)
    
    cmd = [
        'ffmpeg', '-y',
        '-ss', str(start_time),
        '-i', src,
        '-t', str(duration),
        '-c', 'copy',
        dst
    ]
    
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        return jsonify({'error': f'ffmpeg failed: {e.stderr.decode("utf-8", errors="ignore")}'}), 500

    return jsonify({'success': True, 'new_filename': dst_name})
@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    import threading
    import time
    def shutdown():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=shutdown).start()
    return jsonify({'success': True})


if __name__ == '__main__':
    print("=" * 52)
    print("  [*] Music Sorting Studio")
    print("=" * 52)
    print(f"  >>  http://localhost:5000")
    print(f"  DIR: {BASE_DIR}")
    print("  Press Ctrl+C to stop")
    print("=" * 52)
    app.run(debug=False, port=5000, threaded=True)
