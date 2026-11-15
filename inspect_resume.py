import os
import re

resume_path = os.path.expandvars(r"%APPDATA%\uTorrent\resume.dat")
print(f"Reading {resume_path}...")
if os.path.exists(resume_path):
    with open(resume_path, "rb") as f:
        content = f.read()
    
    # decode with latin1 or utf8 ignore
    text = content.decode("utf-8", errors="ignore")
    # Search for windows path patterns
    paths = set(re.findall(r"[A-Za-z]:\\[^:\*\?\"<>\|\r\n\t]+", text))
    clean_paths = sorted([p for p in paths if len(p) > 3 and not any(p.endswith(ext) for ext in ['.exe', '.dll', '.ico'])])
    print("Found download paths in uTorrent:")
    for p in clean_paths:
        print("  ", p)
