"""
The 12 Authentic Keyboard Playing Styles & Textures (T01 - T12)
Modulates genre-specific motifs with historical Baroque keyboard articulations,
dynamics, ornaments, and polyphonic textures.
"""

from typing import List
from baroque_loops_generator.models import NoteEvent, ChordDegrees
from baroque_loops_generator.theory import midi_to_note_name, octave_fit
from baroque_loops_generator.genres import generate_genre_notes

def apply_texture(
    texture_code: str,
    bar_idx: int,
    num_bars: int,
    b_st: int,
    bar_len: int,
    meter: str,
    cd: ChordDegrees,
    dramaturgy_phase: str, # 'exposition', 'development', 'climax', 'resolution'
    form_code: str = 'Pavane',
    track_seed: int = 1
) -> List[NoteEvent]:
    """
    Blends the specific Genre DNA with the chosen Keyboard Playing Style T01-T12.
    """
    # 1. Obtain baseline genre-specific notes (metric pulse & thematic motif)
    base_notes = generate_genre_notes(
        form_code=form_code,
        bar_idx=bar_idx,
        num_bars=num_bars,
        b_st=b_st,
        bar_len=bar_len,
        meter=meter,
        cd=cd,
        dramaturgy_phase=dramaturgy_phase,
        track_seed=track_seed
    )
    
    notes: List[NoteEvent] = []
    bp = cd.bass_pitch
    p_r, p_3, p_5 = cd.inner_pitches[0], cd.inner_pitches[1], cd.inner_pitches[2]
    s_r, s_3, s_5 = cd.soprano_pitches[0], cd.soprano_pitches[1], cd.soprano_pitches[2]
    s_8 = octave_fit(s_r + 12, 'soprano')
    s_sus = cd.suspended_pitch
    b_fifth = octave_fit(p_5, 'bass')
    if b_fifth == bp:
        b_fifth = octave_fit(p_3, 'bass')

    def add(step_offset: int, pitch: int, dur: str, vel: float):
        notes.append(NoteEvent(
            step=b_st + step_offset,
            note=midi_to_note_name(pitch),
            duration=dur,
            velocity=round(vel, 2),
            _p=pitch
        ))

    # =========================================================================
    # T01: Style Brisé (Lute Flow: Broken Staggered Inner Voices)
    # =========================================================================
    if texture_code == 'T01':
        # Retain genre notes, enrich with broken lute arpeggio in middle register
        notes = list(base_notes)
        brise_var = (track_seed + bar_idx) % 3
        if brise_var == 0:
            seq_44 = [(2, p_r, 0.65), (6, p_3, 0.67), (10, p_5, 0.66), (14, p_r, 0.64)]
            seq_34 = [(2, p_r, 0.65), (6, p_3, 0.67), (10, p_5, 0.65)]
        elif brise_var == 1:
            seq_44 = [(2, p_5, 0.66), (6, p_3, 0.67), (10, p_r, 0.65), (14, p_3, 0.64)]
            seq_34 = [(2, p_5, 0.66), (6, p_3, 0.67), (10, p_r, 0.65)]
        else:
            seq_44 = [(2, p_3, 0.65), (6, p_5, 0.68), (10, p_3, 0.66), (14, p_r, 0.64)]
            seq_34 = [(2, p_3, 0.66), (6, p_5, 0.67), (10, p_3, 0.64)]
            
        if meter == '4/4':
            for st, p, v in seq_44:
                add(st, p, '8n', v)
        elif meter == '3/4':
            for st, p, v in seq_34:
                add(st, p, '8n', v)
        else: # 6/8
            add(2, p_r, '8n', 0.64)
            add(4, p_3, '8n', 0.66)
            add(8, p_5, '8n', 0.65)
            add(10, p_r, '8n', 0.64)

    # =========================================================================
    # T02: Tasto Solo / Basso Continuo (Pedal Drone & Floating Monody)
    # =========================================================================
    elif texture_code == 'T02':
        # Remove middle accompaniments, sustain pedal bass, solo expressive melody
        bass_notes = [n for n in base_notes if n._p < 48]
        sop_notes = [n for n in base_notes if n._p >= 60]
        # Prolong first bass note to pedal drone
        if bass_notes:
            bass_notes[0].duration = '1n' if meter == '4/4' else '2n.'
            bass_notes[0].velocity = min(0.95, bass_notes[0].velocity + 0.05)
            notes.append(bass_notes[0])
        notes.extend(sop_notes)

    # =========================================================================
    # T03: Chiaroscuro (Terrace Dynamics: Forte <-> Piano Echo)
    # =========================================================================
    elif texture_code == 'T03':
        is_echo = (bar_idx % 2 == 1)
        notes = list(base_notes)
        if not is_echo:
            # FORTE: enrich velocity and add supporting fifth
            for n in notes:
                n.velocity = min(0.96, n.velocity + 0.07)
            add(0, p_5, '4n', 0.72)
        else:
            # PIANO ECHO: reduce velocity, drop bass volume, solo upper register
            for n in notes:
                n.velocity = max(0.60, n.velocity - 0.18)
            # Remove deep bass in echo bar for transparent distant sound
            notes = [n for n in notes if n._p >= 48 or (n.step - b_st) == 0]

    # =========================================================================
    # T04: Tirata di Note (Rapid Running 16th Cascades)
    # =========================================================================
    elif texture_code == 'T04':
        notes = list(base_notes)
        # Inject rapid cascading run on steps 4..11 in 4/4 or 4..9 in 3/4
        run_variant = (track_seed + bar_idx) % 2
        run_pitches = [s_r, s_3, s_5, s_8] if run_variant == 0 else [s_8, s_5, s_3, s_r]
        if meter == '4/4':
            for i in range(4):
                add(4 + i * 2, run_pitches[i % 4], '16n', 0.86)
        elif meter == '3/4':
            for i in range(3):
                add(4 + i * 2, run_pitches[i % 4], '16n', 0.86)
        else: # 6/8
            for i in range(3):
                add(3 + i * 1, run_pitches[i % 4], '16n', 0.86)

    # =========================================================================
    # T05: Suspiratio (Weeping Sighs: Downbeat Silence & Dissonant Entry)
    # =========================================================================
    elif texture_code == 'T05':
        # Filter out any soprano attack on step 0 (downbeat silence)
        sop_non_zero = [n for n in base_notes if not (n.step == b_st and n._p >= 60)]
        notes = sop_non_zero
        # Ensure deep expressive sigh entry on step 2
        add(2, s_sus, '4n.', 0.82)
        add(8, s_3, '4n', 0.70)

    # =========================================================================
    # T06: Stretto Polyphonico (Imitative Counterpoint Across Voices)
    # =========================================================================
    elif texture_code == 'T06':
        notes = list(base_notes)
        # Add tenor imitation offset by 4 steps
        add(4, p_r, '4n', 0.74)
        add(8, p_3, '4n', 0.72)

    # =========================================================================
    # T07: Campanella (High Bell Chime on Off-beats)
    # =========================================================================
    elif texture_code == 'T07':
        notes = list(base_notes)
        chime_var = (track_seed + bar_idx) % 2
        chime_p = s_8 if chime_var == 0 else s_5
        if meter == '4/4':
            add(2, chime_p, '8n', 0.85)
            add(6, chime_p, '8n', 0.82)
            add(10, chime_p, '8n', 0.85)
            add(14, chime_p, '8n', 0.80)
        elif meter == '3/4':
            add(2, chime_p, '8n', 0.85)
            add(6, chime_p, '8n', 0.82)
            add(10, chime_p, '8n', 0.84)
        else: # 6/8
            add(2, chime_p, '8n', 0.85)
            add(5, chime_p, '8n', 0.82)
            add(8, chime_p, '8n', 0.85)
            add(11, chime_p, '8n', 0.80)

    # =========================================================================
    # T08: Staccato Portato (Detached Walking Bass under Legato Melody)
    # =========================================================================
    elif texture_code == 'T08':
        notes = list(base_notes)
        # Convert bass notes to crisp 8n portato
        for n in notes:
            if n._p < 48:
                n.duration = '8n'
                n.velocity = min(0.92, n.velocity + 0.04)

    # =========================================================================
    # T09: Accordo Arpeggiato (Grand Rolling Chords with 4-3 Suspensions)
    # =========================================================================
    elif texture_code == 'T09':
        notes = list(base_notes)
        # Add grand rolled chord anchor at step 0
        add(0, bp, '1n' if meter == '4/4' else '2n.', 0.86)
        add(0, p_r, '2n' if meter == '4/4' else '4n', 0.70)
        add(0, p_5, '2n' if meter == '4/4' else '4n', 0.70)
        # Add 4-3 suspension resolution
        add(0, s_sus, '4n', 0.84)
        add(4, s_3, '4n', 0.72)

    # =========================================================================
    # T10: Groppo & Trillo (Ornamental Turns & Trills on Suspensions - Diruta 1593)
    # =========================================================================
    elif texture_code == 'T10':
        notes = list(base_notes)
        # Inject florid groppo (turns) & trillo (rapid oscillations) around suspensions
        if meter == '4/4':
            add(8, s_sus, '16n', 0.84)
            add(10, s_3, '16n', 0.80)
            add(12, s_sus, '16n', 0.86)
            add(14, s_3, '16n', 0.82)
        elif meter == '3/4':
            add(6, s_sus, '16n', 0.84)
            add(8, s_3, '16n', 0.80)
            add(10, s_sus, '16n', 0.85)
        else: # 6/8
            add(6, s_sus, '16n', 0.84)
            add(8, s_3, '16n', 0.80)
            add(10, s_sus, '16n', 0.85)

    # =========================================================================
    # T11: Cantus Firmus Legatissimo (Solemn Choral Polyphony - Sweelinck 1610)
    # =========================================================================
    elif texture_code == 'T11':
        # Pure choral counterpoint: solemn uninterrupted legato chords.
        # Strictly zero fast notes (no 8n, 16n, 32n), only 1n, 2n, 2n.
        notes = []
        is_even_bar = (bar_idx % 2 == 0)
        is_cadential_bar = (bar_idx >= num_bars - 2)
        
        # Bass foundation: solid pedal/cantus firmus
        add(0, bp, '1n' if meter == '4/4' else '2n.', 0.88)
        
        # Inner choral voices (Tenor / Alto)
        dur_inner = '1n' if (meter == '4/4' and is_even_bar) else ('2n.' if meter in ['3/4', '6/8'] else '2n')
        add(0, p_r, dur_inner, 0.72)
        add(0, p_5, dur_inner, 0.70)
        
        # Soprano cantus firmus
        if meter == '4/4':
            if is_even_bar or is_cadential_bar:
                # Grand whole note sustain
                add(0, s_r if is_cadential_bar else s_3, '1n', 0.84)
            else:
                # Pair of noble half notes for rhythmic life and interval diversity
                add(0, s_3, '2n', 0.82)
                add(8, s_5, '2n', 0.84)
                add(8, p_3, '2n', 0.68)
        elif meter in ['3/4', '6/8']:
            if is_even_bar or is_cadential_bar:
                add(0, s_r if is_cadential_bar else s_3, '2n.', 0.84)
            else:
                # Noble 2n + 4n division for rhythmic life and cantus firmus motion
                add(0, s_3, '2n', 0.82)
                add(8, s_5, '4n', 0.84)
                add(8, p_3, '4n', 0.68)

    # =========================================================================
    # T12: Arpeggio Spezzato (Virtuosic Split-Register Broken Chords - Pasquini/Scarlatti)
    # =========================================================================
    else: # T12
        notes = []
        # Alternating split hand leaps between deep bass and sparkling treble
        if meter == '4/4':
            add(0, bp, '8n', 0.88)          # Deep bass (< 48)
            add(2, p_3, '8n', 0.74)         # Tenor third
            add(4, s_8, '8n', 0.86)         # High sparkling soprano (>= 65)
            add(6, p_5, '8n', 0.72)         # Alto fifth
            add(8, b_fifth, '8n', 0.82)     # Bass leap (< 48)
            add(10, s_3, '8n', 0.82)        # Soprano third
            add(12, s_8, '8n', 0.86)        # High sparkling soprano (>= 65)
            add(14, p_r, '8n', 0.76)        # Inner voice resolution
        elif meter == '3/4':
            add(0, bp, '8n', 0.88)
            add(2, p_3, '8n', 0.74)
            add(4, s_8, '8n', 0.86)
            add(6, b_fifth, '8n', 0.80)
            add(8, s_3, '8n', 0.82)
            add(10, s_8, '8n', 0.84)
        else: # 6/8
            add(0, bp, '8n', 0.88)
            add(2, p_3, '8n', 0.74)
            add(4, s_8, '8n', 0.86)
            add(6, b_fifth, '8n', 0.80)
            add(8, s_3, '8n', 0.82)
            add(10, s_8, '8n', 0.84)

    return notes
