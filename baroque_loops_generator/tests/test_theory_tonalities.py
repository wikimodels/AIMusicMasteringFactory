"""
Test Suite 2: Music Theory & Pure Modal Intonation
Verifies strict minor scales, leading tones, Picardy thirds, and register fit.
"""

import pytest
from baroque_loops_generator.models import KEY_MODES
from baroque_loops_generator.theory import (
    get_chord_degrees, octave_fit, is_pitch_valid_in_key, note_name_to_midi
)
from baroque_loops_generator.composer import compose_track

TEST_KEYS = ['Dm', 'Am', 'Gm', 'Em', 'Bm', 'Cm', 'Fsm', 'D_Dor']

def test_key_modes_definitions():
    """All 8 keys must have 7 diatonic degrees, leading tone, and picardy tone."""
    for k_code, k_info in KEY_MODES.items():
        assert len(k_info['scale']) == 7, f"Key {k_code} scale does not have 7 notes"
        assert 'leading' in k_info, f"Key {k_code} missing leading tone"
        assert 'picardy' in k_info, f"Key {k_code} missing picardy third"
        assert k_info['root'] == k_info['scale'][0], f"Key {k_code} root mismatch"

def test_octave_fit_boundaries():
    """Octave fit must strictly bound voices without altering pitch class."""
    # Bass C2..B2 (36..47)
    for p in [24, 35, 38, 50, 74]:
        fitted = octave_fit(p, 'bass')
        assert 36 <= fitted <= 47, f"Bass out of bounds: {fitted} (from {p})"
        assert fitted % 12 == p % 12, f"Pitch class distorted in bass: {fitted} vs {p}"
        
    # Middle C3..B3 (48..59)
    for p in [36, 45, 52, 64, 80]:
        fitted = octave_fit(p, 'middle')
        assert 48 <= fitted <= 59, f"Middle out of bounds: {fitted} (from {p})"
        assert fitted % 12 == p % 12, f"Pitch class distorted in middle: {fitted} vs {p}"
        
    # Soprano C4..E5 (60..76)
    for p in [48, 55, 65, 76, 88]:
        fitted = octave_fit(p, 'soprano')
        assert 60 <= fitted <= 76, f"Soprano out of bounds: {fitted} (from {p})"
        assert fitted % 12 == p % 12, f"Pitch class distorted in soprano: {fitted} vs {p}"

def test_zero_alien_notes_across_all_keys():
    """
    Every composed note across all 8 keys must strictly belong to the key's
    diatonic scale, harmonic leading tone, or Picardy major third.
    """
    sample_config = {
        'index': 1, 'volume': 1, 'volume_title': 'Test',
        'form_code': 'Pavane', 'steps': 128, 'meter': '4/4',
        'bpm': 56, 'texture_code': 'T01', 'start_code': 'S01',
        'cadence_code': 'C01'
    }
    
    for k in TEST_KEYS:
        cfg = dict(sample_config)
        cfg['key_code'] = k
        notes = compose_track(cfg)
        
        for n in notes:
            midi_p = note_name_to_midi(n['note'])
            assert is_pitch_valid_in_key(midi_p, k), (
                f"Alien note {n['note']} (MIDI {midi_p}) found in key {k}!"
            )
