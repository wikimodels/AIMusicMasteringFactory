"""
Test Suite 5: 4-Phase Dramaturgy & Musical Story Arc
Verifies Exposition -> Development -> Climax -> Resolution dynamics.
"""

import pytest
from baroque_loops_generator.composer import compose_track
from baroque_loops_generator.theory import note_name_to_midi

def test_climax_pitch_peak():
    """
    In the 4-phase dramaturgy arc, the Climax phase (Bar 6 / golden ratio)
    must reach the soaring peak pitch register of the track.
    """
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Lamento', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T01',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    bar_len = 16
    
    # Bar 0 (Exposition) vs Bar 5 (Climax = Bar 6 in 1-based index: steps 80..95)
    bar0_notes = [n for n in notes if n['step'] < 16 and note_name_to_midi(n['note']) >= 60]
    climax_notes = [n for n in notes if 80 <= n['step'] < 96 and note_name_to_midi(n['note']) >= 60]
    
    if bar0_notes and climax_notes:
        max_expo = max(note_name_to_midi(n['note']) for n in bar0_notes)
        max_climax = max(note_name_to_midi(n['note']) for n in climax_notes)
        assert max_climax >= max_expo, (
            f"Climax pitch ({max_climax}) did not soar above or equal exposition ({max_expo})!"
        )

def test_dramaturgic_velocity_curve():
    """
    Velocity must peak at the Climax and calm down during Resolution/Cadence.
    """
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Gm', 'form_code': 'Ciaccona', 'steps': 128,
        'meter': '3/4', 'bpm': 56, 'texture_code': 'T01',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    bar_len = 12
    num_bars = 128 // 12
    
    climax_st = (num_bars - 3) * bar_len
    resol_st = (num_bars - 1) * bar_len
    
    climax_notes = [n for n in notes if climax_st <= n['step'] < climax_st + bar_len]
    resol_notes = [n for n in notes if resol_st <= n['step'] < resol_st + bar_len]
    
    avg_climax_vel = sum(n['velocity'] for n in climax_notes) / len(climax_notes)
    avg_resol_vel = sum(n['velocity'] for n in resol_notes) / len(resol_notes)
    
    assert avg_climax_vel > avg_resol_vel, (
        f"Dramaturgic velocity failed: Climax {avg_climax_vel:.2f} <= Resolution {avg_resol_vel:.2f}"
    )
