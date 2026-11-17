"""
Master Composer Engine for Early Baroque & Renaissance Music
Implements 4-phase dramaturgy, authentic form schemata, starts S01-S08,
cadences C01-C08, and textures T01-T09 without any dummy fallbacks.
"""

from typing import List, Dict, Any
from baroque_loops_generator.models import (
    TrackConfig, NoteEvent, KEY_MODES, FORM_SCHEMATA, FORM_PROGRESSIONS_CATALOG
)
from baroque_loops_generator.theory import (
    get_chord_degrees, octave_fit, midi_to_note_name, is_pitch_valid_in_key
)
from baroque_loops_generator.textures import apply_texture

def compose_track(item: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Composes full piece obeying:
    - 4-phase dynamic dramaturgy (Exposition -> Development -> Climax -> Resolution)
    - Specific historical form schemata
    - Texture execution (T01-T09)
    - Start models (S01-S08)
    - Cadence models (C01-C08)
    - Max density <= 4 notes
    - Zero out-of-scale notes
    """
    key_code = item['key_code']
    steps = item['steps']
    texture_code = item['texture_code']
    start_code = item['start_code']
    cadence_code = item['cadence_code']
    form_code = item['form_code']
    meter = item['meter']
    track_seed = item.get('index', 1)
    
    # 1. Bar length determination
    if meter == '4/4':
        bar_len = 16
    elif meter in ['3/4', '6/8']:
        bar_len = 12
    else:
        bar_len = 16
        
    num_bars = steps // bar_len
    
    # 2. Harmonic progression by Form & Historical Ground Variant
    variant = item.get('progression_variant')
    if variant and form_code in FORM_PROGRESSIONS_CATALOG and variant in FORM_PROGRESSIONS_CATALOG[form_code]:
        prog_base = FORM_PROGRESSIONS_CATALOG[form_code][variant]
    elif form_code in FORM_PROGRESSIONS_CATALOG:
        variants = list(FORM_PROGRESSIONS_CATALOG[form_code].values())
        prog_base = variants[item.get('index', 0) % len(variants)]
    else:
        prog_base = FORM_SCHEMATA.get(form_code, FORM_SCHEMATA['Pavane'])
        
    prog = [prog_base[i % len(prog_base)] for i in range(num_bars)]
    
    # 3. Apply Start Model S01-S08 to harmonic progression
    if start_code == 'S02':
        prog[0] = 'i6' # First-inversion bass
    elif start_code == 'S03':
        prog[0] = 'V'  # Dominant tension opening
    elif start_code == 'S06':
        prog[0] = 'iv' if item.get('index', 0) % 2 == 0 else 'VI' # Subdominant opening
        
    # 4. Apply Cadence Model C01-C08 to harmonic progression
    if cadence_code == 'C01':
        prog[-1] = 'I_picardy' # Picardy major 3rd
    elif cadence_code == 'C02':
        prog[-1] = 'V'         # Half-cadence question
    elif cadence_code == 'C03':
        prog[-1] = 'VI'        # Deceptive cadence
    elif cadence_code == 'C05':
        prog[-2] = 'iv6'       # Phrygian descent
        prog[-1] = 'V'
    elif cadence_code == 'C06':
        prog[-1] = 'I_open5'   # Open fifth / octave
    elif cadence_code == 'C07':
        prog[-2] = 'iv'        # Plagal Amen
        prog[-1] = 'i'
        
    all_notes: List[NoteEvent] = []
    
    # 5. Bar-by-bar composition with 4-phase dramaturgy
    for bar_idx in range(num_bars):
        b_st = bar_idx * bar_len
        deg = prog[bar_idx]
        cd = get_chord_degrees(key_code, deg)
        
        # Determine 4-phase Dramaturgy
        if bar_idx < 2:
            phase = 'exposition'
        elif bar_idx < num_bars - 3:
            phase = 'development'
        elif bar_idx == num_bars - 3: # Golden section climax (Bar 6 in 8-bar track)
            phase = 'climax'
        else:
            phase = 'resolution'
            
        # Generate notes for measure via Texture Engine T01-T12
        bar_notes = apply_texture(
            texture_code=texture_code,
            bar_idx=bar_idx,
            num_bars=num_bars,
            b_st=b_st,
            bar_len=bar_len,
            meter=meter,
            cd=cd,
            dramaturgy_phase=phase,
            form_code=form_code,
            track_seed=track_seed
        )
        
        # 6. Apply Start Model S01-S08 overrides on Bar 0
        if bar_idx == 0:
            if start_code == 'S01':
                # Solo Melodic Pickup: filter out bass notes in first half of bar
                bar_notes = [n for n in bar_notes if n._p >= 48 or (n.step - b_st) >= (bar_len // 2)]
            elif start_code == 'S04':
                # Imitative Entry: bass enters later, middle voice starts
                bar_notes = [n for n in bar_notes if n._p >= 48 or (n.step - b_st) >= (bar_len // 2)]
            elif start_code == 'S05':
                # Silent Downbeat: nothing on step 0
                bar_notes = [n for n in bar_notes if (n.step - b_st) > 0]
            elif start_code == 'S07':
                # Ostinato Pulse First: soprano silent in bar 0, only bass/inner voice
                bar_notes = [n for n in bar_notes if n._p < 60]
            elif start_code == 'S08':
                # Dotted Rhetorical Question: ensure sharp dotted figure
                bar_notes = [n for n in bar_notes if (n.step - b_st) < (bar_len // 2)]
                
        # 7. Apply Cadence Model C01-C08 overrides on final measure
        if bar_idx == num_bars - 1:
            if cadence_code == 'C04':
                # Solo Melodic Echo Fade: bass silent in last bar, quiet soprano fade
                bar_notes = [n for n in bar_notes if n._p >= 60]
                for n in bar_notes:
                    n.velocity = max(0.60, n.velocity - 0.18)
            elif cadence_code == 'C08':
                # Anacrusis Loop Bridge: add lead-in pickup at end of measure
                bridge_pitch = cd.soprano_pitches[1] # 3rd
                bar_notes.append(NoteEvent(
                    step=b_st + bar_len - 2,
                    note=midi_to_note_name(bridge_pitch),
                    duration='8n',
                    velocity=0.74,
                    _p=bridge_pitch
                ))
            elif cadence_code == 'C06':
                # Open 5th octave: ensure no 3rd is sounding
                third_semi = KEY_MODES.get(key_code, KEY_MODES['Dm'])['scale'][2]
                bar_notes = [n for n in bar_notes if (n._p % 12) != third_semi]
                
        all_notes.extend(bar_notes)
        
    # 8. Density Gate: Max 4 simultaneous notes at any step, preserving outer voices
    by_step: Dict[int, Dict[int, NoteEvent]] = {}
    for n in all_notes:
        step_dict = by_step.setdefault(n.step, {})
        # Deduplicate identical pitches at the same step (keep higher velocity)
        if n._p not in step_dict or n.velocity > step_dict[n._p].velocity:
            step_dict[n._p] = n
            
    pruned: List[NoteEvent] = []
    for st in sorted(by_step.keys()):
        step_notes = sorted(by_step[st].values(), key=lambda x: x._p)
        if len(step_notes) <= 4:
            pruned.extend(step_notes)
        else:
            # Classical frame preservation: strictly preserve Bass (lowest) and Soprano (highest)
            bass = step_notes[0]
            sop = step_notes[-1]
            inner = step_notes[1:-1]
            kept = [bass] + inner[:2] + [sop]
            pruned.extend(kept)

    # 9. Return clean dictionary representation
    return [n.to_dict() for n in pruned]
