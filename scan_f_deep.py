import os
import sys

# Scan F:\ with utf-8 output to avoid cp1252 crash
sys.stdout.reconfigure(encoding='utf-8')

print("Listing all root entries of F:\\:")
for entry in os.scandir("F:\\"):
    print(f"  {entry.name} (is_dir={entry.is_dir()})")

# Let's check $RECYCLE.BIN
recycle = "F:\\$RECYCLE.BIN"
if os.path.exists(recycle):
    print("Checking Recycle Bin on F:...")
    for root, dirs, files in os.walk(recycle):
        for f in files:
            p = os.path.join(root, f)
            try:
                print(f"  Recycle file: {f} ({os.path.getsize(p) / (1024**3):.2f} GB)")
            except:
                pass
