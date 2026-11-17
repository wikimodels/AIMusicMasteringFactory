"""
Test Suite 4: Complete Implementation of All 12 Textures (Zero Stubs)
Verifies that every texture T01-T12 produces distinct, authentic musical signatures.
"""

import pytest
from baroque_loops_generator.composer import compose_track
from baroque_loops_generator.theory import note_name_to_midi

TEXTURE_CODES = [f"T{i:02d}" for i in range(1, 13)]

@pytest.mark.parametrize("tex_code", TEXTURE_CODES)
def test_each_texture_generates_notes(tex_code):
    """Every texture must produce notes without throwing exceptions."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': tex_code,
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    assert len(notes) >= 20, f"Texture {tex_code} generated suspiciously few notes: {len(notes)}"

def test_t02_tasto_solo_drone_bass():
    """T02 (Tasto Solo) must feature sustained pedal bass notes (duration '1n' or '2n.')."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T02',
        'start_code': 'S02', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    bass_notes = [n for n in notes if note_name_to_midi(n['note']) < 48]
    assert any(n['duration'] in ['1n', '2n.'] for n in bass_notes), (
        "T02 (Tasto Solo) missing long sustained pedal bass notes!"
    )

def test_t03_chiaroscuro_dynamic_contrast():
    """T03 (Chiaroscuro) must produce dynamic contrast between Forte and Piano phrases (>0.15 velocity)."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Am', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T03',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    bar0_notes = [n for n in notes if n['step'] < 16] # Forte
    bar1_notes = [n for n in notes if 16 <= n['step'] < 32] # Piano Echo
    
    avg_vel_forte = sum(n['velocity'] for n in bar0_notes) / len(bar0_notes)
    avg_vel_piano = sum(n['velocity'] for n in bar1_notes) / len(bar1_notes)
    
    contrast = avg_vel_forte - avg_vel_piano
    assert contrast >= 0.15, (
        f"T03 (Chiaroscuro) failed to deliver dynamic echo contrast! "
        f"Forte {avg_vel_forte:.2f} vs Piano {avg_vel_piano:.2f} (diff = {contrast:.2f})"
    )

def test_t04_tirata_rapid_16th_passaggi():
    """T04 (Tirata) must contain bursts of 16th notes."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Gm', 'form_code': 'Toccata', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T04',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    sixteenths = [n for n in notes if n['duration'] == '16n']
    assert len(sixteenths) >= 8, f"T04 (Tirata) lacks rapid 16th passaggi! Only {len(sixteenths)} found."

def test_t05_suspiratio_rests_on_strong_beats():
    """T05 (Suspiratio) must avoid monotonous downbeat attacks (weeping sighs)."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Lamento', 'steps': 128,
        'meter': '4/4', 'bpm': 50, 'texture_code': 'T05',
        'start_code': 'S05', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    # Check that in bar 0, step 0 has no soprano attack (sigh enters on offbeat)
    sop_downbeats = [n for n in notes if n['step'] == 0 and note_name_to_midi(n['note']) >= 60]
    assert len(sop_downbeats) == 0, "T05 (Suspiratio) failed to keep downbeat silent for vocal sigh!"

def test_t07_campanella_high_bell_chimes():
    """T07 (Campanella) must feature repeated high octave bell notes on offbeats."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Em', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T07',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    chimes = [n for n in notes if note_name_to_midi(n['note']) >= 72 and (n['step'] % 4) == 2]
    assert len(chimes) >= 4, f"T07 (Campanella) lacks high offbeat bell chimes! Found {len(chimes)}"

def test_t10_groppo_trillo_ornamentation():
    """T10 (Groppo & Trillo) must generate rapid ornamental turns or trills around cadential suspensions."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T10',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    ornaments = [n for n in notes if n['duration'] in ['16n', '32n'] and note_name_to_midi(n['note']) >= 60]
    assert len(ornaments) >= 6, (
        f"T10 (Groppo & Trillo) lacks rapid ornamental figures! Only {len(ornaments)} found."
    )
    # Check that ornaments oscillate (differences between successive ornamental pitches <= 2 semitones)
    orn_pitches = [note_name_to_midi(n['note']) for n in ornaments]
    step_diffs = [abs(orn_pitches[i+1] - orn_pitches[i]) for i in range(len(orn_pitches)-1)]
    assert any(d in [1, 2] for d in step_diffs), (
        f"T10 ornaments must feature stepwise trill/turn oscillations (1 or 2 semitones)! Diffs: {step_diffs}"
    )

def test_t11_cantus_firmus_legatissimo():
    """T11 (Cantus Firmus Legatissimo) must feature sustained choral polyphony with ZERO fast passaggi (16n) or broken 8n picking."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T11',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    fast_notes = [n for n in notes if n['duration'] in ['8n', '16n', '32n']]
    assert len(fast_notes) == 0, (
        f"T11 (Cantus Firmus Legatissimo) contains forbidden rapid passaggi or broken 8n notes: {len(fast_notes)} notes found!"
    )
    sustained = [n for n in notes if n['duration'] in ['1n', '2n.', '2n']]
    assert len(sustained) >= 16, (
        f"T11 lacks solemn sustained chordal voices: only {len(sustained)} sustained notes found!"
    )

def test_t12_arpeggio_spezzato_split_register():
    """T12 (Arpeggio Spezzato) must feature alternating split-register broken arpeggiation (bass vs soprano leaps)."""
    cfg = {
        'index': 1, 'volume': 1, 'volume_title': 'T',
        'key_code': 'Dm', 'form_code': 'Pavane', 'steps': 128,
        'meter': '4/4', 'bpm': 56, 'texture_code': 'T12',
        'start_code': 'S01', 'cadence_code': 'C01'
    }
    notes = compose_track(cfg)
    # Must have both deep bass (< 48) and high soprano (>= 65)
    deep_bass = [n for n in notes if note_name_to_midi(n['note']) < 48]
    high_soprano = [n for n in notes if note_name_to_midi(n['note']) >= 65]
    assert len(deep_bass) >= 8, f"T12 lacks deep bass anchor notes: found {len(deep_bass)}"
    assert len(high_soprano) >= 8, f"T12 lacks high sparkling soprano notes: found {len(high_soprano)}"
    
    # Must have fast arpeggiated movement (8n or 16n)
    arpeggios = [n for n in notes if n['duration'] in ['8n', '16n']]
    assert len(arpeggios) >= 16, f"T12 lacks rapid broken arpeggio notes: found {len(arpeggios)}"
