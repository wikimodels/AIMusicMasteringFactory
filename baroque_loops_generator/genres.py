"""
Genre-Specific Rhythmic Figures, Melodic DNA, and Metric Phrasing
Defines authentic Baroque & Renaissance motifs for Pavane, Ciaccona, Galliard,
Toccata, Lamento, Siciliana, Sarabande, La Folia, Canzona, Ricercar, La Monica, Spagnoletta.
"""

from typing import List, Dict, Any, Tuple
from baroque_loops_generator.models import NoteEvent, ChordDegrees
from baroque_loops_generator.theory import octave_fit, midi_to_note_name

def generate_genre_notes(
    form_code: str,
    bar_idx: int,
    num_bars: int,
    b_st: int,
    bar_len: int,
    meter: str,
    cd: ChordDegrees,
    dramaturgy_phase: str,
    track_seed: int = 1
) -> List[NoteEvent]:
    """
    Generates notes reflecting the true rhythmic, metric, and melodic DNA of the specific genre.
    """
    notes: List[NoteEvent] = []
    bp = cd.bass_pitch
    p_r, p_3, p_5 = cd.inner_pitches[0], cd.inner_pitches[1], cd.inner_pitches[2]
    s_r, s_3, s_5 = cd.soprano_pitches[0], cd.soprano_pitches[1], cd.soprano_pitches[2]
    s_8 = octave_fit(s_r + 12, 'soprano')
    s_sus = cd.suspended_pitch
    b_fifth = octave_fit(p_5, 'bass')
    if b_fifth == bp:
        b_fifth = octave_fit(p_3, 'bass')

    # Dramaturgic velocity shaping
    if dramaturgy_phase == 'exposition':
        vel_b, vel_m, vel_s = 0.76, 0.65, 0.78
    elif dramaturgy_phase == 'development':
        vel_b, vel_m, vel_s = 0.82, 0.70, 0.84
    elif dramaturgy_phase == 'climax':
        vel_b, vel_m, vel_s = 0.88, 0.75, 0.92
    else: # resolution
        vel_b, vel_m, vel_s = 0.74, 0.62, 0.75

    def add(step_offset: int, pitch: int, dur: str, vel: float):
        notes.append(NoteEvent(
            step=b_st + step_offset,
            note=midi_to_note_name(pitch),
            duration=dur,
            velocity=vel,
            _p=pitch
        ))

    # =========================================================================
    # 1. PAVANE (4/4, Stately Renaissance Processional)
    # =========================================================================
    if form_code == 'Pavane':
        # Solemn, noble marching bass: half notes on beats 1 and 3
        add(0, bp, '2n', vel_b)
        add(8, b_fifth, '2n', vel_b - 0.04)
        # Inner accompaniment
        add(4, p_3, '4n', vel_m)
        add(12, p_5, '4n', vel_m - 0.02)
        
        # Renaissance Melodic Contours (varied by track_seed)
        pavane_contour = (track_seed + (bar_idx // 2)) % 3
        if bar_idx % 2 == 0:
            if pavane_contour == 0:
                # Stately 2n - 4n - 4n phrase (Root -> 3rd -> 5th)
                add(0, s_r if dramaturgy_phase != 'climax' else s_5, '2n', vel_s)
                add(8, s_3, '4n', vel_s - 0.02)
                add(12, s_5 if dramaturgy_phase != 'climax' else s_8, '4n', vel_s + 0.03)
            elif pavane_contour == 1:
                # Heroic rising arch (3rd -> 5th -> Octave)
                add(0, s_3 if dramaturgy_phase != 'climax' else s_5, '2n', vel_s + 0.02)
                add(8, s_5, '4n', vel_s)
                add(12, s_8 if dramaturgy_phase != 'climax' else s_5, '4n', vel_s + 0.04)
            else:
                # Noble solemn descent (5th -> 3rd -> Root)
                add(0, s_5 if dramaturgy_phase != 'climax' else s_8, '2n', vel_s + 0.03)
                add(8, s_3, '4n', vel_s - 0.02)
                add(12, s_r, '4n', vel_s - 0.04)
        else:
            if pavane_contour == 0:
                # Lachrimae sigh 4n. - 8n - 2n with suspension
                add(0, s_sus, '4n.', vel_s + 0.04)     # 4th suspension
                add(6, s_3, '8n', vel_s - 0.04)        # resolution to 3rd
                add(8, s_5 if dramaturgy_phase != 'climax' else s_8, '2n', vel_s + 0.05)
            elif pavane_contour == 1:
                # Passing cambiata figure
                add(0, s_5, '4n.', vel_s + 0.03)
                add(6, s_3, '8n', vel_s)
                add(8, s_r, '2n', vel_s - 0.02)
            else:
                # Deep suspended cadence
                add(0, s_sus, '2n', vel_s + 0.05)
                add(8, s_3, '2n', vel_s)

    # =========================================================================
    # 2. CIACCONA / PASSACAGLIA (3/4, Continuous Variation Ground)
    # =========================================================================
    elif form_code in ['Ciaccona', 'Passacaglia']:
        # Characteristic Sarabande 2nd-beat accent
        add(0, bp, '4n', vel_b)
        add(4, b_fifth, '2n', vel_b + 0.04) # held across beats 2 and 3
        
        ciaccona_var = (track_seed + bar_idx) % 3
        
        # 4 variation phases across the ground:
        if dramaturgy_phase == 'exposition':
            if ciaccona_var == 0:
                add(0, s_r, '4n', vel_s)
                add(4, s_5, '2n', vel_s + 0.06)
            elif ciaccona_var == 1:
                add(0, s_3, '4n', vel_s + 0.03)
                add(4, s_8, '2n', vel_s + 0.07)
            else:
                add(0, s_5, '4n', vel_s + 0.04)
                add(4, s_3, '2n', vel_s + 0.02)
            add(0, p_3, '4n', vel_m)
        elif dramaturgy_phase == 'development':
            # Flowing Circulatio 8n - 8n - 4n. - 8n
            if ciaccona_var == 0:
                add(0, s_r, '8n', vel_s)
                add(2, s_3, '8n', vel_s - 0.02)
                add(4, s_5, '4n.', vel_s + 0.05)
                add(10, s_3, '8n', vel_s - 0.03)
            elif ciaccona_var == 1:
                add(0, s_5, '8n', vel_s + 0.03)
                add(2, s_8, '8n', vel_s + 0.05)
                add(4, s_5, '4n.', vel_s + 0.02)
                add(10, s_3, '8n', vel_s - 0.02)
            else:
                add(0, s_3, '8n', vel_s)
                add(2, s_r, '8n', vel_s - 0.02)
                add(4, s_3, '4n.', vel_s + 0.03)
                add(10, s_5, '8n', vel_s + 0.04)
            add(2, p_r, '8n', vel_m)
            add(8, p_5, '4n', vel_m)
        elif dramaturgy_phase == 'climax':
            # Phase 3: Fiery division with 16th passaggi
            if ciaccona_var == 0:
                add(0, s_3, '8n', vel_s)
                add(2, s_5, '8n', vel_s + 0.02)
                add(4, s_8, '4n', vel_s + 0.08)
                add(8, s_5, '16n', vel_s + 0.04)
                add(10, s_3, '16n', vel_s)
            elif ciaccona_var == 1:
                add(0, s_5, '8n', vel_s + 0.04)
                add(2, s_8, '8n', vel_s + 0.08)
                add(4, s_5, '4n', vel_s + 0.03)
                add(8, s_3, '16n', vel_s)
                add(10, s_r, '16n', vel_s - 0.02)
            else:
                add(0, s_r, '8n', vel_s)
                add(2, s_3, '8n', vel_s + 0.02)
                add(4, s_5, '4n', vel_s + 0.06)
                add(8, s_8, '16n', vel_s + 0.07)
                add(10, s_5, '16n', vel_s + 0.03)
            add(4, p_r, '4n', vel_m)
        else: # resolution
            # Phase 4: Stately broad cadence with suspension
            add(0, s_sus, '4n', vel_s + 0.03)
            add(4, s_3, '2n', vel_s - 0.04)
            add(0, p_5, '4n', vel_m)

    # =========================================================================
    # 3. GALLIARD (3/4, Fast Leaping Dance with Hemiola)
    # =========================================================================
    elif form_code == 'Galliard':
        is_penultimate = (bar_idx == num_bars - 2)
        if is_penultimate:
            # THE FAMOUS HEMIOLA: two 3/4 bars felt as three 2/4 bars (2 + 2 + 2)
            add(0, bp, '2n', vel_b + 0.06)
            add(4, b_fifth, '2n', vel_b + 0.04)
            add(8, bp, '2n', vel_b + 0.06)
            add(0, s_5, '2n', vel_s + 0.06)
            add(4, s_sus, '2n', vel_s + 0.08)
            add(8, s_3, '2n', vel_s + 0.04)
        else:
            # Cinque Pas leaping rhythm: buoyant quarter staccato bass
            add(0, bp, '8n', vel_b + 0.04)
            add(4, b_fifth, '8n', vel_b)
            add(8, bp, '8n', vel_b + 0.02)
            galliard_var = (track_seed + bar_idx) % 3
            if bar_idx % 2 == 0:
                if galliard_var == 0:
                    add(0, s_r, '4n', vel_s)
                    add(4, s_3, '4n', vel_s + 0.04)
                    add(8, s_5 if dramaturgy_phase != 'climax' else s_8, '4n', vel_s + 0.06)
                elif galliard_var == 1:
                    add(0, s_3, '4n', vel_s + 0.02)
                    add(4, s_5, '4n', vel_s + 0.05)
                    add(8, s_8 if dramaturgy_phase != 'climax' else s_5, '4n', vel_s + 0.07)
                else:
                    add(0, s_5, '4n', vel_s + 0.04)
                    add(4, s_3, '4n', vel_s + 0.02)
                    add(8, s_r, '4n', vel_s)
            else:
                if galliard_var == 0:
                    add(0, s_5, '4n.', vel_s + 0.05)
                    add(6, s_3, '8n', vel_s - 0.02)
                    add(8, s_r, '4n', vel_s)
                elif galliard_var == 1:
                    add(0, s_8 if dramaturgy_phase == 'climax' else s_5, '4n.', vel_s + 0.06)
                    add(6, s_5, '8n', vel_s)
                    add(8, s_3, '4n', vel_s - 0.02)
                else:
                    add(0, s_3, '4n.', vel_s + 0.03)
                    add(6, s_r, '8n', vel_s - 0.04)
                    add(8, s_3, '4n', vel_s)
            add(4, p_5, '4n', vel_m)

    # =========================================================================
    # 4. CANZONA (4/4, Lively French Chanson with Dactylic Rhythm)
    # =========================================================================
    elif form_code == 'Canzona':
        # Dactylic theme motif: Long - Short - Short (4n - 8n - 8n)
        add(0, bp, '4n', vel_b)
        add(4, bp, '8n', vel_b - 0.03)
        add(6, b_fifth, '8n', vel_b - 0.03)
        add(8, bp, '2n', vel_b + 0.02)
        
        canzona_var = (track_seed + (bar_idx // 2)) % 3
        # Soprano dactyl motif with variable starting degree
        start_p = s_r if canzona_var == 0 else (s_3 if canzona_var == 1 else s_5)
        mid_p = s_3 if canzona_var == 0 else (s_5 if canzona_var == 1 else s_3)
        end_p = s_5 if canzona_var == 0 else (s_8 if canzona_var == 1 else s_r)
        
        add(0, start_p if dramaturgy_phase != 'climax' else s_5, '4n', vel_s + 0.05)
        add(4, mid_p, '8n', vel_s)
        add(6, end_p, '8n', vel_s + 0.02)
        if bar_idx % 2 == 0:
            add(8, s_8 if dramaturgy_phase == 'climax' else s_5, '2n', vel_s + 0.06)
        else:
            add(8, mid_p, '4n', vel_s)
            add(12, s_r, '4n', vel_s - 0.04)
        add(4, p_r, '4n', vel_m)
        add(8, p_5, '4n', vel_m)

    # =========================================================================
    # 5. TOCCATA (4/4, Stylus Phantasticus: Chords & Cascading 16ths)
    # =========================================================================
    elif form_code == 'Toccata':
        # Massive pedal bass
        add(0, bp, '1n', vel_b + 0.06)
        add(0, p_r, '2n', vel_m)
        add(0, p_5, '2n', vel_m)
        
        toccata_var = (track_seed + bar_idx) % 3
        if bar_idx % 2 == 0:
            # Sweeping Tirata cascade of 16ths in beats 2 & 3
            add(0, s_r, '4n', vel_s)
            if toccata_var == 0:
                run = [s_3, s_5, s_8, s_5]
            elif toccata_var == 1:
                run = [s_5, s_8, s_5, s_3]
            else:
                run = [s_r, s_3, s_5, s_8]
            for i in range(4):
                add(4 + i * 2, run[i % 4], '16n', vel_s + 0.04)
            add(12, s_8 if dramaturgy_phase == 'climax' else s_5, '4n', vel_s + 0.06)
        else:
            # Sustained expressive chords with suspensions
            add(0, s_sus, '4n.', vel_s + 0.06)
            add(6, s_3, '8n', vel_s - 0.04)
            add(8, s_5 if dramaturgy_phase != 'climax' else s_8, '2n', vel_s + 0.04)

    # =========================================================================
    # 6. LAMENTO (4/4, Grief-Stricken Aria with Suspiratio Pauses)
    # =========================================================================
    elif form_code == 'Lamento':
        # Slow bass descent
        add(0, bp, '2n', vel_b)
        add(8, b_fifth, '2n', vel_b - 0.04)
        
        lamento_var = (track_seed + bar_idx) % 3
        # Suspiratio: Step 0 is strictly SILENT (rhetorical sigh)
        if bar_idx % 2 == 0:
            susp_pitch = s_sus if lamento_var != 2 else s_5
            res_pitch = s_3 if lamento_var != 2 else s_r
            add(2, susp_pitch, '4n.', vel_s + 0.05) # weeping suspension entry
            add(8, res_pitch, '4n', vel_s - 0.05)    # downward sigh resolution
            add(4, p_r, '4n', vel_m)
        else:
            add(2, s_5 if dramaturgy_phase != 'climax' else s_8, '4n', vel_s + 0.04)
            add(6, s_3, '8n', vel_s - 0.03)
            add(8, s_r, '2n', vel_s - 0.06)
            add(4, p_5, '4n', vel_m)

    # =========================================================================
    # 7. SICILIANA (6/8, Pastoral Lilting Barcarolle)
    # =========================================================================
    elif form_code == 'Siciliana':
        # Bass on pulses 1 and 2 (steps 0 and 6)
        add(0, bp, '4n.', vel_b)
        add(6, b_fifth, '4n.', vel_b - 0.03)
        siciliana_var = (track_seed + bar_idx) % 3
        # Iconic dotted pastoral motif: 8n. + 16n + 8n
        p_start = s_r if siciliana_var == 0 else (s_3 if siciliana_var == 1 else s_5)
        p_mid = s_3 if siciliana_var == 0 else (s_5 if siciliana_var == 1 else s_3)
        p_end = s_5 if siciliana_var == 0 else (s_8 if siciliana_var == 1 else s_r)
        
        add(0, p_start, '8n.', vel_s)
        add(3, p_mid, '16n', vel_s - 0.04)
        add(4, p_end, '8n', vel_s + 0.02)
        add(6, s_8 if dramaturgy_phase == 'climax' else p_mid, '4n.', vel_s + 0.05)
        # Gentle boat-rocking inner accompaniment
        add(2, p_r, '8n', vel_m)
        add(4, p_3, '8n', vel_m)
        add(8, p_5, '8n', vel_m)
        add(10, p_3, '8n', vel_m)

    # =========================================================================
    # 8. SARABANDE (3/4, Grave Spanish Dance with Elongated Beat 2)
    # =========================================================================
    elif form_code == 'Sarabande':
        # Solemn bass step
        add(0, bp, '4n', vel_b)
        add(4, b_fifth, '2n', vel_b + 0.03)
        sarabande_var = (track_seed + bar_idx) % 3
        # Prolonged accented 2nd beat with silence on 3rd beat
        p_first = s_r if sarabande_var == 0 else (s_3 if sarabande_var == 1 else s_5)
        p_second = s_3 if sarabande_var == 0 else (s_5 if sarabande_var == 1 else s_8)
        add(0, p_first, '4n', vel_s)
        add(4, p_second if dramaturgy_phase != 'climax' else s_8, '2n', vel_s + 0.08)
        add(0, p_5, '4n', vel_m)
        add(4, p_3, '4n', vel_m + 0.02)

    # =========================================================================
    # 9. LA FOLIA (3/4, Historic Iberian Ground)
    # =========================================================================
    elif form_code == 'La_Folia':
        add(0, bp, '4n', vel_b)
        add(4, b_fifth, '2n', vel_b + 0.02)
        folia_var = (track_seed + (bar_idx // 2)) % 3
        if bar_idx % 2 == 0:
            if folia_var == 0:
                add(0, s_r, '4n', vel_s)
                add(4, s_5, '2n', vel_s + 0.06)
            elif folia_var == 1:
                add(0, s_3, '4n', vel_s + 0.03)
                add(4, s_8, '2n', vel_s + 0.08)
            else:
                add(0, s_5, '4n', vel_s + 0.04)
                add(4, s_3, '2n', vel_s + 0.02)
        else:
            add(0, s_3, '4n', vel_s)
            add(4, s_sus, '4n', vel_s + 0.04)
            add(8, s_3, '4n', vel_s - 0.03)
        add(4, p_r, '4n', vel_m)

    # =========================================================================
    # 10. RICERCAR (4/4, Severe Renaissance Imitative Polyphony)
    # =========================================================================
    elif form_code == 'Ricercar':
        # Staggered polyphonic voice entrances shifted by track_seed
        voice_order = (bar_idx + track_seed) % 3
        if voice_order == 0:
            add(0, bp, '2n', vel_b + 0.05)
            add(8, b_fifth, '2n', vel_b)
            add(4, s_r, '2n', vel_s)
        elif voice_order == 1:
            add(0, p_r, '2n', vel_m + 0.04)
            add(8, p_5, '2n', vel_m)
            add(4, bp, '2n', vel_b)
            add(8, s_5, '2n', vel_s)
        else:
            add(0, s_r, '2n', vel_s + 0.06)
            add(8, s_3, '2n', vel_s)
            add(4, p_3, '2n', vel_m)
            add(8, bp, '2n', vel_b)

    # =========================================================================
    # 11. LA MONICA & SPAGNOLETTA (4/4, Popular Renaissance Folk Song-Dances)
    # =========================================================================
    else:
        # Melodic folk song phrasing with buoyant quarter bass
        add(0, bp, '4n', vel_b)
        add(4, b_fifth, '4n', vel_b - 0.02)
        add(8, bp, '4n', vel_b + 0.02)
        add(12, b_fifth, '4n', vel_b - 0.02)
        folk_var = (track_seed + bar_idx) % 3
        if bar_idx % 2 == 0:
            # Phrase A: 4n. - 8n - 2n (Iconic La Monica / Spagnoletta cantilena)
            p_first = s_r if folk_var == 0 else (s_3 if folk_var == 1 else s_5)
            p_mid = s_3 if folk_var == 0 else (s_5 if folk_var == 1 else s_3)
            add(0, p_first, '4n.', vel_s + 0.03)
            add(6, p_mid, '8n', vel_s)
            add(8, s_5 if dramaturgy_phase != 'climax' else s_8, '2n', vel_s + 0.04)
        else:
            # Phrase B: 4n - 4n - 2n with melodic resolution
            p_first = s_5 if folk_var == 0 else (s_8 if folk_var == 1 else s_3)
            add(0, p_first, '4n', vel_s + 0.02)
            add(4, s_3, '4n', vel_s)
            add(8, s_r, '2n', vel_s - 0.03)
        add(4, p_5, '4n', vel_m)

    return notes
