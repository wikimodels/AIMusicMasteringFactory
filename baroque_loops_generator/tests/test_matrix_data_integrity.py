"""
Test Suite 1: Matrix Data Integrity & Specifications Coverage
Audits baroque_master_matrix_300.json against baroque_master_matrix_300.md
"""

import os
import json
import pytest

MATRIX_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "baroque_master_matrix_300.json")
DOC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "baroque_master_matrix_300.md")

ALLOWED_KEYS = {'Dm', 'Am', 'Gm', 'Em', 'Bm', 'Cm', 'Fsm', 'D_Dor'}
ALLOWED_TEXTURES = {f'T{i:02d}' for i in range(1, 13)}
ALLOWED_STARTS = {f'S{i:02d}' for i in range(1, 9)}
ALLOWED_CADENCES = {f'C{i:02d}' for i in range(1, 9)}
ALLOWED_METERS = {'4/4', '3/4', '6/8'}

@pytest.fixture(scope="module")
def matrix_data():
    assert os.path.exists(MATRIX_PATH), f"Matrix JSON missing at {MATRIX_PATH}"
    with open(MATRIX_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def test_matrix_total_tracks_count(matrix_data):
    """Must have exactly 300 tracks across 10 volumes."""
    assert len(matrix_data) == 300, f"Expected 300 tracks, found {len(matrix_data)}"

def test_matrix_volume_partitioning(matrix_data):
    """Every volume must contain exactly 30 tracks."""
    for vol in range(1, 11):
        vol_tracks = [t for t in matrix_data if t['volume'] == vol]
        assert len(vol_tracks) == 30, f"Volume {vol} has {len(vol_tracks)} tracks, expected 30"

def test_zero_dummy_engine_codes(matrix_data):
    """Strict ban: Zero legacy dummy 'E' engine codes in matrix."""
    for t in matrix_data:
        assert 'engine_code' not in t, f"Found legacy dummy engine_code in track {t['filename']}"
        assert 'texture_code' in t, f"Missing texture_code in track {t['filename']}"
        assert t['texture_code'] in ALLOWED_TEXTURES, f"Invalid texture {t['texture_code']}"

def test_intra_volume_key_rotation(matrix_data):
    """Every volume must rotate keys with zero adjacent duplicates."""
    for vol in range(1, 11):
        vol_tracks = [t for t in matrix_data if t['volume'] == vol]
        keys = [t['key_code'] for t in vol_tracks]
        
        # Check all keys belong to allowed minor set
        for k in keys:
            assert k in ALLOWED_KEYS, f"Disallowed key {k} in Volume {vol}"
            
        # Check continuous rotation: no two adjacent tracks share same key
        for i in range(len(keys) - 1):
            assert keys[i] != keys[i + 1], f"Adjacent key collision in Vol {vol} at tracks {i} and {i+1}: {keys[i]}"
            
        # Check variety: volume must contain all 8 minor keys
        assert len(set(keys)) == 8, f"Volume {vol} only has {len(set(keys))} unique keys, expected 8"

def test_texture_diversity_per_volume(matrix_data):
    """Every volume must feature all 12 playing styles T01-T12."""
    for vol in range(1, 11):
        vol_tracks = [t for t in matrix_data if t['volume'] == vol]
        texs = {t['texture_code'] for t in vol_tracks}
        assert len(texs) == 12, f"Volume {vol} only has {len(texs)} textures, expected 12"

def test_starts_and_cadences_validity(matrix_data):
    """All starts must be S01-S08 and cadences C01-C08."""
    for t in matrix_data:
        assert t['start_code'] in ALLOWED_STARTS, f"Invalid start {t['start_code']} in {t['filename']}"
        assert t['cadence_code'] in ALLOWED_CADENCES, f"Invalid cadence {t['cadence_code']} in {t['filename']}"
        assert t['meter'] in ALLOWED_METERS, f"Invalid meter {t['meter']} in {t['filename']}"
