import os
import json
from baroque_loops_generator.synth import load_salamander_samples, render_piece
from baroque_loops_generator.composer import compose_track

pilot_indices = [1, 2, 4, 8, 10, 11, 12]
with open('baroque_master_matrix_300.json', 'r', encoding='utf-8') as f:
    matrix = json.load(f)

tracks = [t for t in matrix if t['index'] in pilot_indices]
out_dir = os.path.abspath('PILOT_DEMOS')
os.makedirs(out_dir, exist_ok=True)

print(f"Pre-loading acoustic samples...")
load_salamander_samples()

for t in tracks:
    notes = compose_track(t)
    mp3, mid, js, dur = render_piece(t, notes, out_dir)
    print(f"[OK] Rendered #{t['index']:02d}: {t['filename']} ({dur:.1f}s | {t['bpm']} BPM | {t['meter']})")
    print(f"     Genre:     {t['form_code']} ({t['progression_desc']})")
    print(f"     Texture:   {t['texture_code']} - {t['texture_name']}")
    print(f"     Audio:     {mp3}")
