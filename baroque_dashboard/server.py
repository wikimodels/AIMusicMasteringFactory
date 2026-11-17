"""
Baroque Master Album Dashboard Server
=============================================================================
Lightweight, robust Python HTTP server for browsing, playing, and managing
the default Baroque Master Album and its sub-albums.

Features:
- Sub-album discovery (volumes with up to 30 tracks each).
- Track metadata extraction from .json and baroque_master_matrix_300.json.
- Audio streaming with full HTTP 206 Partial Content (Range request) support.
- Atomic deletion of track artifacts: .mp3, .mid, and .json.
- Serves Angular Material 3 styled dashboard.
=============================================================================
"""

import os
import sys
import json
import mimetypes
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Any, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
STATIC_DIR = HERE / "static"
DEFAULT_ALBUM_DIR = REPO_ROOT / "baroque_master_album"
MATRIX_PATH = REPO_ROOT / "baroque_master_matrix_300.json"

# Load matrix for rich metadata lookup
matrix_cache: Dict[str, Dict[str, Any]] = {}
if MATRIX_PATH.exists():
    try:
        with open(MATRIX_PATH, "r", encoding="utf-8") as f:
            raw_matrix = json.load(f)
            for item in raw_matrix:
                matrix_cache[item.get("filename", "")] = item
    except Exception as e:
        print(f"[!] Warning: failed to load matrix cache: {e}")

def get_album_dirs() -> List[Path]:
    """Finds all sub-album directories under default album."""
    if not DEFAULT_ALBUM_DIR.exists():
        DEFAULT_ALBUM_DIR.mkdir(parents=True, exist_ok=True)
        
    sub_dirs = [p for p in DEFAULT_ALBUM_DIR.iterdir() if p.is_dir()]
    # Sort by name (e.g. Tom_01, Tom_02)
    sub_dirs.sort(key=lambda p: p.name)
    return sub_dirs

class BaroqueDashboardHandler(BaseHTTPRequestHandler):
    server_version = "BaroqueDashboard/1.0"

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_file(STATIC_DIR / "index.html", "text/html; charset=utf-8")
        elif path.startswith("/static/"):
            rel = path[len("/static/"):]
            file_path = STATIC_DIR / rel
            self.serve_static_file(file_path)
        elif path == "/api/albums":
            self.handle_get_albums()
        elif path == "/api/tracks":
            album_id = query.get("album", [""])[0]
            self.handle_get_tracks(album_id)
        elif path == "/api/audio":
            album_id = query.get("album", [""])[0]
            track_name = query.get("track", [""])[0]
            self.handle_stream_audio(album_id, track_name)
        elif path == "/api/file":
            album_id = query.get("album", [""])[0]
            track_name = query.get("track", [""])[0]
            file_type = query.get("type", ["json"])[0]
            self.handle_download_file(album_id, track_name, file_type)
        else:
            self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/api/tracks":
            album_id = query.get("album", [""])[0]
            track_stem = query.get("track", [""])[0]
            self.handle_delete_track(album_id, track_stem)
        else:
            self.send_error(404, "Unknown DELETE endpoint")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/delete_track":
            # Support DELETE via POST body for environments where HTTP DELETE has proxy issues
            content_len = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_len).decode("utf-8") if content_len > 0 else "{}"
            try:
                data = json.loads(post_body)
                album_id = data.get("album", "")
                track_stem = data.get("track", "")
                self.handle_delete_track(album_id, track_stem)
            except Exception as e:
                self.send_json_response({"success": False, "error": str(e)}, status=400)
        else:
            self.send_error(404, "Unknown POST endpoint")

    # -------------------------------------------------------------------------
    # API Handlers
    # -------------------------------------------------------------------------
    def handle_get_albums(self):
        album_dirs = get_album_dirs()
        result = []

        # Ensure at least 10 volumes are represented even if folders are created on-the-fly
        existing_names = {p.name for p in album_dirs}
        
        # Merge physical dirs + matrix volume metadata
        vol_info: Dict[int, Dict[str, Any]] = {}
        for m in matrix_cache.values():
            v = m.get("volume", 1)
            if v not in vol_info:
                vol_info[v] = {
                    "volume": v,
                    "title": m.get("volume_title", f"Том {v:02d}"),
                    "key": m.get("key_code", ""),
                    "instrument": m.get("instrument", "Chamber Piano"),
                }

        for v in range(1, 11):
            folder_name = f"Tom_{v:02d}_Early_Baroque_Minor"
            folder_path = DEFAULT_ALBUM_DIR / folder_name
            
            # Count actual files
            track_count = 0
            total_dur = 0.0
            genres = set()
            keys = set()
            has_files = False

            if folder_path.exists():
                mp3_files = list(folder_path.glob("*.mp3"))
                track_count = len(mp3_files)
                has_files = track_count > 0
                for f in mp3_files:
                    stem = f.stem
                    m = matrix_cache.get(stem)
                    if m:
                        total_dur += m.get("duration_sec", 35.0)
                        genres.add(m.get("form_name", m.get("form_code", "")))
                        keys.add(m.get("key_code", ""))

            meta = vol_info.get(v, {"volume": v, "title": f"Том {v:02d}: Собрание {v}", "key": "Dm"})
            
            result.append({
                "id": folder_name,
                "volume": v,
                "title": meta["title"],
                "key": meta.get("key", "Dm"),
                "instrument": meta.get("instrument", "Chamber Piano (Yamaha C5)"),
                "track_count": track_count,
                "expected_count": 30,
                "total_duration_sec": round(total_dur, 1),
                "genres": sorted(list(genres)),
                "keys": sorted(list(keys)),
                "has_files": has_files,
                "folder_path": str(folder_path)
            })

        self.send_json_response({"albums": result, "root_album": str(DEFAULT_ALBUM_DIR)})

    def handle_get_tracks(self, album_id: str):
        if not album_id:
            self.send_json_response({"error": "Missing album parameter"}, status=400)
            return

        album_dir = DEFAULT_ALBUM_DIR / album_id
        if not album_dir.exists():
            # If folder doesn't exist yet, return empty list cleanly
            self.send_json_response({"album": album_id, "tracks": [], "count": 0})
            return

        tracks = []
        # Find all MP3 files
        mp3_files = sorted(list(album_dir.glob("*.mp3")), key=lambda p: p.name)
        
        for mp3_p in mp3_files:
            stem = mp3_p.stem
            mid_p = album_dir / f"{stem}.mid"
            json_p = album_dir / f"{stem}.json"
            
            # Lookup metadata from matrix cache
            meta = matrix_cache.get(stem, {})
            
            # Try to read Tone.js JSON if available for exact note counts
            note_count = None
            if json_p.exists():
                try:
                    with open(json_p, "r", encoding="utf-8") as jf:
                        j_data = json.load(jf)
                        if isinstance(j_data, list) and len(j_data) > 0 and "notes" in j_data[0]:
                            note_count = len(j_data[0]["notes"])
                except Exception:
                    pass

            track_info = {
                "stem": stem,
                "filename": stem,
                "index": meta.get("index", 0),
                "volume": meta.get("volume", 1),
                "title": meta.get("filename", stem),
                "key_code": meta.get("key_code", ""),
                "key_name": meta.get("key_name", ""),
                "form_code": meta.get("form_code", ""),
                "form_name": meta.get("form_name", ""),
                "progression_variant": meta.get("progression_variant", ""),
                "progression_desc": meta.get("progression_desc", ""),
                "texture_code": meta.get("texture_code", ""),
                "texture_name": meta.get("texture_name", ""),
                "texture_desc": meta.get("texture_desc", ""),
                "start_code": meta.get("start_code", ""),
                "start_desc": meta.get("start_desc", ""),
                "cadence_code": meta.get("cadence_code", ""),
                "cadence_desc": meta.get("cadence_desc", ""),
                "bpm": meta.get("bpm", 56),
                "meter": meta.get("meter", "4/4"),
                "duration_sec": meta.get("duration_sec", 35.0),
                "steps": meta.get("steps", 128),
                "instrument": meta.get("instrument", "Chamber Piano"),
                "note_count": note_count,
                "has_mp3": mp3_p.exists(),
                "has_mid": mid_p.exists(),
                "has_json": json_p.exists(),
                "file_size_mp3": mp3_p.stat().st_size if mp3_p.exists() else 0,
            }
            tracks.append(track_info)

        # Sort by index if present
        tracks.sort(key=lambda x: (x["index"] if x["index"] > 0 else 9999, x["stem"]))
        self.send_json_response({"album": album_id, "tracks": tracks, "count": len(tracks)})

    def handle_delete_track(self, album_id: str, track_stem: str):
        """
        Deletes .mp3, .mid, and .json files for the track atomically.
        """
        if not album_id or not track_stem:
            self.send_json_response({"success": False, "error": "album and track required"}, status=400)
            return

        album_dir = DEFAULT_ALBUM_DIR / album_id
        if not album_dir.exists():
            self.send_json_response({"success": False, "error": f"Album {album_id} not found"}, status=404)
            return

        # Target files
        targets = [
            album_dir / f"{track_stem}.mp3",
            album_dir / f"{track_stem}.mid",
            album_dir / f"{track_stem}.json",
        ]

        deleted = []
        errors = []

        for p in targets:
            if p.exists():
                try:
                    p.unlink()
                    deleted.append(p.name)
                except Exception as e:
                    errors.append(f"Failed to delete {p.name}: {e}")

        if errors:
            self.send_json_response({
                "success": False,
                "deleted": deleted,
                "errors": errors,
                "message": "Частичное удаление с ошибками"
            }, status=500)
        else:
            self.send_json_response({
                "success": True,
                "track": track_stem,
                "deleted": deleted,
                "count": len(deleted),
                "message": f"Успешно удалены файлы ({', '.join(deleted)})"
            })

    def handle_stream_audio(self, album_id: str, track_name: str):
        """
        Streams MP3 with full HTTP 206 Partial Content support for seeking in HTML5 audio.
        """
        if not album_id or not track_name:
            self.send_error(400, "Missing album or track")
            return

        # Sanitize path to prevent traversal
        if ".." in album_id or ".." in track_name:
            self.send_error(403, "Access denied")
            return

        if not track_name.endswith(".mp3"):
            track_name += ".mp3"

        audio_path = DEFAULT_ALBUM_DIR / album_id / track_name
        if not audio_path.exists():
            self.send_error(404, f"Audio file not found: {track_name}")
            return

        file_size = audio_path.stat().st_size
        range_header = self.headers.get("Range")

        if not range_header:
            # Full file request (200 OK)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            with open(audio_path, "rb") as f:
                while chunk := f.read(65536):
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        break
            return

        # Parse Range header: e.g. "bytes=0-1024" or "bytes=1024-"
        try:
            bytes_range = range_header.strip().split("=")[1]
            start_str, end_str = bytes_range.split("-")
            start = int(start_str) if start_str else 0
            end = int(end_str) if end_str else file_size - 1
            if end >= file_size:
                end = file_size - 1
            length = end - start + 1
        except Exception:
            self.send_error(416, "Requested Range Not Satisfiable")
            return

        # Partial content response (206)
        self.send_response(206)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        with open(audio_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk_size = min(65536, remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                try:
                    self.wfile.write(data)
                except (BrokenPipeError, ConnectionResetError):
                    break
                remaining -= len(data)

    def handle_download_file(self, album_id: str, track_name: str, file_type: str):
        if not album_id or not track_name:
            self.send_error(400, "Missing album or track")
            return

        ext_map = {"mid": ".mid", "json": ".json", "mp3": ".mp3"}
        ext = ext_map.get(file_type.lower(), ".json")
        target_path = DEFAULT_ALBUM_DIR / album_id / f"{track_name}{ext}"

        if not target_path.exists():
            self.send_error(404, f"File {target_path.name} not found")
            return

        mime_type = mimetypes.guess_type(str(target_path))[0] or "application/octet-stream"
        file_size = target_path.stat().st_size

        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Content-Disposition", f'attachment; filename="{target_path.name}"')
        self.end_headers()

        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                self.wfile.write(chunk)

    # -------------------------------------------------------------------------
    # Utility Helpers
    # -------------------------------------------------------------------------
    def serve_static_file(self, file_path: Path):
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, f"File {file_path.name} not found")
            return
        mime_type, _ = mimetypes.guess_type(str(file_path))
        self.serve_file(file_path, mime_type or "application/octet-stream")

    def serve_file(self, file_path: Path, content_type: str):
        try:
            with open(file_path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except Exception as e:
            self.send_error(500, f"Error reading file: {e}")

    def send_json_response(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

def run_server(port: int = 8088):
    server_address = ("127.0.0.1", port)
    httpd = ThreadingHTTPServer(server_address, BaroqueDashboardHandler)
    print("=" * 76)
    print("  BAROQUE MASTER ALBUM DASHBOARD")
    print("=" * 76)
    print(f"  [+] Server running at: http://127.0.0.1:{port}/")
    print(f"  [+] Default Album Dir: {DEFAULT_ALBUM_DIR}")
    print(f"  [+] Static Web Assets: {STATIC_DIR}")
    print("=" * 76)
    print("  Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        httpd.server_close()

if __name__ == "__main__":
    p = 8088
    if len(sys.argv) > 1:
        try:
            p = int(sys.argv[1])
        except ValueError:
            pass
    run_server(p)
