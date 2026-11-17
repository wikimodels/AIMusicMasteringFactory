"""
Industrial Conveyor Runner for Baroque Master Album
Renders 30 tracks per sub-album into baroque_master_album/
"""

import os
import sys
import json
import time
import concurrent.futures
from typing import Dict, List, Tuple, Any, Optional

from baroque_loops_generator.synth import load_salamander_samples, render_piece
from baroque_loops_generator.composer import compose_track

OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "..", "baroque_master_album")
MATRIX_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "baroque_master_matrix_300.json")

def process_item(item: Dict[str, Any], force: bool = False) -> Tuple[int, str, str, str, float]:
    idx = item['index']
    vol_num = item['volume']
    filename = item['filename']
    vol_dir = os.path.join(OUTPUT_BASE, f"Tom_{vol_num:02d}_Early_Baroque_Minor")
    
    mp3_target = os.path.join(vol_dir, f"{filename}.mp3")
    mid_target = os.path.join(vol_dir, f"{filename}.mid")
    json_target = os.path.join(vol_dir, f"{filename}.json")
    
    # Fast skip if already rendered and valid
    if not force and os.path.exists(mp3_target) and os.path.exists(mid_target) and os.path.exists(json_target):
        if os.path.getsize(mp3_target) > 50000:
            return idx, filename, mp3_target, mid_target, item.get('duration_sec', 35.0)
    
    notes = compose_track(item)
    mp3_p, mid_p, json_p, dur = render_piece(item, notes, vol_dir)
    return idx, filename, mp3_p, mid_p, dur

def run_conveyor(max_workers: int = 4, target_volume: Optional[int] = None, force: bool = False):
    print("=" * 80)
    print("BAROQUE MASTER ALBUM CONVEYOR (MODULAR ENGINE)")
    print(f"Output directory: {OUTPUT_BASE}")
    print("=" * 80)
    
    with open(MATRIX_JSON_PATH, 'r', encoding='utf-8') as f:
        matrix = json.load(f)
        
    if target_volume is not None:
        matrix = [item for item in matrix if item['volume'] == target_volume]
        print(f"[+] Filtered to Volume {target_volume:02d}: {len(matrix)} tracks.")
    else:
        print(f"[+] Loaded master matrix: {len(matrix)} tracks across 10 sub-albums.")
    print("[*] Pre-loading Yamaha C5 Salamander samples...")
    load_salamander_samples()
    
    t0 = time.time()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_item, item, force): item for item in matrix}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                res = future.result()
                results.append(res)
                if len(results) % 25 == 0 or len(results) == len(matrix):
                    print(f"    [{len(results):03d}/{len(matrix):03d}] Rendered: {res[1]} ({res[4]:.1f}s)")
            except Exception as e:
                print(f"[!] Error on {item['filename']}: {e}")
                
    total_time = time.time() - t0
    print(f"\n[SUCCESS] Rendered {len(results)}/{len(matrix)} tracks in {total_time:.1f}s!")

if __name__ == '__main__':
    vol = None
    if len(sys.argv) > 1:
        try:
            vol = int(sys.argv[1])
        except ValueError:
            pass
    run_conveyor(target_volume=vol)
