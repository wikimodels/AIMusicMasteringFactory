import os

resume_path = os.path.expandvars(r"%APPDATA%\uTorrent\resume.dat")
with open(resume_path, "rb") as f:
    raw = f.read()

# Bencode parser for torrent names and paths
import re

# Find strings associated with path and caption
torrents = []
# split roughly by .torrent
parts = raw.split(b".torrent")
for p in parts[:-1]:
    # Extract name before .torrent
    name_match = re.search(rb"([^\x00-\x1f\\/:*?\"<>|]+\.torrent)$", p + b".torrent")
    # Search for path nearby
    path_match = re.search(rb"path\d+:([A-Za-z]:\\[^\x00-\x1f\"]+)", p)
    caption_match = re.search(rb"caption\d+:([^\x00-\x1f]+)", p)
    
    t_name = name_match.group(1).decode("utf-8", errors="ignore") if name_match else "unknown"
    t_path = path_match.group(1).decode("utf-8", errors="ignore") if path_match else "unknown"
    torrents.append((t_name, t_path))

for t, p in torrents[-10:]:
    print(f"Torrent: {t} -> Path: {p}")
