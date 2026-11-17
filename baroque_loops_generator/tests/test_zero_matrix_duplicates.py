"""
Regression Gate: Zero Duplicate Tracks & Full Axis Decoupling Test
Guarantees:
1. Exactly 300 tracks generated across 10 volumes.
2. Parameter duplicate count == 0 across the entire 300-track collection.
3. Exact note duplicate count == 0 (100% unique musical compositions).
4. Zero adjacent key, genre, or texture collisions.
5. All 12 genres are paired with all 12 textures (full 12x12 orthogonal coverage).
"""

import pytest
from baroque_loops_generator.matrix_builder import generate_matrix
from baroque_loops_generator.composer import compose_track

@pytest.fixture(scope="module")
def full_matrix():
    return generate_matrix()

def test_exact_track_count_and_volume_distribution(full_matrix):
    """Matrix must contain exactly 300 tracks, exactly 30 per volume."""
    assert len(full_matrix) == 300
    for vol in range(1, 11):
        vol_tracks = [t for t in full_matrix if t['volume'] == vol]
        assert len(vol_tracks) == 30

def test_zero_parameter_duplicates(full_matrix):
    """No two tracks may share the exact same (genre, texture, key, start, cadence) tuple."""
    seen = {}
    duplicates = []
    for t in full_matrix:
        sig = (t['form_code'], t['texture_code'], t['key_code'], t['start_code'], t['cadence_code'])
        if sig in seen:
            duplicates.append((t['index'], seen[sig], sig))
        else:
            seen[sig] = t['index']
    assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate parameter signatures: {duplicates[:5]}"

def test_zero_exact_note_duplicates(full_matrix):
    """No two tracks may produce identical note event sequences."""
    seen_notes = {}
    duplicates = []
    for t in full_matrix:
        notes = compose_track(t)
        note_sig = tuple((n['step'], n['note'], n['duration'], n['velocity']) for n in notes)
        if note_sig in seen_notes:
            duplicates.append((t['index'], seen_notes[note_sig], t['filename']))
        else:
            seen_notes[note_sig] = t['index']
    assert len(duplicates) == 0, f"Found {len(duplicates)} duplicate note sequences: {duplicates[:5]}"

def test_zero_adjacent_collisions(full_matrix):
    """Adjacent tracks must never share the same key, genre, or playing style."""
    for i in range(len(full_matrix) - 1):
        t1, t2 = full_matrix[i], full_matrix[i + 1]
        assert t1['key_code'] != t2['key_code'], f"Adjacent key collision at tracks {t1['index']} & {t2['index']}: {t1['key_code']}"
        assert t1['form_code'] != t2['form_code'], f"Adjacent genre collision at tracks {t1['index']} & {t2['index']}: {t1['form_code']}"
        assert t1['texture_code'] != t2['texture_code'], f"Adjacent texture collision at tracks {t1['index']} & {t2['index']}: {t1['texture_code']}"

def test_full_orthogonal_texture_coverage(full_matrix):
    """Every genre must explore all 12 authentic playing styles across the collection."""
    for genre in set(t['form_code'] for t in full_matrix):
        genre_textures = set(t['texture_code'] for t in full_matrix if t['form_code'] == genre)
        assert len(genre_textures) == 12, f"Genre {genre} only has {len(genre_textures)} textures, expected 12"
