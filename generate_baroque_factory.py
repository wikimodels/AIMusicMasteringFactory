"""
Baroque Music Production Factory
CLI and batch orchestrator powered by baroque_engine.py.
Can generate batches from 1 to 300+ contrasting Baroque tracks across 9 distinct archetypes.
"""

import os
import sys
import argparse
import time
from baroque_engine import (
    ARCHETYPE_GENERATORS,
    KEYS_CATALOG,
    generate_baroque_track,
)

DEFAULT_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "baroque_collection_v2")

# Curated 14 showcase tracks representing maximum stylistic contrast
SHOWCASE_TRACKS = [
    # 1. Toccata (Brilliant Harpsichord cascades, dry, rapid 16th/32nd notes)
    (1, "TOCCATA", (50, "Dm", True)),
    (2, "TOCCATA", (45, "Am", True)),
    
    # 2. French Overture (Majestic double-dotted royal court fanfare)
    (3, "FRENCH_OVERTURE", (53, "F", False)),
    (4, "FRENCH_OVERTURE", (50, "D", False)),
    
    # 3. La Folia con Variazioni (Accelerating diminutions: 8ths -> 16ths -> Corelli cadence)
    (5, "FOLIA_VARIATIONS", (50, "Dm", True)),
    (6, "FOLIA_VARIATIONS", (43, "Gm", True)),
    
    # 4. Organ Chorale Prelude (Massive cathedral organ, 16' pedal & 4-part polyphony)
    (7, "ORGAN_CHORALE", (48, "Cm", True)),
    (8, "ORGAN_CHORALE", (45, "Am", True)),
    
    # 5. Gigue / Saltarello (Bouncy galloping 6/8 dance with playful imitations)
    (9, "GIGUE_DANCE", (55, "G", False)),
    (10, "GIGUE_DANCE", (48, "C", False)),
    
    # 6. Dido's Lament (Chromatic passus duriusculus & weeping suspensions)
    (11, "DIDO_LAMENT", (43, "Gm", True)),
    
    # 7. Chaconne Buildup (3/4 ostinato with accelerating bariolage waves)
    (12, "CHACONNE_BUILDUP", (50, "Dm", True)),
    
    # 8. Pastoral Siciliana (Gentle swaying 6/8 flauto dolce & lute)
    (13, "SICILIANA_PASTORALE", (53, "F", False)),
    
    # 9. Concerto Grosso (Vivaldian motoric driving 16th strings & stile concitato)
    (14, "CONCERTO_GROSSO", (43, "Gm", True)),
]

def generate_showcase(output_dir: str = DEFAULT_OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    print("=" * 75)
    print("BAROQUE FACTORY: 14 CONTRASTING SHOWCASE TRACKS (40 BPM, 42-49s)")
    print(f"Output directory: {output_dir}")
    print("=" * 75)
    
    t_start = time.time()
    for idx, (t_id, arch, key_tup) in enumerate(SHOWCASE_TRACKS, start=1):
        clean_arch = arch.replace('_', ' ').title()
        print(f"\n[{idx:02d}/14] Generating: {clean_arch} in {key_tup[1]}...")
        t0 = time.time()
        midi_p, mp3_p = generate_baroque_track(
            track_id=t_id,
            archetype_name=arch,
            key_tuple=key_tup,
            output_dir=output_dir,
            seed=42 + t_id * 10,
            bpm=40
        )
        dt = time.time() - t0
        print(f"   -> Rendered in {dt:.1f}s | MP3: {os.path.basename(mp3_p)}")
        
    total_dt = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"SUCCESS: All 14 contrasting showcase tracks generated in {total_dt:.1f}s!")
    print(f"Location: {output_dir}")
    print("=" * 75)

def generate_full_batch(count: int = 300, output_dir: str = DEFAULT_OUTPUT_DIR):
    os.makedirs(output_dir, exist_ok=True)
    archetype_list = list(ARCHETYPE_GENERATORS.keys())
    print("=" * 75)
    print(f"BAROQUE FACTORY: BATCH GENERATION OF {count} TRACKS")
    print(f"Archetypes: {len(archetype_list)} | Keys: {len(KEYS_CATALOG)}")
    print(f"Output directory: {output_dir}")
    print("=" * 75)
    
    t_start = time.time()
    for i in range(1, count + 1):
        arch = archetype_list[(i - 1) % len(archetype_list)]
        key_tup = KEYS_CATALOG[(i - 1 + (i // len(archetype_list))) % len(KEYS_CATALOG)]
        
        # Minor-only archetypes adjustment
        if arch in ['FOLIA_VARIATIONS', 'DIDO_LAMENT'] and not key_tup[2]:
            key_tup = (key_tup[0], key_tup[1] + "m", True)
            
        seed_val = 1000 + i * 37
        t0 = time.time()
        midi_p, mp3_p = generate_baroque_track(
            track_id=i,
            archetype_name=arch,
            key_tuple=key_tup,
            output_dir=output_dir,
            seed=seed_val,
            bpm=40
        )
        dt = time.time() - t0
        clean_arch = arch.replace('_', ' ').title()
        print(f"[{i:03d}/{count}] {clean_arch} in {key_tup[1]} -> {os.path.basename(mp3_p)} ({dt:.1f}s)")
        
    total_dt = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"SUCCESS: Generated {count} tracks in {total_dt:.1f}s ({total_dt/count:.2f}s per track)")
    print(f"Location: {output_dir}")
    print("=" * 75)

def main():
    parser = argparse.ArgumentParser(description="Baroque AI Music Factory")
    parser.add_argument("--count", type=int, default=14, help="Number of tracks to generate (14 for showcase, 300 for full library)")
    parser.add_argument("--out", type=str, default=DEFAULT_OUTPUT_DIR, help="Output directory path")
    args = parser.parse_args()
    
    if args.count == 14:
        generate_showcase(args.out)
    else:
        generate_full_batch(args.count, args.out)

if __name__ == "__main__":
    main()
