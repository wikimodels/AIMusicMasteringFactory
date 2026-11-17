"""
Unit Tests for Baroque Master Album Dashboard Server
Validates REST API endpoints, Range audio streaming, and atomic 3-file deletion.
"""

import os
import json
import socket
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
import pytest

from baroque_dashboard.server import BaroqueDashboardHandler, DEFAULT_ALBUM_DIR

@pytest.fixture(scope="module")
def live_server():
    """Starts a live ThreadingHTTPServer on an ephemeral port."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), BaroqueDashboardHandler)
    port = server.server_address[1]
    
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    
    base_url = f"http://127.0.0.1:{port}"
    yield base_url
    
    server.shutdown()
    server.server_close()

def test_static_index_html(live_server):
    """GET / must return the Angular Material index.html."""
    url = f"{live_server}/"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        html = response.read().decode("utf-8")
        assert "BAROQUE MASTER" in html
        assert "mat-sidenav" in html
        assert "track-cards-grid" in html

def test_api_albums_endpoint(live_server):
    """GET /api/albums must return all 10 volumes."""
    url = f"{live_server}/api/albums"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "albums" in data
        albums = data["albums"]
        assert len(albums) == 10
        # Check volumes have rendered tracks
        vol1 = [a for a in albums if a["volume"] == 1][0]
        assert vol1["track_count"] > 0
        assert vol1["has_files"] is True
        vol3 = [a for a in albums if a["volume"] == 3][0]
        assert vol3["track_count"] == 30

def test_api_tracks_endpoint(live_server):
    """GET /api/tracks?album=Tom_03_Early_Baroque_Minor must list all 30 tracks with metadata."""
    url = f"{live_server}/api/tracks?album=Tom_03_Early_Baroque_Minor"
    with urllib.request.urlopen(url) as response:
        assert response.status == 200
        data = json.loads(response.read().decode("utf-8"))
        assert "tracks" in data
        tracks = data["tracks"]
        assert len(tracks) == 30
        
        # Verify first track metadata
        t0 = tracks[0]
        assert t0["has_mp3"] is True
        assert t0["has_mid"] is True
        assert t0["has_json"] is True
        assert t0["bpm"] > 0
        assert t0["meter"] in ["4/4", "3/4", "6/8"]

def test_audio_streaming_range_request(live_server):
    """GET /api/audio with Range header must return HTTP 206 Partial Content."""
    # Find a track from Vol 3
    url_tracks = f"{live_server}/api/tracks?album=Tom_03_Early_Baroque_Minor"
    with urllib.request.urlopen(url_tracks) as res:
        tracks = json.loads(res.read().decode("utf-8"))["tracks"]
    
    stem = tracks[0]["stem"]
    audio_url = f"{live_server}/api/audio?album=Tom_03_Early_Baroque_Minor&track={stem}"
    
    # 1. Full request (200)
    with urllib.request.urlopen(audio_url) as res:
        assert res.status == 200
        assert res.headers.get("Accept-Ranges") == "bytes"
        assert res.headers.get("Content-Type") == "audio/mpeg"
        total_size = int(res.headers.get("Content-Length"))
        assert total_size > 100000
        
    # 2. Byte Range request (206)
    req = urllib.request.Request(audio_url, headers={"Range": "bytes=0-1023"})
    with urllib.request.urlopen(req) as res:
        assert res.status == 206
        content = res.read()
        assert len(content) == 1024
        assert res.headers.get("Content-Range").startswith("bytes 0-1023/")

def test_atomic_three_file_deletion(live_server, tmp_path):
    """DELETE /api/tracks must delete .mp3, .mid, and .json atomically without touching others."""
    # Create an isolated mock sub-album inside DEFAULT_ALBUM_DIR
    mock_album_name = "Tom_Test_Mock_Deletion"
    mock_dir = DEFAULT_ALBUM_DIR / mock_album_name
    mock_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        stem = "Loop_Mock_099_Test_Delete"
        mp3_f = mock_dir / f"{stem}.mp3"
        mid_f = mock_dir / f"{stem}.mid"
        json_f = mock_dir / f"{stem}.json"
        
        mp3_f.write_text("mock mp3 content", encoding="utf-8")
        mid_f.write_text("mock mid content", encoding="utf-8")
        json_f.write_text("{}", encoding="utf-8")
        
        assert mp3_f.exists() and mid_f.exists() and json_f.exists()
        
        # Send DELETE request
        delete_url = f"{live_server}/api/tracks?album={mock_album_name}&track={stem}"
        req = urllib.request.Request(delete_url, method="DELETE")
        
        with urllib.request.urlopen(req) as res:
            assert res.status == 200
            data = json.loads(res.read().decode("utf-8"))
            assert data["success"] is True
            assert len(data["deleted"]) == 3
            assert f"{stem}.mp3" in data["deleted"]
            assert f"{stem}.mid" in data["deleted"]
            assert f"{stem}.json" in data["deleted"]
            
        # Verify files are deleted from disk
        assert not mp3_f.exists(), "MP3 was not deleted!"
        assert not mid_f.exists(), "MID was not deleted!"
        assert not json_f.exists(), "JSON was not deleted!"
        
    finally:
        # Cleanup mock dir
        if mock_dir.exists():
            for p in mock_dir.iterdir():
                p.unlink()
            mock_dir.rmdir()
