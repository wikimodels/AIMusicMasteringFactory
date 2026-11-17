"""
Test Suite 7: Full 300 Matrix Composition & Music Theory Gate
Validates that all 300 tracks in baroque_master_matrix_300.json can be composed
without errors, respecting all theoretical constraints, pitch boundaries,
polyphony limits, and anti-monotony rhythm rules.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from baroque_loops_generator.composer import compose_track
from baroque_loops_generator.theory import note_name_to_midi, is_pitch_valid_in_key

MATRIX_FILE = Path(__file__).resolve().parent.parent.parent / "baroque_master_matrix_300.json"

@pytest.fixture(scope="module")
def all_tracks():
    with open(MATRIX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def test_compose_all_300_tracks_without_error(all_tracks):
    """Verify all 300 tracks compose cleanly into valid NoteEvents."""
    assert len(all_tracks) == 300
    for track in all_tracks:
        tid = track.get('filename_id', f"Track_{track.get('index')}")
        notes = compose_track(track)
        assert len(notes) >= 16, f"Track {tid} generated too few notes ({len(notes)})"
        max_notes = (track['steps'] // 12 + 2) * 14
        assert len(notes) <= max_notes, f"Track {tid} exceeded density ceiling ({len(notes)} > {max_notes})"

def test_all_300_pitch_scale_validity(all_tracks):
    """Zero foreign / alien pitches outside key mode across all 300 tracks."""
    for track in all_tracks:
        tid = track.get('filename_id', f"Track_{track.get('index')}")
        notes = compose_track(track)
        key_code = track['key_code']
        cadence_code = track['cadence_code']
        
        for n in notes:
            midi = note_name_to_midi(n['note'])
            is_valid = is_pitch_valid_in_key(midi, key_code)
            # If C01 Picardy in final bar, major 3rd is explicitly allowed
            if not is_valid and cadence_code == 'C01' and n['step'] >= track['steps'] - 16:
                is_valid = True
            assert is_valid, (
                f"Track {tid} ({key_code}) generated out-of-scale note: {n['note']} ({midi}) "
                f"at step {n['step']}"
            )

def test_all_300_polyphony_limit_max_4_notes(all_tracks):
    """No single step across any of the 300 tracks may contain > 4 simultaneous notes."""
    for track in all_tracks:
        tid = track.get('filename_id', f"Track_{track.get('index')}")
        notes = compose_track(track)
        step_counts = {}
        for n in notes:
            step_counts[n['step']] = step_counts.get(n['step'], 0) + 1
        for step, count in step_counts.items():
            assert count <= 4, (
                f"Track {tid} violated polyphony limit: {count} notes at step {step}"
            )

def test_all_300_rhythm_anti_monotony(all_tracks):
    """All 300 tracks must have varied rhythm (std > 0.3) - zero flat metronomes."""
    for track in all_tracks:
        tid = track.get('filename_id', f"Track_{track.get('index')}")
        notes = compose_track(track)
        sop_notes = [n for n in notes if note_name_to_midi(n['note']) >= 60]
        sop_steps = [n['step'] for n in sop_notes]
        intervals = [sop_steps[i+1] - sop_steps[i] for i in range(len(sop_steps)-1) if sop_steps[i+1] > sop_steps[i]]
        
        assert len(intervals) >= 4, f"Track {tid} has too few melodic intervals"
        std_val = float(np.std(intervals))
        assert std_val > 0.3, (
            f"Mechanical rhythm in track {tid} ({track['texture_code']})! std = {std_val:.3f}"
        )
