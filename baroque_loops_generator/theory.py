"""
Early Baroque Music Theory & Register Voicing Rules
"""

from typing import Tuple, List, Set
from baroque_loops_generator.models import (
    KEY_MODES, NOTE_NAMES, DEGREE_SCALE_INDEX, ChordDegrees
)

def midi_to_note_name(p: int) -> str:
    octave = (p // 12) - 1
    semi = p % 12
    return f"{NOTE_NAMES[semi]}{octave}"

def note_name_to_midi(name: str) -> int:
    octave = int(name[-1])
    p_name = name[:-1]
    offsets = {'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4,
               'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11}
    return (octave + 1) * 12 + offsets[p_name]

def octave_fit(p: int, voice: str) -> int:
    """
    Octave-preserving register fitting:
    - Bass: C2..B2 (MIDI 36..47)
    - Middle / Tenor / Alto: C3..B3 (MIDI 48..59)
    - Soprano: C4..E5 (MIDI 60..76)
    Always transposes by +-12 to preserve exact pitch class!
    """
    if voice == 'bass':
        low, high = 36, 47
    elif voice == 'middle':
        low, high = 48, 59
    else: # soprano
        low, high = 60, 76
        
    while p > high:
        p -= 12
    while p < low:
        p += 12
    return p

def get_chord_degrees(key_code: str, degree: str) -> ChordDegrees:
    """
    Resolves degree into strictly diatonic / authentic harmonic baroque triad pitches.
    """
    k = KEY_MODES.get(key_code, KEY_MODES['Dm'])
    sc = k['scale']
    lt = k['leading']
    pic = k['picardy']
    
    base_idx = DEGREE_SCALE_INDEX.get(degree, 0)
    root_semi = sc[base_idx]
    third_semi = sc[(base_idx + 2) % 7]
    fifth_semi = sc[(base_idx + 4) % 7]
    sus_semi = sc[(base_idx + 3) % 7] # diatonic suspension resolving down to 3rd
    
    # Authentic dominant harmonic minor leading tone
    if degree in ['V', 'V6', 'V7']:
        third_semi = lt
    elif degree == 'I_picardy':
        third_semi = pic
    elif degree == 'I_open5':
        third_semi = fifth_semi # Open fifth / octave (no 3rd)
        
    # Bass pitch (C2..B2)
    if degree in ['i6', 'iv6', 'v6', 'V6', 'ii_dim6', 'III6', 'VI6', 'VII6']:
        bp = octave_fit(36 + third_semi, 'bass') # 1st inversion (3rd in bass)
    else:
        bp = octave_fit(36 + root_semi, 'bass')
        
    inner = [
        octave_fit(48 + root_semi, 'middle'),
        octave_fit(48 + third_semi, 'middle'),
        octave_fit(48 + fifth_semi, 'middle')
    ]
    
    soprano = [
        octave_fit(60 + root_semi, 'soprano'),
        octave_fit(60 + third_semi, 'soprano'),
        octave_fit(60 + fifth_semi, 'soprano')
    ]
    
    sus_p = octave_fit(60 + sus_semi, 'soprano')
    
    return ChordDegrees(
        bass_pitch=bp,
        inner_pitches=inner,
        soprano_pitches=soprano,
        suspended_pitch=sus_p
    )

def get_allowed_pitch_classes(key_code: str) -> Set[int]:
    """
    Returns set of valid semitones (0..11) for key (scale + leading tone + picardy third).
    """
    k = KEY_MODES.get(key_code, KEY_MODES['Dm'])
    allowed = set(k['scale'])
    allowed.add(k['leading'])
    allowed.add(k['picardy'])
    return allowed

def is_pitch_valid_in_key(pitch: int, key_code: str) -> bool:
    semi = pitch % 12
    return semi in get_allowed_pitch_classes(key_code)
