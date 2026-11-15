"""
Slow Baroque Piano Masterpieces Generator (50 - 60 BPM, Minor Keys)
Renders 8 noble, melodious, and deeply expressive Baroque compositions
using the authentic Yamaha C5 Concert Grand Piano (Salamander Grand)
with flowing Alberti/arpeggio accompaniment and singing cantabile melody.
Target Duration: ~40 - 50 seconds each (complete musical period + acoustic tail).
"""

import os
import sys
import time
import subprocess
import numpy as np
import scipy.signal as signal
import soundfile as sf
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from typing import Dict, List, Tuple

from render_golden_fond import (
    load_salamander_samples,
    get_piano_sample,
    apply_concert_grand_reverb,
    SR,
    TICKS_PER_BEAT,
    FFMPEG_PATH,
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "baroque_slow_piano")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Helper timing & rolling functions
def t_beat(bar: int, beat: float, meter_beats: int = 3, beat_sec: float = 1.11) -> float:
    return (bar - 1) * meter_beats * beat_sec + (beat - 1.0) * beat_sec

def dur_s(beats: float, beat_sec: float = 1.11) -> float:
    return beats * beat_sec

def piano_arpeggio(notes: List[int], start_s: float, base_vel: float = 0.65,
                   step_s: float = 0.045, dur_beats: float = 2.0, beat_sec: float = 1.11) -> List[Tuple[float, float, int, float]]:
    res = []
    d_sec = dur_s(dur_beats, beat_sec)
    for i, n in enumerate(notes):
        v = base_vel + (0.05 if i == 0 else -0.02 * (i % 2))
        res.append((start_s + i * step_s, d_sec - i * step_s, n, max(0.35, min(0.95, v))))
    return res

# ---------------------------------------------------------------------------
# 8 NOBLE SLOW BAROQUE MASTERPIECES (50 - 60 BPM, MINOR KEYS)
# ---------------------------------------------------------------------------

# 1. LA FOLIA NOBLE (D minor, 54 BPM, 3/4 meter)
def compose_slow_folia() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 54
    bs = 60.0 / bpm # 1.111s
    notes = []
    
    # 12 bars in 3/4 @ 54 BPM = 40.0s (+ 5s tail = 45.0s)
    # Folia Ground with flowing 8th-note broken chord waves in Left Hand:
    # Bar:  1: Dm,  2: A7,  3: Dm,  4: C,   5: F,   6: C,   7: Dm,  8: A7,  9: Dm, 10: Gm, 11: A7, 12: D maj (Picardy)
    lh_patterns = [
        (38, [50, 53, 57]), # 1: Dm
        (33, [49, 52, 57]), # 2: A7
        (38, [50, 53, 57]), # 3: Dm
        (36, [48, 52, 55]), # 4: C
        (41, [53, 57, 60]), # 5: F
        (36, [48, 52, 55]), # 6: C
        (38, [50, 53, 57]), # 7: Dm
        (33, [49, 52, 57]), # 8: A7
        (38, [50, 53, 57]), # 9: Dm
        (34, [50, 55, 58]), # 10: Gm/Bb
        (33, [49, 52, 57]), # 11: A7
        (26, [38, 50, 54, 57, 62]), # 12: D major (Picardy Third!)
    ]
    
    for bar_num, (bass_root, chord_triad) in enumerate(lh_patterns, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        if bar_num < 12:
            # Resonant deep bass note on Beat 1
            notes.append((t_b, dur_s(2.8, bs), bass_root, 0.82))
            # Flowing broken arpeggio (Alberti wave) on beats 1.5, 2.0, 2.5, 3.0
            step8 = bs / 2.0
            for i in range(1, 6):
                p = chord_triad[(i - 1) % len(chord_triad)]
                notes.append((t_b + i * step8, dur_s(1.2, bs), p, 0.55 + (0.04 if i % 2 == 0 else 0)))
        else:
            # Bar 12 Final deep arpeggiated major chord
            notes.extend(piano_arpeggio([bass_root] + chord_triad, t_b, base_vel=0.88, step_s=0.06, dur_beats=4.5, beat_sec=bs))
            
    # Right Hand: Noble, singing cantilena with Baroque ornaments
    rh_melody = [
        # Bar 1: D5 -> E5
        (t_beat(1, 1.0, 3, bs), dur_s(1.8, bs), 62, 0.82),
        (t_beat(1, 3.0, 3, bs), dur_s(0.9, bs), 64, 0.72),
        # Bar 2: F5
        (t_beat(2, 1.0, 3, bs), dur_s(2.8, bs), 65, 0.85),
        # Bar 3: E5 -> D5
        (t_beat(3, 1.0, 3, bs), dur_s(1.8, bs), 64, 0.78),
        (t_beat(3, 3.0, 3, bs), dur_s(0.9, bs), 62, 0.70),
        # Bar 4: C5
        (t_beat(4, 1.0, 3, bs), dur_s(2.8, bs), 60, 0.80),
        # Bar 5: F5 -> G5
        (t_beat(5, 1.0, 3, bs), dur_s(1.8, bs), 65, 0.84),
        (t_beat(5, 3.0, 3, bs), dur_s(0.9, bs), 67, 0.74),
        # Bar 6: A5 (climax)
        (t_beat(6, 1.0, 3, bs), dur_s(2.8, bs), 69, 0.90),
        # Bar 7: G5 -> F5 -> E5
        (t_beat(7, 1.0, 3, bs), dur_s(1.4, bs), 67, 0.80),
        (t_beat(7, 2.5, 3, bs), dur_s(0.5, bs), 65, 0.72),
        (t_beat(7, 3.0, 3, bs), dur_s(0.9, bs), 64, 0.70),
        # Bar 8: C#5 (leading tone with ornament)
        (t_beat(8, 1.0, 3, bs), dur_s(1.8, bs), 61, 0.82),
        (t_beat(8, 2.8, 3, bs), dur_s(0.4, bs), 62, 0.70),
        (t_beat(8, 3.2, 3, bs), dur_s(0.6, bs), 61, 0.68),
        # Bar 9: D5
        (t_beat(9, 1.0, 3, bs), dur_s(2.8, bs), 62, 0.78),
        # Bar 10: Bb5 soaring tender leap
        (t_beat(10, 1.0, 3, bs), dur_s(1.8, bs), 70, 0.88),
        (t_beat(10, 3.0, 3, bs), dur_s(0.9, bs), 69, 0.76),
        # Bar 11: G5 -> E5 -> C#5 cadence
        (t_beat(11, 1.0, 3, bs), dur_s(1.0, bs), 67, 0.78),
        (t_beat(11, 2.0, 3, bs), dur_s(1.0, bs), 64, 0.74),
        (t_beat(11, 3.0, 3, bs), dur_s(0.9, bs), 61, 0.70),
        # Bar 12: F#5 (Major Picardy Third resolution)
        (t_beat(12, 1.0, 3, bs), dur_s(4.5, bs), 66, 0.80),
    ]
    notes.extend(rh_melody)
    return notes, "La Folia Noble in D Minor", bpm, (3, 4)

# 2. PASSACAGLIA DOLOROSA (C minor, 50 BPM, 3/4 meter)
def compose_slow_passacaglia() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 50
    bs = 60.0 / bpm # 1.200s
    notes = []
    
    # 11 bars in 3/4 @ 50 BPM = 39.6s (+ 5s tail = 44.6s)
    # Ground Bass: C2 -> Bb1 -> Ab1 -> G1 with weeping 4-3 and 7-6 suspensions
    ground_cycles = [
        (36, [48, 51, 55]), # 1: C2
        (34, [46, 50, 53]), # 2: Bb1
        (32, [44, 48, 51]), # 3: Ab1
        (31, [43, 47, 50]), # 4: G1
        (36, [48, 51, 55]), # 5: C2
        (34, [46, 50, 53]), # 6: Bb1
        (32, [44, 48, 51]), # 7: Ab1
        (31, [43, 47, 50]), # 8: G1
        (36, [48, 51, 55]), # 9: C2
        (31, [43, 47, 50]), # 10: G1
        (24, [36, 48, 52, 55, 60]), # 11: C major Picardy
    ]
    
    for bar_num, (bass_root, chord_triad) in enumerate(ground_cycles, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        if bar_num < 11:
            notes.append((t_b, dur_s(2.8, bs), bass_root, 0.84))
            # Undulating 8th notes
            step8 = bs / 2.0
            for i in range(1, 6):
                p = chord_triad[(i - 1) % len(chord_triad)]
                notes.append((t_b + i * step8, dur_s(1.2, bs), p, 0.54))
        else:
            notes.extend(piano_arpeggio([bass_root] + chord_triad, t_b, base_vel=0.86, step_s=0.06, dur_beats=4.5, beat_sec=bs))
            
    # Suspensions in Right Hand (4-3 suspension: F -> Eb; Eb -> D; D -> C; C -> B)
    rh_suspensions = [
        # Bar 1: F5 -> Eb5
        (t_beat(1, 1.0, 3, bs), dur_s(1.5, bs), 65, 0.84),
        (t_beat(1, 2.5, 3, bs), dur_s(1.4, bs), 63, 0.75),
        # Bar 2: Eb5 -> D5
        (t_beat(2, 1.0, 3, bs), dur_s(1.5, bs), 63, 0.80),
        (t_beat(2, 2.5, 3, bs), dur_s(1.4, bs), 62, 0.72),
        # Bar 3: D5 -> C5
        (t_beat(3, 1.0, 3, bs), dur_s(1.5, bs), 62, 0.78),
        (t_beat(3, 2.5, 3, bs), dur_s(1.4, bs), 60, 0.70),
        # Bar 4: C5 -> B4
        (t_beat(4, 1.0, 3, bs), dur_s(1.5, bs), 60, 0.82),
        (t_beat(4, 2.5, 3, bs), dur_s(1.4, bs), 59, 0.72),
        # Bars 5-8: Higher Octave Cantilena
        (t_beat(5, 1.0, 3, bs), dur_s(1.8, bs), 72, 0.88),
        (t_beat(5, 3.0, 3, bs), dur_s(0.9, bs), 70, 0.76),
        (t_beat(6, 1.0, 3, bs), dur_s(1.8, bs), 70, 0.85),
        (t_beat(6, 3.0, 3, bs), dur_s(0.9, bs), 68, 0.74),
        (t_beat(7, 1.0, 3, bs), dur_s(1.8, bs), 68, 0.82),
        (t_beat(7, 3.0, 3, bs), dur_s(0.9, bs), 67, 0.72),
        (t_beat(8, 1.0, 3, bs), dur_s(1.8, bs), 67, 0.85),
        (t_beat(8, 3.0, 3, bs), dur_s(0.9, bs), 65, 0.72),
        # Bar 9-10: Pre-cadence
        (t_beat(9, 1.0, 3, bs), dur_s(2.8, bs), 63, 0.78),
        (t_beat(10, 1.0, 3, bs), dur_s(2.8, bs), 62, 0.75),
        # Bar 11: E5 (Picardy Third Resolution)
        (t_beat(11, 1.0, 3, bs), dur_s(4.5, bs), 64, 0.80),
    ]
    notes.extend(rh_suspensions)
    return notes, "Passacaglia Dolorosa in C Minor", bpm, (3, 4)

# 3. CHACONNE GRAVE (G minor, 52 BPM, 3/4 meter)
def compose_slow_chaconne() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 52
    bs = 60.0 / bpm # 1.154s
    notes = []
    
    # 12 bars in 3/4 @ 52 BPM = 41.5s (+ 5s tail = 46.5s)
    # Stressed 2nd beat with rolling arpeggio cords
    chords_seq = [
        (43, [55, 58, 62, 67]),     # 1: Gm
        (42, [54, 57, 62, 66]),     # 2: D/F#
        (40, [52, 55, 58, 64]),     # 3: Edim/G
        (38, [50, 54, 57, 62]),     # 4: D7
        (39, [51, 55, 58, 63]),     # 5: Ebmaj7
        (38, [50, 53, 57, 62]),     # 6: Dm7
        (36, [48, 51, 55, 60]),     # 7: Cm
        (38, [50, 54, 57, 62]),     # 8: D7
        (43, [55, 58, 62, 67]),     # 9: Gm
        (39, [51, 55, 58, 63]),     # 10: Eb
        (38, [50, 54, 57, 62]),     # 11: D7
        (31, [43, 50, 55, 59, 67]), # 12: G major Picardy
    ]
    
    for bar_num, (bass_pitch, chord_pitches) in enumerate(chords_seq, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        # Beat 1: Firm deep bass
        notes.append((t_b, dur_s(1.0, bs), bass_pitch, 0.82))
        # Beat 2: Accentuated rolled chord (Chaconne signature)
        notes.extend(piano_arpeggio(chord_pitches, t_b + dur_s(1.0, bs), base_vel=0.76, step_s=0.04, dur_beats=1.8, beat_sec=bs))
        
    return notes, "Chaconne Grave in G Minor", bpm, (3, 4)

# 4. SARABANDE TRISTE (D minor, 50 BPM, 3/4 meter)
def compose_slow_sarabande() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 50
    bs = 60.0 / bpm # 1.200s
    notes = []
    
    # 11 bars in 3/4 @ 50 BPM = 39.6s (+ 5s tail = 44.6s)
    # Slow majestic Spanish Sarabande (Handel spirit) with prolonged singing 2nd beat
    sarabande_bars = [
        (38, [50, 53, 57], 62), # 1: Dm (melody D4)
        (37, [49, 52, 57], 61), # 2: A/C# (melody C#4)
        (38, [50, 53, 57], 62), # 3: Dm (melody D4)
        (35, [47, 50, 55], 67), # 4: Gm (melody G4)
        (36, [48, 52, 55], 65), # 5: C (melody F4)
        (33, [45, 48, 53], 64), # 6: F (melody E4)
        (34, [46, 50, 53], 65), # 7: Bb (melody F4)
        (40, [46, 49, 52], 64), # 8: Edim (melody E4)
        (33, [45, 49, 52], 61), # 9: A7 (melody C#4)
        (38, [50, 53, 57], 62), # 10: Dm (melody D4)
        (26, [38, 50, 54, 57, 66], 66), # 11: D major Picardy
    ]
    
    for bar_num, (bass_p, chord_ps, mel_p) in enumerate(sarabande_bars, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        # Beat 1: Bass note
        notes.append((t_b, dur_s(1.0, bs), bass_p, 0.80))
        # Beat 2: Prolonged singing chord + melody
        full_ch = chord_ps + [mel_p + 12]
        notes.extend(piano_arpeggio(full_ch, t_b + dur_s(1.0, bs), base_vel=0.78, step_s=0.038, dur_beats=1.9, beat_sec=bs))
        # Delicate ornament on beat 3 of bars 2, 4, 8
        if bar_num in [2, 4, 8]:
            notes.append((t_b + dur_s(2.6, bs), dur_s(0.35, bs), mel_p + 13, 0.65))
            notes.append((t_b + dur_s(2.8, bs), dur_s(0.35, bs), mel_p + 12, 0.68))
            
    return notes, "Sarabande Triste in D Minor", bpm, (3, 4)

# 5. DIDO'S LAMENT (G minor, 52 BPM, 4/4 meter)
def compose_slow_dido_lament() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 52
    bs = 60.0 / bpm # 1.154s
    notes = []
    
    # 9 bars of 4/4 @ 52 BPM = 41.5s (+ 5s tail = 46.5s)
    # Passus Duriusculus chromatic ground bass: G1 -> F#1 -> F1 -> E1 -> Eb1 -> D1
    chrom_ground = [
        (31, [43, 46, 50, 55]), # 1: G1
        (30, [42, 45, 50, 54]), # 2: F#1
        (29, [41, 46, 50, 53]), # 3: F1
        (28, [40, 46, 49, 52]), # 4: E1
        (27, [39, 46, 51, 55]), # 5: Eb1
        (26, [38, 45, 50, 54]), # 6: D1
        (31, [43, 46, 50, 55]), # 7: G1
        (26, [38, 45, 50, 54]), # 8: D1
        (19, [31, 43, 50, 55, 59]), # 9: G major
    ]
    
    for bar_num, (bp, ch) in enumerate(chrom_ground, start=1):
        t_b = (bar_num - 1) * 4.0 * bs
        # Deep bass
        notes.append((t_b, dur_s(3.8, bs), bp, 0.85))
        # Flowing arpeggio accompaniment
        notes.extend(piano_arpeggio(ch, t_b + dur_s(0.5, bs), base_vel=0.58, step_s=0.045, dur_beats=3.2, beat_sec=bs))
        
    # Weeping Downward Sighs (Melody in Right Hand)
    rh_sighs = [
        (t_beat(1, 2.0, 4, bs), dur_s(2.8, bs), 67, 0.80), # G4
        (t_beat(2, 1.0, 4, bs), dur_s(1.8, bs), 68, 0.85), # Ab4 (painful minor 9th tension!)
        (t_beat(2, 3.0, 4, bs), dur_s(1.8, bs), 67, 0.74), # G4 resolution
        (t_beat(3, 1.0, 4, bs), dur_s(1.8, bs), 70, 0.84), # Bb4
        (t_beat(3, 3.0, 4, bs), dur_s(1.8, bs), 69, 0.74), # A4 resolution
        (t_beat(4, 1.0, 4, bs), dur_s(1.8, bs), 67, 0.80), # G4
        (t_beat(4, 3.0, 4, bs), dur_s(1.8, bs), 66, 0.72), # F#4
        (t_beat(5, 1.0, 4, bs), dur_s(1.8, bs), 65, 0.82), # F4
        (t_beat(5, 3.0, 4, bs), dur_s(1.8, bs), 63, 0.70), # Eb4
        (t_beat(6, 1.0, 4, bs), dur_s(1.8, bs), 62, 0.80), # D4
        (t_beat(6, 3.0, 4, bs), dur_s(1.8, bs), 61, 0.72), # C#4
        (t_beat(7, 1.0, 4, bs), dur_s(3.8, bs), 67, 0.82), # G4
        (t_beat(8, 1.0, 4, bs), dur_s(1.8, bs), 66, 0.76), # F#4
        (t_beat(8, 3.0, 4, bs), dur_s(1.8, bs), 62, 0.72), # D4
        (t_beat(9, 1.0, 4, bs), dur_s(4.5, bs), 67, 0.80), # G4 final
    ]
    notes.extend(rh_sighs)
    return notes, "Dido's Lament in G Minor (Passus Duriusculus)", bpm, (4, 4)

# 6. SICILIANA MELANCHOLICA (A minor, 56 BPM, 6/8 meter)
def compose_slow_siciliana() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 56
    # In 6/8 @ 56 BPM, dotted quarter = 1.071s, 1 eighth = 0.357s, 1 bar = 2.143s
    bar_sec = 60.0 / bpm * 2.0 # 2.143s
    eighth_sec = bar_sec / 6.0
    notes = []
    
    # 20 bars in 6/8 = 42.8s (+ 4.5s tail = 47.3s)
    # Tender, rocking dotted rhythm (Bach Erbarme dich spirit)
    chords_68 = [
        (33, [45, 52, 57, 60]), # 1: Am
        (28, [40, 47, 52, 56]), # 2: E7
        (33, [45, 52, 57, 60]), # 3: Am
        (26, [38, 50, 53, 57]), # 4: Dm
        (23, [35, 47, 50, 53]), # 5: Bdim
        (28, [40, 47, 52, 56]), # 6: E7
        (33, [45, 52, 57, 60]), # 7: Am
        (29, [41, 48, 53, 57]), # 8: F
        (26, [38, 50, 53, 57]), # 9: Dm
        (23, [35, 47, 50, 53]), # 10: Bdim
        (28, [40, 47, 52, 56]), # 11: E7
        (33, [45, 52, 57, 60]), # 12: Am
        (29, [41, 48, 53, 57]), # 13: F
        (26, [38, 50, 53, 57]), # 14: Dm
        (28, [40, 47, 52, 56]), # 15: E7
        (33, [45, 52, 57, 60]), # 16: Am
        (26, [38, 50, 53, 57]), # 17: Dm
        (28, [40, 47, 52, 56]), # 18: E7
        (33, [45, 52, 57, 60]), # 19: Am
        (21, [33, 45, 52, 57, 61]), # 20: A major Picardy
    ]
    
    for i, (bp, ch) in enumerate(chords_68):
        t_b = i * bar_sec
        # Bass on beat 1 and beat 2 (dotted quarters)
        notes.append((t_b, bar_sec * 0.45, bp, 0.78))
        notes.append((t_b + bar_sec * 0.5, bar_sec * 0.45, bp + 7, 0.65))
        # Gentle inner accompaniment arpeggio
        notes.extend(piano_arpeggio(ch, t_b + 0.1, base_vel=0.52, step_s=0.04, dur_beats=1.5))
        
    # Cantilena Melody in Right Hand (dotted 8th + 16th + 8th rocking rhythm)
    for b in range(19):
        t_b = b * bar_sec
        mel_base = 69 + ((b * 3) % 7) # In A minor scale
        notes.append((t_b, eighth_sec * 2.8, mel_base, 0.82))
        notes.append((t_b + eighth_sec * 3.0, eighth_sec * 0.9, mel_base + 2, 0.70))
        notes.append((t_b + eighth_sec * 4.0, eighth_sec * 1.8, mel_base + 3, 0.85))
        
    # Final Bar 20: Picardy third
    notes.append((19 * bar_sec, 4.5, 69, 0.80))
    return notes, "Siciliana Melancholica in A Minor", bpm, (6, 8)

# 7. ADAGIO CANTABILE / BAROQUE ARIA (F minor, 50 BPM, 4/4 meter)
def compose_slow_adagio_aria() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 50
    bs = 60.0 / bpm # 1.200s
    notes = []
    
    # 9 bars in 4/4 @ 50 BPM = 43.2s (+ 5s tail = 48.2s)
    # Warm undulating Alberti bass + long arching vocal melody (Vivaldi Winter Largo spirit)
    harmonies = [
        (29, [41, 44, 48]), # 1: Fm
        (24, [36, 43, 48]), # 2: C
        (29, [41, 44, 48]), # 3: Fm
        (22, [34, 41, 46]), # 4: Bbm
        (20, [32, 39, 44]), # 5: Ab
        (19, [31, 38, 43]), # 6: Gdim
        (24, [36, 43, 46]), # 7: C7
        (29, [41, 44, 48]), # 8: Fm
        (17, [29, 41, 45, 48, 53]), # 9: F major Picardy
    ]
    
    for bar_num, (bp, ch) in enumerate(harmonies, start=1):
        t_b = (bar_num - 1) * 4.0 * bs
        if bar_num < 9:
            # Resonant bass note
            notes.append((t_b, dur_s(3.8, bs), bp, 0.82))
            # Gentle undulating Alberti pattern in 8th notes (Low - High - Mid - High)
            step8 = bs / 2.0
            for i in range(8):
                # Alberti pattern indices: 0, 2, 1, 2
                idx = [0, 2, 1, 2][i % 4]
                p = ch[idx % len(ch)]
                notes.append((t_b + i * step8, dur_s(1.0, bs), p, 0.52 + (0.04 if i % 2 == 0 else 0)))
        else:
            notes.extend(piano_arpeggio([bp] + ch, t_b, base_vel=0.86, step_s=0.06, dur_beats=4.5, beat_sec=bs))
            
    # Singing Arching Cantilena
    aria_melody = [
        # Bar 1
        (t_beat(1, 1.5, 4, bs), dur_s(2.2, bs), 65, 0.84), # F4
        (t_beat(1, 3.5, 4, bs), dur_s(1.2, bs), 68, 0.88), # Ab4
        # Bar 2
        (t_beat(2, 1.0, 4, bs), dur_s(2.0, bs), 67, 0.82), # G4
        (t_beat(2, 3.0, 4, bs), dur_s(1.8, bs), 60, 0.78), # C4
        # Bar 3
        (t_beat(3, 1.0, 4, bs), dur_s(1.8, bs), 65, 0.85), # F4
        (t_beat(3, 3.0, 4, bs), dur_s(1.8, bs), 72, 0.90), # C5 soaring
        # Bar 4
        (t_beat(4, 1.0, 4, bs), dur_s(1.8, bs), 70, 0.86), # Bb4
        (t_beat(4, 3.0, 4, bs), dur_s(1.8, bs), 68, 0.80), # Ab4
        # Bar 5
        (t_beat(5, 1.0, 4, bs), dur_s(2.0, bs), 68, 0.84), # Ab4
        (t_beat(5, 3.0, 4, bs), dur_s(1.8, bs), 67, 0.78), # G4
        # Bar 6
        (t_beat(6, 1.0, 4, bs), dur_s(2.0, bs), 65, 0.82), # F4
        (t_beat(6, 3.0, 4, bs), dur_s(1.8, bs), 64, 0.78), # E4
        # Bar 7
        (t_beat(7, 1.0, 4, bs), dur_s(2.0, bs), 65, 0.84), # F4
        (t_beat(7, 3.0, 4, bs), dur_s(1.8, bs), 67, 0.80), # G4
        # Bar 8
        (t_beat(8, 1.0, 4, bs), dur_s(3.8, bs), 65, 0.86), # F4
        # Bar 9
        (t_beat(9, 1.0, 4, bs), dur_s(4.5, bs), 65, 0.82), # F4
    ]
    notes.extend(aria_melody)
    return notes, "Adagio Cantabile in F Minor (Baroque Aria)", bpm, (4, 4)

# 8. TWO-PART INVENTION (Lento Espressivo, C minor, 58 BPM, 4/4 meter)
def compose_slow_invention() -> Tuple[List[Tuple[float, float, int, float]], str, int, Tuple[int, int]]:
    bpm = 58
    bs = 60.0 / bpm # 1.034s
    notes = []
    
    # 10 bars in 4/4 @ 58 BPM = 41.4s (+ 5s tail = 46.4s)
    # Contrapuntal dialogue between upper and lower voices (Bach Invention style)
    # Voice 1 (Upper) introduces subject in Bar 1
    # Subject: C4 -> Eb4 -> D4 -> C4 -> B3 -> C4 -> D4 -> G3
    notes.extend([
        (t_beat(1, 1.0, 4, bs), dur_s(1.0, bs), 60, 0.84), # C4
        (t_beat(1, 2.0, 4, bs), dur_s(1.0, bs), 63, 0.86), # Eb4
        (t_beat(1, 3.0, 4, bs), dur_s(1.0, bs), 62, 0.80), # D4
        (t_beat(1, 4.0, 4, bs), dur_s(1.0, bs), 60, 0.78), # C4
    ])
    
    # Voice 2 (Lower) enters in Bar 2 an octave lower!
    notes.extend([
        (t_beat(2, 1.0, 4, bs), dur_s(1.0, bs), 48, 0.82), # C3
        (t_beat(2, 2.0, 4, bs), dur_s(1.0, bs), 51, 0.84), # Eb3
        (t_beat(2, 3.0, 4, bs), dur_s(1.0, bs), 50, 0.78), # D3
        (t_beat(2, 4.0, 4, bs), dur_s(1.0, bs), 48, 0.76), # C3
    ])
    # Meanwhile Voice 1 plays countersubject in Bar 2:
    notes.extend([
        (t_beat(2, 1.0, 4, bs), dur_s(1.0, bs), 59, 0.78), # B3
        (t_beat(2, 2.0, 4, bs), dur_s(1.0, bs), 60, 0.80), # C4
        (t_beat(2, 3.0, 4, bs), dur_s(1.0, bs), 62, 0.82), # D4
        (t_beat(2, 4.0, 4, bs), dur_s(1.0, bs), 55, 0.74), # G3
    ])
    
    # Bars 3 to 9: Contrapuntal sequences with beautiful suspensions
    for bar_num in range(3, 10):
        t_b = (bar_num - 1) * 4.0 * bs
        shift = (bar_num % 3) * 2
        # Upper Voice
        notes.append((t_b, dur_s(1.5, bs), 63 + shift, 0.82))
        notes.append((t_b + dur_s(1.5, bs), dur_s(1.5, bs), 62 + shift, 0.78))
        notes.append((t_b + dur_s(3.0, bs), dur_s(1.0, bs), 60 + shift, 0.75))
        # Lower Voice
        notes.append((t_b, dur_s(2.0, bs), 48 + shift, 0.76))
        notes.append((t_b + dur_s(2.0, bs), dur_s(2.0, bs), 43 + shift, 0.74))
        
    # Bar 10: Cadential Resolution to C Major (Picardy Third)
    t_fin = 9 * 4.0 * bs
    notes.extend(piano_arpeggio([24, 36, 48, 52, 55, 64], t_fin, base_vel=0.88, step_s=0.06, dur_beats=4.5, beat_sec=bs))
    
    return notes, "Two-Part Invention in C Minor (Lento Espressivo)", bpm, (4, 4)

# ---------------------------------------------------------------------------
# RENDERING PIPELINE FOR THE 8 MASTERPIECES
# ---------------------------------------------------------------------------

MASTERPIECES = [
    compose_slow_folia,
    compose_slow_passacaglia,
    compose_slow_chaconne,
    compose_slow_sarabande,
    compose_slow_dido_lament,
    compose_slow_siciliana,
    compose_slow_adagio_aria,
    compose_slow_invention,
]

def render_track(notes: List[Tuple[float, float, int, float]], title: str, bpm: int,
                 meter: Tuple[int, int], output_prefix: str) -> Tuple[str, str]:
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
        # Audio rendering via Yamaha C5 Concert Grand
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
    
    midi_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.mid")
    mid.save(midi_path)
    
    # Apply warm acoustic piano room reverb
    final_audio = apply_concert_grand_reverb(stereo_buf, room_size=0.82, wet=0.22)
    wav_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.wav")
    mp3_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.mp3")
    
    sf.write(wav_path, final_audio, SR, subtype='PCM_24')
    
    actual_sec = len(final_audio) / SR
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={title}",
        "-metadata", "artist=Concert Grand Piano (Yamaha C5)",
        "-metadata", "album=Noble Slow Baroque (50-60 BPM)",
        "-metadata", f"genre=Slow Baroque Piano ({bpm} BPM)",
        "-metadata", f"comment=Noble, melodious Baroque loop ({actual_sec:.1f}s)",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return midi_path, mp3_path

def main():
    print("=" * 75)
    print("NOBLE SLOW BAROQUE PIANO FACTORY (50 - 60 BPM, MINOR KEYS)")
    print("Instrument: Yamaha C5 Concert Grand Piano (Salamander Grand)")
    print(f"Output directory: {OUTPUT_DIR}")
    print("=" * 75)
    
    load_salamander_samples()
    print("Salamander Concert Grand Piano samples loaded into RAM!\n")
    
    t_start = time.time()
    for idx, comp_fn in enumerate(MASTERPIECES, start=1):
        notes, title, bpm, meter = comp_fn()
        prefix = f"slow_baroque_{idx:02d}"
        print(f"[{idx:02d}/8] Rendering: {title} ({bpm} BPM, {meter[0]}/{meter[1]})...")
        t0 = time.time()
        midi_p, mp3_p = render_track(notes, title, bpm, meter, prefix)
        dt = time.time() - t0
        print(f"   -> Rendered in {dt:.1f}s | MP3: {os.path.basename(mp3_p)}")
        
    total_dt = time.time() - t_start
    print("\n" + "=" * 75)
    print(f"SUCCESS: All 8 Slow Baroque Piano Masterpieces generated in {total_dt:.1f}s!")
    print(f"Location: {OUTPUT_DIR}")
    print("=" * 75)

if __name__ == "__main__":
    main()
