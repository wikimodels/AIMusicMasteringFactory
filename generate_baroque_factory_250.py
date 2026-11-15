"""
Industrial Baroque Grand Piano Factory (250 Noble Masterpieces)
=============================================================================
Procedural Baroque Engine generating 250 distinct, noble, slow Baroque
masterpieces (50 - 60 BPM, Minor Keys) with Yamaha C5 Concert Grand Piano,
singing cantabile lines, expressive Alberti/arpeggio textures, suspensions,
and concert hall acoustic mastering.
=============================================================================
"""

import os
import sys
import time
import argparse
import subprocess
import numpy as np
import scipy.signal as signal
import soundfile as sf
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from typing import Dict, List, Tuple, Any

from render_golden_fond import (
    load_salamander_samples,
    get_piano_sample,
    apply_concert_grand_reverb,
    SR,
    TICKS_PER_BEAT,
    FFMPEG_PATH,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "baroque_factory_250")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# HARMONIC SYSTEM (8 CLASSICAL MINOR KEYS)
# ---------------------------------------------------------------------------

KEYS = {
    'Dm': {
        'name': 'D Minor', 'root': 38, 'tonic_mid': 62,
        'italian': 'Re minore', 'affekt': 'Tragico e Nobile'
    },
    'Cm': {
        'name': 'C Minor', 'root': 36, 'tonic_mid': 60,
        'italian': 'Do minore', 'affekt': 'Patetico e Solenne'
    },
    'Gm': {
        'name': 'G Minor', 'root': 31, 'tonic_mid': 55,
        'italian': 'Sol minore', 'affekt': 'Melanconico e Tenero'
    },
    'Am': {
        'name': 'A Minor', 'root': 33, 'tonic_mid': 57,
        'italian': 'La minore', 'affekt': 'Devoto e Cantabile'
    },
    'Fm': {
        'name': 'F Minor', 'root': 29, 'tonic_mid': 53,
        'italian': 'Fa minore', 'affekt': 'Profondo e Doloroso'
    },
    'Bm': {
        'name': 'B Minor', 'root': 35, 'tonic_mid': 59,
        'italian': 'Si minore', 'affekt': 'Nostalgico e Solitario'
    },
    'Em': {
        'name': 'E Minor', 'root': 28, 'tonic_mid': 52,
        'italian': 'Mi minore', 'affekt': 'Meditativo e Grave'
    },
    'C#m': {
        'name': 'C# Minor', 'root': 37, 'tonic_mid': 61,
        'italian': 'Do diesis minore', 'affekt': 'Appassionato e Soave'
    },
}

KEY_NAMES = list(KEYS.keys())

# Build chord pitches relative to root
def get_chord(root: int, chord_type: str) -> Tuple[int, List[int], List[int]]:
    """
    Returns (bass_note, accompaniment_pitches, melodic_targets)
    """
    r = root
    r_mid = r + 12
    if chord_type == 'i': # tonic minor
        bass = r
        acc = [r_mid, r_mid + 3, r_mid + 7, r_mid + 12]
        mel = [r_mid + 12, r_mid + 15, r_mid + 19, r_mid + 24]
    elif chord_type == 'V': # dominant major / 7th
        bass = r + 7
        acc = [r_mid + 7, r_mid + 11, r_mid + 14, r_mid + 17]
        mel = [r_mid + 11, r_mid + 14, r_mid + 17, r_mid + 23]
    elif chord_type == 'iv': # subdominant minor
        bass = r + 5
        acc = [r_mid + 5, r_mid + 8, r_mid + 12, r_mid + 17]
        mel = [r_mid + 8, r_mid + 12, r_mid + 17, r_mid + 20]
    elif chord_type == 'VI': # submediant major
        bass = r + 8
        acc = [r_mid + 8, r_mid + 12, r_mid + 15, r_mid + 20]
        mel = [r_mid + 12, r_mid + 15, r_mid + 20, r_mid + 24]
    elif chord_type == 'III': # mediant major
        bass = r + 3
        acc = [r_mid + 3, r_mid + 7, r_mid + 10, r_mid + 15]
        mel = [r_mid + 7, r_mid + 10, r_mid + 15, r_mid + 19]
    elif chord_type == 'VII': # subtonic major
        bass = r + 10
        acc = [r_mid + 10, r_mid + 14, r_mid + 17, r_mid + 22]
        mel = [r_mid + 10, r_mid + 14, r_mid + 17, r_mid + 22]
    elif chord_type == 'ii_dim': # diminished supertonic
        bass = r + 2
        acc = [r_mid + 2, r_mid + 5, r_mid + 8, r_mid + 14]
        mel = [r_mid + 5, r_mid + 8, r_mid + 14, r_mid + 17]
    elif chord_type == 'V6_dim': # chromatic diminished / passing
        bass = r + 11
        acc = [r_mid + 5, r_mid + 8, r_mid + 11, r_mid + 14]
        mel = [r_mid + 11, r_mid + 14, r_mid + 17, r_mid + 23]
    elif chord_type == 'VI_dim': # chromatic 6th
        bass = r + 9
        acc = [r_mid + 3, r_mid + 6, r_mid + 9, r_mid + 12]
        mel = [r_mid + 12, r_mid + 15, r_mid + 18, r_mid + 21]
    elif chord_type == 'I_maj': # Picardy Third Resolution
        bass = r - 12 if r >= 36 else r
        acc = [r, r_mid, r_mid + 4, r_mid + 7, r_mid + 12, r_mid + 16]
        mel = [r_mid + 16, r_mid + 19, r_mid + 24]
    else:
        bass = r
        acc = [r_mid, r_mid + 3, r_mid + 7]
        mel = [r_mid + 12, r_mid + 15]
        
    return bass, acc, mel

# ---------------------------------------------------------------------------
# 12 BAROQUE STYLES & STRUCTURAL DEFINITIONS
# ---------------------------------------------------------------------------

STYLES = [
    {
        'id': 'folia',
        'name': 'La Folia di Spagna',
        'sub': 'Adagio e Grave',
        'meter': (3, 4),
        'bpm_range': (52, 55),
        'chords': ['i', 'V', 'i', 'VII', 'III', 'VII', 'i', 'V', 'i', 'iv', 'V', 'I_maj'],
        'acc_style': 'alberti_34',
        'mel_style': 'sarabande_2nd',
    },
    {
        'id': 'passacaglia',
        'name': 'Passacaglia Dolorosa',
        'sub': 'Largo Sostenuto',
        'meter': (3, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'VII', 'VI', 'V', 'i', 'VII', 'VI', 'V', 'iv', 'V', 'I_maj'],
        'acc_style': 'ground_wave',
        'mel_style': 'suspension_chain',
    },
    {
        'id': 'chaconne',
        'name': 'Chaconne delle Memorie',
        'sub': 'Grave Maestoso',
        'meter': (3, 4),
        'bpm_range': (52, 54),
        'chords': ['i', 'V', 'VI', 'V', 'iv', 'i', 'ii_dim', 'V', 'i', 'iv', 'V', 'I_maj'],
        'acc_style': 'chaconne_rolled',
        'mel_style': 'arpeggiated_arch',
    },
    {
        'id': 'sarabande',
        'name': 'Sarabande Triste',
        'sub': 'Lento Espressivo',
        'meter': (3, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'V', 'i', 'iv', 'VII', 'III', 'VI', 'ii_dim', 'V', 'i', 'I_maj'],
        'acc_style': 'sarabande_chord',
        'mel_style': 'sarabande_noble',
    },
    {
        'id': 'lamento',
        'name': 'Lamento con Passus Duriusculus',
        'sub': 'Largo Triste',
        'meter': (4, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'V6_dim', 'VII', 'VI_dim', 'VI', 'V', 'iv', 'V', 'I_maj'],
        'acc_style': 'chromatic_ground',
        'mel_style': 'sighing_seufzer',
    },
    {
        'id': 'siciliana',
        'name': 'Siciliana Melancholica',
        'sub': 'Andante Pastorale',
        'meter': (6, 8),
        'bpm_range': (54, 56),
        'chords': ['i', 'V', 'i', 'iv', 'ii_dim', 'V', 'i', 'VI', 'iv', 'V', 'i', 'iv', 'ii_dim', 'V', 'i', 'iv', 'V', 'I_maj'],
        'acc_style': 'siciliana_rocking',
        'mel_style': 'dotted_siciliana',
    },
    {
        'id': 'aria_cantabile',
        'name': 'Adagio Cantabile (Aria Barocca)',
        'sub': 'Adagio Sostenuto',
        'meter': (4, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'V', 'i', 'iv', 'III', 'ii_dim', 'V', 'i', 'I_maj'],
        'acc_style': 'alberti_44',
        'mel_style': 'vocal_cantilena',
    },
    {
        'id': 'invention',
        'name': 'Invenzione a Due Voci',
        'sub': 'Lento Contrapuntale',
        'meter': (4, 4),
        'bpm_range': (56, 58),
        'chords': ['i', 'V', 'i', 'iv', 'III', 'VII', 'VI', 'ii_dim', 'V', 'I_maj'],
        'acc_style': 'polyphonic_duet',
        'mel_style': 'canonic_imitation',
    },
    {
        'id': 'pavane',
        'name': 'Pavane Lacrymae',
        'sub': 'Largo Dolente',
        'meter': (4, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'VII', 'i', 'V', 'VI', 'ii_dim', 'iv', 'V', 'I_maj'],
        'acc_style': 'stately_pavane',
        'mel_style': 'renaissance_arch',
    },
    {
        'id': 'tombeau',
        'name': 'Tombeau Elegiaco',
        'sub': 'Grave Triste',
        'meter': (3, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'iv', 'VII', 'III', 'VI', 'ii_dim', 'V', 'i', 'iv', 'V', 'I_maj'],
        'acc_style': 'alberti_34',
        'mel_style': 'tombeau_agremens',
    },
    {
        'id': 'sinfonia_grave',
        'name': 'Sinfonia Grave all\'Antica',
        'sub': 'Adagio Maestoso',
        'meter': (4, 4),
        'bpm_range': (50, 52),
        'chords': ['i', 'V', 'VI', 'iv', 'i', 'ii_dim', 'iv', 'V', 'I_maj'],
        'acc_style': 'stately_pavane',
        'mel_style': 'french_dotted',
    },
    {
        'id': 'ricercar',
        'name': 'Ricercar Cromatico',
        'sub': 'Lento Solenne',
        'meter': (4, 4),
        'bpm_range': (54, 56),
        'chords': ['i', 'V', 'iv', 'i', 'VI', 'ii_dim', 'iv', 'i', 'V', 'I_maj'],
        'chords': ['i', 'V', 'iv', 'i', 'VI', 'III', 'ii_dim', 'V', 'iv', 'V', 'I_maj'],
        'acc_style': 'polyphonic_duet',
        'mel_style': 'chromatic_subject',
    },
]

# Helper timing & rolling functions
def t_beat(bar: int, beat: float, meter_beats: int, beat_sec: float) -> float:
    return (bar - 1) * meter_beats * beat_sec + (beat - 1.0) * beat_sec

def dur_s(beats: float, beat_sec: float) -> float:
    return beats * beat_sec

def piano_arpeggio(notes: List[int], start_s: float, base_vel: float = 0.65,
                   step_s: float = 0.045, dur_s_val: float = 2.0) -> List[Tuple[float, float, int, float]]:
    res = []
    for i, n in enumerate(notes):
        v = base_vel + (0.05 if i == 0 else -0.02 * (i % 2))
        res.append((start_s + i * step_s, max(0.4, dur_s_val - i * step_s), n, max(0.35, min(0.95, v))))
    return res

# ---------------------------------------------------------------------------
# PROCEDURAL COMPOSITION ENGINE
# ---------------------------------------------------------------------------

def compose_baroque_piece(style_def: Dict[str, Any], key_id: str, var_idx: int) -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    key_info = KEYS[key_id]
    root = key_info['root']
    meter = style_def['meter']
    meter_num, meter_den = meter
    
    bpm_min, bpm_max = style_def['bpm_range']
    # Deterministic variation of BPM within range
    bpm = bpm_min + (var_idx % (bpm_max - bpm_min + 1))
    
    # Timing
    if meter == (6, 8):
        # 6/8 meter: dotted quarter = 1 beat pulse
        beat_sec = 60.0 / bpm # duration of 1 dotted quarter (3 eighths)
        bar_sec = beat_sec * 2.0 # 2 dotted quarters per bar
        eighth_sec = bar_sec / 6.0
    else:
        beat_sec = 60.0 / bpm # quarter note
        bar_sec = meter_num * beat_sec
        eighth_sec = beat_sec / 2.0
        
    chords = list(style_def['chords'])
    num_bars = len(chords)
    
    notes: List[Tuple[float, float, int, float]] = []
    
    # -----------------------------------------------------------------------
    # 1. ACCOMPANIMENT GENERATION (LEFT HAND)
    # -----------------------------------------------------------------------
    acc_style = style_def['acc_style']
    
    for bar_idx, ch_name in enumerate(chords, start=1):
        t_bar = (bar_idx - 1) * bar_sec
        bass_p, chord_ps, mel_targets = get_chord(root, ch_name)
        is_final_bar = (bar_idx == num_bars)
        
        if is_final_bar:
            # Grand Picardy Third Arpeggiated Resolution
            notes.extend(piano_arpeggio(chord_ps, t_bar, base_vel=0.88, step_s=0.065, dur_s_val=4.8))
            continue
            
        if acc_style in ['alberti_34']:
            # Beat 1: Deep resonant bass
            notes.append((t_bar, dur_s(2.6, beat_sec), bass_p, 0.82))
            # Beats 1.5, 2.0, 2.5, 3.0: Alberti wave (Low - High - Mid - High)
            for i in range(1, 6):
                idx = [0, 2, 1, 2, 0][(i - 1) % 5]
                p = chord_ps[idx % len(chord_ps)]
                vel = 0.52 + (0.04 if i % 2 == 0 else 0.0)
                notes.append((t_bar + i * eighth_sec, dur_s(1.2, beat_sec), p, vel))
                
        elif acc_style in ['ground_wave']:
            # Deep bass note on beat 1
            notes.append((t_bar, dur_s(2.8, beat_sec), bass_p, 0.84))
            # Undulating 8th notes rising and falling
            for i in range(1, 6):
                p = chord_ps[(i - 1) % len(chord_ps)]
                notes.append((t_bar + i * eighth_sec, dur_s(1.1, beat_sec), p, 0.53))
                
        elif acc_style in ['chaconne_rolled']:
            # Beat 1: Ground bass
            notes.append((t_bar, dur_s(0.9, beat_sec), bass_p, 0.82))
            # Beat 2: Accentuated rolled chord (Chaconne signature)
            notes.extend(piano_arpeggio(chord_ps, t_bar + dur_s(1.0, beat_sec), base_vel=0.76, step_s=0.04, dur_s_val=1.8))
            
        elif acc_style in ['sarabande_chord']:
            # Beat 1: Bass note
            notes.append((t_bar, dur_s(0.95, beat_sec), bass_p, 0.80))
            # Beat 2: Prolonged singing rolled chord
            notes.extend(piano_arpeggio(chord_ps, t_bar + dur_s(1.0, beat_sec), base_vel=0.75, step_s=0.038, dur_s_val=1.9))
            
        elif acc_style in ['chromatic_ground']:
            # Resonant sustained bass
            notes.append((t_bar, dur_s(3.8, beat_sec), bass_p, 0.85))
            # Flowing harp arpeggio fill
            notes.extend(piano_arpeggio(chord_ps, t_bar + dur_s(0.5, beat_sec), base_vel=0.56, step_s=0.045, dur_s_val=3.2))
            
        elif acc_style in ['alberti_44']:
            # Beat 1: Deep bass note
            notes.append((t_bar, dur_s(3.8, beat_sec), bass_p, 0.82))
            # 8 eighth-notes undulating Alberti pattern (0, 2, 1, 2)
            for i in range(8):
                idx = [0, 2, 1, 2][i % 4]
                p = chord_ps[idx % len(chord_ps)]
                notes.append((t_bar + i * eighth_sec, dur_s(1.0, beat_sec), p, 0.52 + (0.03 if i % 2 == 0 else 0)))
                
        elif acc_style in ['siciliana_rocking']:
            # 6/8 meter: Dotted quarters on beat 1 and beat 2
            notes.append((t_bar, bar_sec * 0.45, bass_p, 0.78))
            notes.append((t_bar + bar_sec * 0.5, bar_sec * 0.45, bass_p + 7, 0.65))
            # Gentle inner arpeggio
            notes.extend(piano_arpeggio(chord_ps, t_bar + 0.1, base_vel=0.52, step_s=0.04, dur_s_val=1.5))
            
        elif acc_style in ['stately_pavane']:
            # Stately slow majestic chords
            notes.append((t_bar, dur_s(1.8, beat_sec), bass_p, 0.84))
            notes.extend(piano_arpeggio(chord_ps, t_bar + dur_s(0.5, beat_sec), base_vel=0.68, step_s=0.04, dur_s_val=1.4))
            notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.8, beat_sec), bass_p, 0.78))
            notes.extend(piano_arpeggio(chord_ps, t_bar + dur_s(2.5, beat_sec), base_vel=0.65, step_s=0.04, dur_s_val=1.4))
            
        elif acc_style in ['polyphonic_duet']:
            # Contrapuntal lower voice (Tenor/Bass line)
            shift = (var_idx * 2) % 5
            notes.append((t_bar, dur_s(1.8, beat_sec), bass_p, 0.80))
            notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.8, beat_sec), chord_ps[1 % len(chord_ps)], 0.74))
            
    # -----------------------------------------------------------------------
    # 2. MELODIC CANTABILE GENERATION (RIGHT HAND)
    # -----------------------------------------------------------------------
    mel_style = style_def['mel_style']
    
    for bar_idx, ch_name in enumerate(chords, start=1):
        t_bar = (bar_idx - 1) * bar_sec
        _, _, mel_targets = get_chord(root, ch_name)
        is_final_bar = (bar_idx == num_bars)
        
        # Dynamic arch: quiet opening, building to bar 7-8, peaceful resolution
        dyn_factor = 0.85 + 0.15 * np.sin(np.pi * (bar_idx - 1) / max(1, num_bars - 1))
        
        if is_final_bar:
            # Singing Picardy third resolution in top voice
            final_pitch = mel_targets[0]
            notes.append((t_bar, 4.5, final_pitch, 0.82))
            continue
            
        if meter == (3, 4):
            # 3/4 Bar Melodic Archetypes
            target_p = mel_targets[(bar_idx + var_idx) % len(mel_targets)]
            
            if mel_style in ['sarabande_2nd', 'sarabande_noble']:
                # Prolonged expressive 2nd beat with appoggiatura
                notes.append((t_bar, dur_s(1.0, beat_sec), target_p - 2, 0.75 * dyn_factor))
                notes.append((t_bar + dur_s(1.0, beat_sec), dur_s(1.8, beat_sec), target_p, 0.88 * dyn_factor))
                # Delicate ornament on beat 3 of alternate bars
                if bar_idx % 2 == 0:
                    notes.append((t_bar + dur_s(2.6, beat_sec), dur_s(0.35, beat_sec), target_p + 2, 0.68))
                    
            elif mel_style in ['suspension_chain']:
                # Classical 4-3 or 7-6 suspension: sustained dissonance on beat 1 resolving on beat 2.5
                notes.append((t_bar, dur_s(1.5, beat_sec), target_p + 1, 0.84 * dyn_factor))
                notes.append((t_bar + dur_s(1.5, beat_sec), dur_s(1.4, beat_sec), target_p, 0.74 * dyn_factor))
                
            elif mel_style in ['arpeggiated_arch']:
                # Soaring melodic arch: Beat 1 target, Beat 2 peak, Beat 3 return
                notes.append((t_bar, dur_s(0.9, beat_sec), target_p, 0.80 * dyn_factor))
                notes.append((t_bar + dur_s(1.0, beat_sec), dur_s(1.0, beat_sec), target_p + 3, 0.86 * dyn_factor))
                notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(0.9, beat_sec), target_p + 1, 0.72 * dyn_factor))
                
            elif mel_style in ['tombeau_agremens']:
                # Fragile French baroque sigh
                notes.append((t_bar, dur_s(1.8, beat_sec), target_p, 0.82 * dyn_factor))
                notes.append((t_bar + dur_s(1.8, beat_sec), dur_s(0.6, beat_sec), target_p + 1, 0.68))
                notes.append((t_bar + dur_s(2.4, beat_sec), dur_s(0.5, beat_sec), target_p - 1, 0.70))
                
        elif meter == (4, 4):
            # 4/4 Bar Melodic Archetypes
            target_p = mel_targets[(bar_idx + var_idx) % len(mel_targets)]
            
            if mel_style in ['sighing_seufzer']:
                # Descending painful sigh on beats 1 and 3
                notes.append((t_bar, dur_s(1.8, beat_sec), target_p + 1, 0.85 * dyn_factor))
                notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.8, beat_sec), target_p, 0.75 * dyn_factor))
                
            elif mel_style in ['vocal_cantilena']:
                # Arching Italianate cantilena line
                notes.append((t_bar, dur_s(1.8, beat_sec), target_p, 0.82 * dyn_factor))
                notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.0, beat_sec), target_p + 2, 0.86 * dyn_factor))
                notes.append((t_bar + dur_s(3.0, beat_sec), dur_s(0.9, beat_sec), target_p - 1, 0.72 * dyn_factor))
                
            elif mel_style in ['canonic_imitation', 'chromatic_subject']:
                # Polyphonic subject with rhythmic imitation
                notes.append((t_bar, dur_s(1.0, beat_sec), target_p, 0.84 * dyn_factor))
                notes.append((t_bar + dur_s(1.0, beat_sec), dur_s(1.0, beat_sec), target_p + 3, 0.86 * dyn_factor))
                notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.0, beat_sec), target_p + 2, 0.80 * dyn_factor))
                notes.append((t_bar + dur_s(3.0, beat_sec), dur_s(1.0, beat_sec), target_p, 0.76 * dyn_factor))
                
            elif mel_style in ['renaissance_arch', 'french_dotted']:
                # Noble dotted rhythm: dotted quarter + eighth
                notes.append((t_bar, dur_s(1.4, beat_sec), target_p, 0.85 * dyn_factor))
                notes.append((t_bar + dur_s(1.5, beat_sec), dur_s(0.5, beat_sec), target_p + 2, 0.72))
                notes.append((t_bar + dur_s(2.0, beat_sec), dur_s(1.8, beat_sec), target_p - 1, 0.78 * dyn_factor))
                
        elif meter == (6, 8):
            # 6/8 Siciliana Rocking Cantilena
            target_p = mel_targets[(bar_idx + var_idx) % len(mel_targets)]
            notes.append((t_bar, eighth_sec * 2.8, target_p, 0.82 * dyn_factor))
            notes.append((t_bar + eighth_sec * 3.0, eighth_sec * 0.9, target_p + 2, 0.70))
            notes.append((t_bar + eighth_sec * 4.0, eighth_sec * 1.8, target_p + 3, 0.85 * dyn_factor))
            
    title = f"{style_def['name']} in {key_info['name']} ({style_def['sub']})"
    return notes, title, bpm, meter

# ---------------------------------------------------------------------------
# RENDERING PIPELINE FOR BATCH GENERATION
# ---------------------------------------------------------------------------

def render_single_track(notes: List[Tuple[float, float, int, float]], title: str,
                        bpm: int, meter: Tuple[int, int], prefix: str,
                        out_dir: str = OUTPUT_DIR) -> Tuple[str, str]:
    # 1. Export MIDI
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=title, time=0))
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    track.append(MetaMessage('time_signature', numerator=meter[0], denominator=meter[1], clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))
    track.append(Message('program_change', program=0, channel=0, time=0)) # Acoustic Grand Piano
    
    beat_sec = 60.0 / bpm
    midi_events = []
    
    # 2. Audio Buffer
    max_time_s = max(s + d for s, d, _, _ in notes)
    total_samples = int((max_time_s + 4.5) * SR)
    stereo_buf = np.zeros((total_samples, 2), dtype=np.float32)
    
    for start_s, dur_s_val, midi_p, vel in notes:
        # Yamaha C5 Concert Grand Synthesis
        note_audio = get_piano_sample(midi_p, dur_s_val, vel)
        s_idx = int(start_s * SR)
        e_idx = min(total_samples, s_idx + len(note_audio))
        if e_idx > s_idx:
            stereo_buf[s_idx:e_idx] += note_audio[:e_idx - s_idx]
            
        # MIDI event
        start_tick = int((start_s / beat_sec) * TICKS_PER_BEAT)
        dur_tick = int((dur_s_val / beat_sec) * TICKS_PER_BEAT)
        midi_vel = int(vel * 127)
        midi_events.append((start_tick, 10, Message('note_on', note=midi_p, velocity=midi_vel, channel=0)))
        midi_events.append((start_tick + dur_tick, 5, Message('note_off', note=midi_p, velocity=0, channel=0)))
        
    midi_events.sort(key=lambda x: (x[0], x[1]))
    last_t = 0
    for tick, _, msg in midi_events:
        delta = max(0, tick - last_t)
        msg.time = delta
        track.append(msg)
        last_t = tick
    track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
    
    midi_path = os.path.join(out_dir, f"{prefix}.mid")
    mid.save(midi_path)
    
    # 3. DSP Acoustic Mastering (Hall Reverb + -1.50 dBFS True Peak)
    final_audio = apply_concert_grand_reverb(stereo_buf, room_size=0.82, wet=0.22)
    wav_path = os.path.join(out_dir, f"{prefix}.wav")
    mp3_path = os.path.join(out_dir, f"{prefix}.mp3")
    
    sf.write(wav_path, final_audio, SR, subtype='PCM_24')
    
    actual_sec = len(final_audio) / SR
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={title}",
        "-metadata", "artist=Yamaha C5 Concert Grand Piano",
        "-metadata", "album=Noble Slow Baroque Factory",
        "-metadata", f"genre=Slow Baroque Piano ({bpm} BPM)",
        "-metadata", f"comment=Noble Baroque Masterpiece ({actual_sec:.1f}s)",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return midi_path, mp3_path

# ---------------------------------------------------------------------------
# CATALOG BUILDER (250 UNIQUE TRACKS)
# ---------------------------------------------------------------------------

def generate_catalog(count: int = 250) -> List[Dict[str, Any]]:
    catalog = []
    num_styles = len(STYLES)
    num_keys = len(KEY_NAMES)
    
    for i in range(count):
        style_idx = i % num_styles
        # Key rotates with style index offset so every adjacent track is a different key AND style
        key_idx = (i + (i // num_styles)) % num_keys
        var_idx = i // num_styles
        
        style = STYLES[style_idx]
        key_id = KEY_NAMES[key_idx]
        
        catalog.append({
            'index': i + 1,
            'prefix': f"baroque_noble_{i+1:03d}",
            'style': style,
            'key_id': key_id,
            'var_idx': var_idx,
        })
    return catalog

def main():
    parser = argparse.ArgumentParser(description="Baroque Piano 250 Factory")
    parser.add_argument("--count", type=int, default=12, help="Number of tracks to render (default 12 for experiment)")
    parser.add_argument("--start", type=int, default=1, help="Start track index (default 1)")
    args = parser.parse_args()
    
    catalog = generate_catalog(250)
    selected = [c for c in catalog if args.start <= c['index'] < args.start + args.count]
    
    print("=" * 75)
    print("NOBLE SLOW BAROQUE PIANO FACTORY - 250 ARCHIVE")
    print(f"Target count: {len(selected)} tracks (from #{args.start:03d} to #{args.start + len(selected) - 1:03d})")
    print("Instrument: Yamaha C5 Concert Grand Piano (Salamander Grand)")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 75)
    
    load_salamander_samples()
    print("Salamander Concert Grand Piano samples loaded into RAM!\n")
    
    t_start = time.time()
    for item in selected:
        idx = item['index']
        prefix = item['prefix']
        style = item['style']
        key_id = item['key_id']
        var_idx = item['var_idx']
        
        notes, title, bpm, meter = compose_baroque_piece(style, key_id, var_idx)
        print(f"[{idx:03d}/250] Rendering: {title} ({bpm} BPM, {meter[0]}/{meter[1]})...")
        t0 = time.time()
        midi_p, mp3_p = render_single_track(notes, title, bpm, meter, prefix)
        dt = time.time() - t0
        print(f"   -> Rendered in {dt:.1f}s | MP3: {os.path.basename(mp3_p)}")
        
    total_dt = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"SUCCESS: Rendered {len(selected)} tracks in {total_dt:.1f}s ({total_dt/max(1, len(selected)):.1f}s per track)!")
    print(f"Destination: {OUTPUT_DIR}")
    print("=" * 75)

if __name__ == "__main__":
    main()
