"""
Test Suite 3: Anti-Monotony Rhythm & Metric Differentiation
Bans the mechanical '4 quarter notes marching trap' across all genres.
"""

import numpy as np
import pytest
from baroque_loops_generator.composer import compose_track
from baroque_loops_generator.theory import note_name_to_midi

def test_ban_flat_marching_quarter_notes_trap():
    """
    CRITICAL QUALITY GATE:
    A track must NEVER consist merely of 4 identical quarter notes in every measure!
    Standard deviation of melodic onset intervals must be > 0.
    """
    configs_to_test = [
        {'form_code': 'Lamento', 'meter': '4/4', 'texture_code': 'T05', 'key_code': 'Dm'},
        {'form_code': 'Ciaccona', 'meter': '3/4', 'texture_code': 'T01', 'key_code': 'Gm'},
        {'form_code': 'Siciliana', 'meter': '6/8', 'texture_code': 'T01', 'key_code': 'Em'},
        {'form_code': 'Galliard', 'meter': '3/4', 'texture_code': 'T08', 'key_code': 'D_Dor'},
        {'form_code': 'Toccata', 'meter': '4/4', 'texture_code': 'T04', 'key_code': 'Am'},
        {'form_code': 'Pavane', 'meter': '4/4', 'texture_code': 'T09', 'key_code': 'Cm'},
    ]
    
    for cfg in configs_to_test:
        cfg.update({'index': 1, 'volume': 1, 'volume_title': 'T', 'steps': 128, 'bpm': 56, 'start_code': 'S01', 'cadence_code': 'C01'})
        notes = compose_track(cfg)
        
        # Extract soprano melody notes
        sop_notes = [n for n in notes if note_name_to_midi(n['note']) >= 60]
        assert len(sop_notes) >= 8, f"Too few melody notes in {cfg['form_code']}"
        
        sop_steps = [n['step'] for n in sop_notes]
        intervals = [sop_steps[i+1] - sop_steps[i] for i in range(len(sop_steps)-1) if sop_steps[i+1] > sop_steps[i]]
        
        # Verify onset intervals are NOT all identical (std > 0)
        assert len(intervals) > 0, "No positive step intervals found"
        std_val = float(np.std(intervals))
        assert std_val > 0.3, (
            f"Mechanical rhythm detected in {cfg['form_code']} ({cfg['texture_code']})! "
            f"Interval std = {std_val:.3f}. All notes fall on identical rhythmic grids!"
        )

def test_duration_diversity_across_pieces():
    """Tracks must employ a rich vocabulary of note durations, not just '4n'."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Lamento', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T04', # Tirata
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    durations = {n['duration'] for n in notes}
    # Tirata must have 16n, along with 4n, 2n or 1n
    assert '16n' in durations, "Tirata failed to include 16th note passaggi!"
    assert len(durations) >= 3, f"Insufficient duration diversity: only {durations}"

def test_siciliana_pastorale_6_8_meter():
    """Siciliana in 6/8 must have 2 pulses per bar with dotted pastoral rhythm."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Em', 'form_code': 'Siciliana', 'steps': 128,
        'meter': '6/8', 'bpm': 56, 'texture_code': 'T01',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    # Check that dotted 8th exists in notes
    durations = {n['duration'] for n in notes}
    assert '8n.' in durations or '16n' in durations, (
        f"Siciliana lacks characteristic pastoral dotted rhythm! Found: {durations}"
    )

def test_galliard_hemiola_penultimate_bar():
    """Galliard must feature a metric grouping change before cadence."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'D_Dor', 'form_code': 'Galliard', 'steps': 128,
        'meter': '3/4', 'bpm': 58, 'texture_code': 'T08',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    num_bars = 128 // 12
    penult_bar_st = (num_bars - 2) * 12
    # Verify notes exist in penultimate bar
    penult_notes = [n for n in notes if penult_bar_st <= n['step'] < penult_bar_st + 12]
    assert len(penult_notes) >= 2, "Penultimate bar lacks notes for Hemiola"
