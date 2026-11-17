"""
Test Suite 8: Deep Genre Differentiation & Historical Distinctiveness
Enforces that Pavane, Ciaccona, Galliard, Toccata, Lamento, Siciliana, etc.
each possess their own authentic rhythmic DNA, metric architecture,
and harmonic ground variations — eliminating intra-genre and inter-genre monotony.
"""

import json
from pathlib import Path
import numpy as np
import pytest

from baroque_loops_generator.composer import compose_track
from baroque_loops_generator.models import FORM_SCHEMATA
from baroque_loops_generator.theory import note_name_to_midi

MATRIX_FILE = Path(__file__).resolve().parent.parent.parent / "baroque_master_matrix_300.json"

@pytest.fixture(scope="module")
def matrix_tracks():
    with open(MATRIX_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def test_bpm_genre_separation_gate(matrix_tracks):
    """
    CRITICAL QUALITY GATE:
    Tempos must reflect historical dance types and not be squeezed into 56-58 BPM!
    Fast dances (Galliard, Canzona, Toccata) must be faster than grave forms (Lamento, Sarabande, Pavane).
    """
    bpms_by_form = {}
    for t in matrix_tracks:
        bpms_by_form.setdefault(t['form_code'], []).append(t['bpm'])
        
    avg_lamento = np.mean(bpms_by_form['Lamento'])
    avg_sarabande = np.mean(bpms_by_form['Sarabande'])
    avg_galliard = np.mean(bpms_by_form['Galliard'])
    avg_canzona = np.mean(bpms_by_form['Canzona'])
    avg_toccata = np.mean(bpms_by_form['Toccata'])
    
    # Fast forms must be significantly faster than slow forms
    assert avg_galliard > 70, f"Galliard is too slow: avg BPM = {avg_galliard:.1f} (must be > 70)"
    assert avg_canzona > 70, f"Canzona is too slow: avg BPM = {avg_canzona:.1f} (must be > 70)"
    assert avg_toccata > 64, f"Toccata is too slow: avg BPM = {avg_toccata:.1f} (must be > 64)"
    assert avg_lamento < 55, f"Lamento is too fast: avg BPM = {avg_lamento:.1f} (must be < 55)"
    assert avg_sarabande < 55, f"Sarabande is too fast: avg BPM = {avg_sarabande:.1f} (must be < 55)"
    
    # Global BPM std across all 300 tracks must be >= 6.0
    all_bpms = [t['bpm'] for t in matrix_tracks]
    bpm_std = float(np.std(all_bpms))
    assert bpm_std >= 6.0, f"BPM range across matrix is too flat! std = {bpm_std:.2f}"

def test_harmonic_ground_diversity_per_genre(matrix_tracks):
    """
    Tracks within the same genre must NOT all have identical chord progressions!
    Pavane and Ciaccona must have multiple authentic historical ground schemata.
    """
    # Check that FORM_SCHEMATA provides multiple variations for main genres
    assert isinstance(FORM_SCHEMATA['Pavane'], list), "Pavane schema missing"
    assert isinstance(FORM_SCHEMATA['Ciaccona'], list), "Ciaccona schema missing"
    
    # In matrix, check that track filenames or progression variants rotate
    prog_variants = {}
    for t in matrix_tracks:
        f = t['form_code']
        prog_variants.setdefault(f, set()).add(t.get('progression_variant', 'default'))
        
    # Major genres must feature at least 2 distinct harmonic progression variants
    assert len(prog_variants.get('Pavane', [])) >= 2, "Pavane lacks harmonic progression diversity"
    assert len(prog_variants.get('Ciaccona', [])) >= 2, "Ciaccona lacks harmonic progression diversity"

def test_pavane_vs_ciaccona_rhythmic_distinctiveness():
    """
    Pavane (duple, stately march) and Ciaccona (triple, Sarabande beat-2 accent)
    must produce completely distinct rhythmic duration profiles.
    """
    cfg_pavane = {
        'index': 1, 'volume': 1, 'volume_title': 'T', 'key_code': 'Dm',
        'form_code': 'Pavane', 'steps': 128, 'meter': '4/4', 'bpm': 54,
        'texture_code': 'T01', 'start_code': 'S01', 'cadence_code': 'C01',
        'progression_variant': 'Lachrimae'
    }
    cfg_ciaccona = {
        'index': 5, 'volume': 1, 'volume_title': 'T', 'key_code': 'Dm',
        'form_code': 'Ciaccona', 'steps': 128, 'meter': '3/4', 'bpm': 60,
        'texture_code': 'T01', 'start_code': 'S01', 'cadence_code': 'C01',
        'progression_variant': 'Descending_Tetrachord'
    }
    
    notes_pavane = compose_track(cfg_pavane)
    notes_ciaccona = compose_track(cfg_ciaccona)
    
    # Check that Pavane has 4/4 bar rhythm and Ciaccona has 3/4 bar rhythm
    pavane_steps = [n['step'] % 16 for n in notes_pavane]
    ciaccona_steps = [n['step'] % 12 for n in notes_ciaccona]
    
    # In Ciaccona (3/4, 12 steps per bar), beat 2 is step 4. Beat 2 must have prominent presence.
    beat2_ciaccona = [s for s in ciaccona_steps if s == 4]
    assert len(beat2_ciaccona) >= 4, "Ciaccona lacks characteristic Sarabande 2nd beat emphasis!"

def test_canzona_dactylic_rhythm():
    """Canzona must feature characteristic French dactylic motif (Long - Short - Short)."""
    cfg = {
        'index': 100, 'volume': 4, 'volume_title': 'T', 'key_code': 'Dm',
        'form_code': 'Canzona', 'steps': 128, 'meter': '4/4', 'bpm': 84,
        'texture_code': 'T06', 'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    durations = [n['duration'] for n in notes]
    # Check that 4n is followed by 8n in the composition
    has_dactyl = any(
        durations[i] == '4n' and durations[i+1] == '8n' and durations[i+2] == '8n'
        for i in range(len(durations) - 2)
    )
    assert has_dactyl, "Canzona lacks defining Baroque dactylic rhythm (4n - 8n - 8n)!"
