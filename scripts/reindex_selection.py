"""
Reindex SELECTION and SELECTION_MIDI Tracks Utility
==================================================
Automatically shifts, renumbers, and realigns tracks in SELECTION and SELECTION_MIDI
whenever one or more files are deleted due to Suno rejections.

Smart Loops Sync:
    Automatically detects the first affected track and copies only the remaining
    tracks of that batch (from the shifted track up to N30) into the Loops folder,
    so already uploaded tracks are not duplicated.

Usage:
    python scripts/reindex_selection.py
    python scripts/reindex_selection.py --dry-run
    python scripts/reindex_selection.py --loops-batch 4 --loops-from 12
"""

import os
import re
import json
import uuid
import shutil
import argparse

DEFAULT_SELECTION_DIR = r"D:\GitHub\AIMusicMasteringFactory\SELECTION"
DEFAULT_MIDI_DIR = r"D:\GitHub\AIMusicMasteringFactory\SELECTION_MIDI"
DEFAULT_REJECTED_DIR = r"D:\GitHub\AIMusicMasteringFactory\SELECTION_REJECTED"
DEFAULT_LOOPS_DIR = r"C:\Users\Vitali\Downloads\AIMusicTools\Loops"

BATCH_SIZE = 30
MAX_FILENAME_LEN = 70
PREFIX_RE = re.compile(r"^([A-Za-z0-9]+)_B(\d{4})_(N)?(\d{2})_(.*)\.mp3$", re.IGNORECASE)


def parse_mp3_files(selection_dir: str):
    files = [f for f in os.listdir(selection_dir) if f.lower().endswith(".mp3")]
    parsed = []
    unmatched = []
    for f in files:
        m = PREFIX_RE.match(f)
        if m:
            series = m.group(1)
            batch = int(m.group(2))
            has_n = bool(m.group(3))
            num = int(m.group(4))
            title = m.group(5)
            parsed.append({
                "filename": f,
                "series": series,
                "batch": batch,
                "has_n": has_n,
                "num": num,
                "title": title
            })
        else:
            unmatched.append(f)
    
    if unmatched:
        raise ValueError(f"Found {len(unmatched)} files not matching pattern: {unmatched[:5]}")
    
    parsed.sort(key=lambda x: (x["batch"], x["num"]))
    return parsed


def reindex(
    selection_dir: str = DEFAULT_SELECTION_DIR,
    midi_dir: str = DEFAULT_MIDI_DIR,
    rejected_dir: str = DEFAULT_REJECTED_DIR,
    loops_dir: str = DEFAULT_LOOPS_DIR,
    loops_batch: int = None,
    loops_from: int = None,
    auto_sync_loops: bool = True,
    dry_run: bool = False
):
    print("=" * 60)
    print("  SELECTION & MIDI Re-indexing Utility")
    print("=" * 60)
    print(f"Directory: {selection_dir}")
    print(f"MIDI Directory: {midi_dir}")
    if dry_run:
        print("[MODE: DRY RUN - No files will be modified]")
    print()

    # 1. Parse MP3s
    mp3_list = parse_mp3_files(selection_dir)
    total_mp3 = len(mp3_list)
    print(f"Found {total_mp3} MP3 tracks.")

    # 2. Build MP3 rename plan
    mp3_plan = []
    base_map = {}
    for idx, item in enumerate(mp3_list):
        new_batch = (idx // BATCH_SIZE) + 1
        new_num = (idx % BATCH_SIZE) + 1
        n_str = f"N{new_num:02d}" if item.get("has_n") else f"{new_num:02d}"
        series = item.get("series", "DarkJazz")
        new_prefix = f"{series}_B{new_batch:04d}_{n_str}_"
        new_name = f"{new_prefix}{item['title']}.mp3"
        
        if len(new_name) > MAX_FILENAME_LEN:
            raise ValueError(f"Name exceeds limit ({len(new_name)} > {MAX_FILENAME_LEN}): {new_name}")
        
        old_name = item["filename"]
        old_base = os.path.splitext(old_name)[0]
        new_base = os.path.splitext(new_name)[0]
        base_map[old_base] = new_base

        mp3_plan.append({
            "idx": idx + 1,
            "old_name": old_name,
            "new_name": new_name,
            "new_batch": new_batch,
            "new_num": new_num,
            "title": item["title"],
            "changed": old_name != new_name
        })

    changed_mp3 = [p for p in mp3_plan if p["changed"]]
    print(f"MP3 files requiring rename: {len(changed_mp3)} / {total_mp3}")
    
    first_changed_batch = None
    first_changed_num = None
    if changed_mp3:
        first_changed = changed_mp3[0]
        first_changed_batch = first_changed["new_batch"]
        first_changed_num = first_changed["new_num"]
        print(f"First changed position: Batch {first_changed_batch}, Track N{first_changed_num:02d}")
        print(f"  {first_changed['old_name']} -> {first_changed['new_name']}")
        print(f"Last rename:  {changed_mp3[-1]['old_name']} -> {changed_mp3[-1]['new_name']}")

    # 3. Build MIDI plan
    midi_plan = []
    orphaned_midi = []
    if os.path.exists(midi_dir):
        midi_files = sorted([f for f in os.listdir(midi_dir) if f.lower().endswith((".mid", ".midi"))])
        print(f"\nFound {len(midi_files)} MIDI files in {midi_dir}.")
        for mf in midi_files:
            old_mid_base = os.path.splitext(mf)[0]
            if old_mid_base in base_map:
                new_mid_base = base_map[old_mid_base]
                new_mid_name = f"{new_mid_base}.mid"
                midi_plan.append({
                    "old_name": mf,
                    "new_name": new_mid_name,
                    "changed": mf != new_mid_name
                })
            else:
                orphaned_midi.append(mf)
        
        changed_midi = [p for p in midi_plan if p["changed"]]
        print(f"MIDI files requiring rename: {len(changed_midi)} / {len(midi_files)}")
        if orphaned_midi:
            print(f"WARNING: {len(orphaned_midi)} orphaned MIDI files:")
            for o in orphaned_midi[:5]:
                print(f"  {o}")
    else:
        print(f"MIDI directory not found: {midi_dir}")

    if dry_run:
        print("\nDry run completed successfully. No changes applied.")
        return

    # 4. Execute MP3 renames via two-phase UUID
    if changed_mp3:
        print("\nExecuting MP3 renames (Phase 1: safe temp rename)...")
        temp_renames = []
        for p in changed_mp3:
            old_path = os.path.join(selection_dir, p["old_name"])
            temp_name = f"__tmp_{uuid.uuid4().hex[:8]}_{p['new_name']}"
            temp_path = os.path.join(selection_dir, temp_name)
            os.rename(old_path, temp_path)
            temp_renames.append((temp_path, os.path.join(selection_dir, p["new_name"])))

        print("Executing MP3 renames (Phase 2: final target rename)...")
        for temp_path, final_path in temp_renames:
            os.rename(temp_path, final_path)
        print("MP3 renames complete.")

    # 5. Execute MIDI renames via two-phase UUID
    if os.path.exists(midi_dir):
        changed_midi = [p for p in midi_plan if p["changed"]]
        if changed_midi:
            print("\nExecuting MIDI renames (Phase 1: safe temp rename)...")
            temp_midi_renames = []
            for p in changed_midi:
                old_path = os.path.join(midi_dir, p["old_name"])
                temp_name = f"__tmp_{uuid.uuid4().hex[:8]}_{p['new_name']}"
                temp_path = os.path.join(midi_dir, temp_name)
                os.rename(old_path, temp_path)
                temp_midi_renames.append((temp_path, os.path.join(midi_dir, p["new_name"])))

            print("Executing MIDI renames (Phase 2: final target rename)...")
            for temp_path, final_path in temp_midi_renames:
                os.rename(temp_path, final_path)
            print("MIDI renames complete.")

        if orphaned_midi:
            os.makedirs(os.path.join(rejected_dir, "midi"), exist_ok=True)
            for om in orphaned_midi:
                src_om = os.path.join(midi_dir, om)
                dst_om = os.path.join(rejected_dir, "midi", om)
                shutil.move(src_om, dst_om)
                print(f"Archived orphaned MIDI: {om} -> SELECTION_REJECTED/midi/")

    # 6. Update Manifest
    manifest_path = os.path.join(selection_dir, "rename_manifest.json")
    manifest_data = []
    for item in mp3_plan:
        mid_name = f"{os.path.splitext(item['new_name'])[0]}.mid"
        has_mid = os.path.exists(os.path.join(midi_dir, mid_name)) if os.path.exists(midi_dir) else False
        manifest_data.append({
            "index": item["idx"],
            "batch": item["new_batch"],
            "track_in_batch": item["new_num"],
            "filename": item["new_name"],
            "has_midi": has_mid,
            "midi_filename": mid_name if has_mid else None
        })

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    print(f"\nUpdated manifest: {manifest_path}")

    # 7. Sync Loops directory
    # If loops_batch is explicitly given, use it. Otherwise, if auto_sync_loops is True and changes occurred, use first_changed_batch
    target_batch = loops_batch if loops_batch is not None else first_changed_batch
    from_num = loops_from if loops_from is not None else (first_changed_num or 1)

    if target_batch is not None and auto_sync_loops:
        if not os.path.exists(loops_dir):
            os.makedirs(loops_dir, exist_ok=True)
        
        print(f"\nSyncing Batch {target_batch} (from track N{from_num:02d} to N{BATCH_SIZE:02d}) to Loops...")
        
        # Clear existing MP3s in loops
        for f in os.listdir(loops_dir):
            if f.lower().endswith(".mp3"):
                try:
                    os.remove(os.path.join(loops_dir, f))
                except Exception:
                    pass

        # Select tracks in target_batch with track_num >= from_num
        target_tracks = [
            item["new_name"] for item in mp3_plan 
            if item["new_batch"] == target_batch and item["new_num"] >= from_num
        ]
        
        for tt in target_tracks:
            shutil.copy2(os.path.join(selection_dir, tt), os.path.join(loops_dir, tt))
        
        print(f"Copied {len(target_tracks)} tracks (N{from_num:02d}..N{from_num + len(target_tracks) - 1:02d}) to Loops.")

    # 8. Summary
    batches_count = (total_mp3 + BATCH_SIZE - 1) // BATCH_SIZE
    last_batch_count = total_mp3 % BATCH_SIZE or BATCH_SIZE
    print("\n" + "=" * 60)
    print(f"  Summary:")
    print(f"  Total Tracks: {total_mp3}")
    print(f"  Total Batches: {batches_count} (Batches 1..{batches_count - 1} have 30 tracks; Batch {batches_count} has {last_batch_count} tracks)")
    print(f"  MIDI Files Synced: {len(midi_plan)}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Reindex SELECTION and SELECTION_MIDI tracks consecutively.")
    parser.add_argument("--selection-dir", default=DEFAULT_SELECTION_DIR, help="Path to SELECTION folder")
    parser.add_argument("--midi-dir", default=DEFAULT_MIDI_DIR, help="Path to SELECTION_MIDI folder")
    parser.add_argument("--rejected-dir", default=DEFAULT_REJECTED_DIR, help="Path to SELECTION_REJECTED folder")
    parser.add_argument("--loops-dir", default=DEFAULT_LOOPS_DIR, help="Path to Loops folder")
    parser.add_argument("--loops-batch", type=int, default=None, help="Batch number to sync to Loops folder")
    parser.add_argument("--loops-from", type=int, default=None, help="Start track number to sync to Loops (e.g. 12)")
    parser.add_argument("--no-auto-loops", action="store_true", help="Disable automatic Loops sync of modified batch")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without modifying files")

    args = parser.parse_args()
    reindex(
        selection_dir=args.selection_dir,
        midi_dir=args.midi_dir,
        rejected_dir=args.rejected_dir,
        loops_dir=args.loops_dir,
        loops_batch=args.loops_batch,
        loops_from=args.loops_from,
        auto_sync_loops=not args.no_auto_loops,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
