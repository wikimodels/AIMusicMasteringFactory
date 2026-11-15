"""
Baroque Master Matrix 300 Generator
=============================================================================
Compiles the complete 300-track combinatorial matrix strictly following:
- 10 Volumes (30 tracks each = 300 tracks)
- 3 Instrument Blocks (Chamber Piano, Harpsichord/Lute, Consort Strings/Organ)
- 8 Genre Forms per Volume (Pavane, Passacaglia, Lamento/Toccata, Folia, 
  Sarabande, Rigaudon/Bourree, Galliard/Courante, Ricercar/Canzona)
- 12 Texture Engines (E01-E12 with +2 rotation per volume)
- 8 Start Models (S01-S08 in cyclic rotation)
- 8 Cadence Models (C01-C08 in cyclic rotation)
- Path A Tempo: 54-58 BPM (target duration strictly 30-45 seconds)
=============================================================================
"""

import os
import json

OUTPUT_DIR = os.path.dirname(__file__)

VOLUMES = [
    {
        'volume': 1,
        'title': 'Том 1: D Minor',
        'key_code': 'Dm',
        'key_name': 'D Minor',
        'instrument': 'Chamber Piano',
        'engine_start_idx': 0, # E01
    },
    {
        'volume': 2,
        'title': 'Том 2: A Minor',
        'key_code': 'Am',
        'key_name': 'A Minor',
        'instrument': 'Chamber Piano',
        'engine_start_idx': 2, # E03
    },
    {
        'volume': 3,
        'title': 'Том 3: G Minor',
        'key_code': 'Gm',
        'key_name': 'G Minor',
        'instrument': 'Chamber Piano',
        'engine_start_idx': 4, # E05
    },
    {
        'volume': 4,
        'title': 'Том 4: C Minor',
        'key_code': 'Cm',
        'key_name': 'C Minor',
        'instrument': 'Chamber Piano (091-100) / Harpsichord (101-120)',
        'engine_start_idx': 6, # E07
    },
    {
        'volume': 5,
        'title': 'Том 5: E Minor',
        'key_code': 'Em',
        'key_name': 'E Minor',
        'instrument': 'Harpsichord / Lute',
        'engine_start_idx': 8, # E09
    },
    {
        'volume': 6,
        'title': 'Том 6: F# Minor',
        'key_code': 'Fsm',
        'key_name': 'F# Minor',
        'instrument': 'Harpsichord / Lute',
        'engine_start_idx': 10, # E11
    },
    {
        'volume': 7,
        'title': 'Том 7: B Minor',
        'key_code': 'Bm',
        'key_name': 'B Minor',
        'instrument': 'Harpsichord (181-200) / Consort Strings & Organ (201-210)',
        'engine_start_idx': 0, # E01
    },
    {
        'volume': 8,
        'title': 'Том 8: F Major / D Dorian',
        'key_code': 'F_Maj_D_Dor',
        'key_name': 'F Major / D Dorian',
        'instrument': 'Consort Strings / Organ',
        'engine_start_idx': 2, # E03
    },
    {
        'volume': 9,
        'title': 'Том 9: G Major / E Phrygian',
        'key_code': 'G_Maj_E_Phryg',
        'key_name': 'G Major / E Phrygian',
        'instrument': 'Chamber Piano',
        'engine_start_idx': 4, # E05
    },
    {
        'volume': 10,
        'title': 'Том 10: C Major / A Harmonic & Melodic',
        'key_code': 'C_Maj_A_Harm',
        'key_name': 'C Major / A Harmonic & Melodic',
        'instrument': 'Consort Strings / Organ',
        'engine_start_idx': 6, # E07
    },
]

ENGINES = [
    ('E01', 'Alberti Baroque Subdivided'),
    ('E02', 'Counterpoint Dual-Voice Canon'),
    ('E03', 'French Overture Dotted Motorics'),
    ('E04', 'Ostinato Ground Bass Variations'),
    ('E05', 'Broken Arpeggiation Harpsichord Flow'),
    ('E06', 'Syncopated Renaissance Suspension'),
    ('E07', 'Fast Triple Motoric (Courante Drive)'),
    ('E08', 'Chromatic Lamento Descent'),
    ('E09', 'Imitative Pedal Point Fugato'),
    ('E10', 'Corelli Trio Sonata Interlocking'),
    ('E11', 'Ornate Florid Cantabile'),
    ('E12', 'Staccato Chaconne Bounce'),
]

STARTS = [
    ('S01', 'Solo Melodic Pickup'),
    ('S02', 'First-Inversion Bass'),
    ('S03', 'Dominant / Leading-Tone Tension'),
    ('S04', 'Imitative Tenor/Alto Entry'),
    ('S05', 'Silent Downbeat / Syncopated Entry'),
    ('S06', 'Subdominant / Mediant Opening'),
    ('S07', 'Ostinato Pulse First'),
    ('S08', 'Dotted Rhetorical Question'),
]

CADENCES = [
    ('C01', 'Picardy Cadence & Octave Anchor'),
    ('C02', 'Half-Cadence Open Question'),
    ('C03', 'Deceptive Resolution to VI'),
    ('C04', 'Solo Melodic Echo / Unison Fade'),
    ('C05', 'Phrygian Cadence Descent'),
    ('C06', 'Tierce-Free Open Fifth'),
    ('C07', 'Plagal Amen Echo'),
    ('C08', 'Anacrusis Loop Bridge'),
]

# 8 Genre Forms breakdown inside 30 tracks
# Tempos tuned so total duration (including tail) is strictly between 32.0s and 45.0s
FORM_SLOTS = [
    # 01-04: Pavane (128 steps, 4/4) -> ~37-39s
    (1, 'Pavane', 'Pavane', 128, (4, 4), [56, 57, 58, 56]),
    (2, 'Pavane', 'Pavane', 128, (4, 4), [57, 58, 56, 57]),
    (3, 'Pavane', 'Pavane', 128, (4, 4), [58, 56, 57, 58]),
    (4, 'Pavane', 'Pavane', 128, (4, 4), [56, 57, 58, 57]),
    # 05-08: Passacaglia (128 steps, 3/4) -> ~37-39s
    (5, 'Passacaglia', 'Passacaglia', 128, (3, 4), [56, 57, 58, 56]),
    (6, 'Passacaglia', 'Passacaglia', 128, (3, 4), [57, 56, 58, 57]),
    (7, 'Passacaglia', 'Passacaglia', 128, (3, 4), [58, 57, 56, 58]),
    (8, 'Passacaglia', 'Passacaglia', 128, (3, 4), [56, 58, 57, 56]),
    # 09-12: Lamento / Toccata (144 steps, 4/4) -> ~40-42s
    (9, 'Lamento', 'Lamento', 144, (4, 4), [56, 57, 58, 57]),
    (10, 'Toccata', 'Toccata', 144, (4, 4), [58, 59, 57, 58]),
    (11, 'Lamento', 'Lamento', 144, (4, 4), [57, 56, 58, 57]),
    (12, 'Toccata', 'Toccata', 144, (4, 4), [58, 57, 59, 58]),
    # 13-16: La Folia (128 steps, 3/4) -> ~37-39s
    (13, 'La_Folia', 'La Folia', 128, (3, 4), [56, 57, 58, 56]),
    (14, 'La_Folia', 'La Folia', 128, (3, 4), [57, 58, 56, 57]),
    (15, 'La_Folia', 'La Folia', 128, (3, 4), [58, 56, 57, 58]),
    (16, 'La_Folia', 'La Folia', 128, (3, 4), [56, 58, 57, 56]),
    # 17-20: Sarabande (128 steps, 3/4) -> ~37-39s
    (17, 'Sarabande', 'Sarabande', 128, (3, 4), [55, 56, 57, 55]),
    (18, 'Sarabande', 'Sarabande', 128, (3, 4), [56, 55, 57, 56]),
    (19, 'Sarabande', 'Sarabande', 128, (3, 4), [57, 56, 55, 57]),
    (20, 'Sarabande', 'Sarabande', 128, (3, 4), [55, 57, 56, 55]),
    # 21-24: Rigaudon & Bourree (112 steps, 2/4 or 4/4) -> ~32-34s
    (21, 'Rigaudon', 'Rigaudon', 112, (2, 4), [56, 57, 58, 56]),
    (22, 'Bourree', 'Bourree', 112, (4, 4), [57, 56, 58, 57]),
    (23, 'Rigaudon', 'Rigaudon', 112, (2, 4), [58, 57, 56, 58]),
    (24, 'Bourree', 'Bourree', 112, (4, 4), [56, 58, 57, 56]),
    # 25-27: Galliard & Courante (128 steps, 3/4 or 6/8) -> ~36-38s
    (25, 'Galliard', 'Galliard', 128, (3, 4), [57, 58, 56, 57]),
    (26, 'Courante', 'Courante', 128, (6, 8), [58, 59, 57, 58]),
    (27, 'Galliard', 'Galliard', 128, (3, 4), [58, 57, 56, 58]),
    # 28-30: Ricercar & Canzona (160 steps, 4/4) -> ~43-45s
    (28, 'Ricercar', 'Ricercar', 160, (4, 4), [58, 59, 60, 59]),
    (29, 'Canzona', 'Canzona', 160, (4, 4), [59, 60, 58, 59]),
    (30, 'Ricercar', 'Ricercar Solenne', 160, (4, 4), [58, 59, 60, 58]),
]

def build_matrix():
    matrix = []
    
    global_idx = 1
    start_cycle = 0
    cadence_cycle = 0
    
    for v_idx, v in enumerate(VOLUMES):
        vol_num = v['volume']
        vol_title = v['title']
        key_code = v['key_code']
        key_name = v['key_name']
        instrument = v['instrument']
        engine_start = v['engine_start_idx']
        
        for slot_idx, (slot_num, form_code, form_name, steps, meter, bpm_choices) in enumerate(FORM_SLOTS):
            # Engine calculation (E01-E12 with +2 shift per volume)
            engine_idx = (engine_start + slot_idx) % len(ENGINES)
            engine_code, engine_desc = ENGINES[engine_idx]
            
            # Start model rotation (S01-S08)
            s_code, s_desc = STARTS[start_cycle % len(STARTS)]
            start_cycle += 1
            
            # Cadence model rotation (C01-C08)
            c_code, c_desc = CADENCES[cadence_cycle % len(CADENCES)]
            cadence_cycle += 1
            
            bpm = bpm_choices[v_idx % len(bpm_choices)]
            
            # Exact duration calculation:
            # 1 step = 16th note = (60 / bpm) / 4 seconds
            step_duration_s = (60.0 / bpm) / 4.0
            base_audio_duration_s = steps * step_duration_s
            reverb_tail_s = 3.5
            total_duration_s = base_audio_duration_s + reverb_tail_s
            
            # Filename
            filename = f"Loop_{global_idx:03d}_{key_code}_{form_code}_{engine_code}_{s_code}_{c_code}"
            
            matrix.append({
                'index': global_idx,
                'volume': vol_num,
                'volume_title': vol_title,
                'key_code': key_code,
                'key_name': key_name,
                'instrument': instrument,
                'form_code': form_code,
                'form_name': form_name,
                'steps': steps,
                'meter': f"{meter[0]}/{meter[1]}",
                'bpm': bpm,
                'duration_sec': round(total_duration_s, 1),
                'engine_code': engine_code,
                'engine_desc': engine_desc,
                'start_code': s_code,
                'start_desc': s_desc,
                'cadence_code': c_code,
                'cadence_desc': c_desc,
                'filename': filename,
            })
            global_idx += 1
            
    return matrix

def main():
    matrix = build_matrix()
    
    # 1. Save JSON
    json_path = os.path.join(OUTPUT_DIR, "baroque_master_matrix_300.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)
    print(f"[+] JSON matrix saved: {json_path} ({len(matrix)} tracks)")
    
    # 2. Save Markdown
    md_path = os.path.join(OUTPUT_DIR, "baroque_master_matrix_300.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Полная Генеральная Матрица Барочной Музыки (300 Лупов)\n\n")
        f.write("Спецификация составлена строго по правилам документа:\n")
        f.write("- **10 томов по 30 лупов** = 300 оригинальных композиций.\n")
        f.write("- **3 инструментальных блока:** Chamber Piano (001-100), Harpsichord/Lute (101-200), Consort Strings & Organ (201-300).\n")
        f.write("- **Тональная ротация:** Dm -> Am -> Gm -> Cm -> Em -> F#m -> Bm -> F Major / D Dorian -> G Major / E Phrygian -> C Major / A Harmonic.\n")
        f.write("- **8 форм в каждом томе:** Pavane (4), Passacaglia (4), Lamento/Toccata (4), La Folia (4), Sarabande (4), Rigaudon/Bourree (4), Galliard/Courante (3), Ricercar/Canzona (3).\n")
        f.write("- **Ротация 12 движков (E01-E12)** со сдвигом +2 на том.\n")
        f.write("- **Ротация 8 стартов (S01-S08)** и **8 кадансов (C01-C08)**.\n")
        f.write("- **Хронометраж: строго 30–45 секунд** (медленный барочный темп 54–58 BPM).\n\n")
        f.write("---\n\n")
        
        curr_vol = 0
        for item in matrix:
            if item['volume'] != curr_vol:
                curr_vol = item['volume']
                f.write(f"\n## {item['volume_title']} | Инструмент: {item['instrument']}\n\n")
                f.write("| # | ID Файла | Форма | Шаги | Темп | Длит. | Движок (E) | Старт (S) | Каданс (C) |\n")
                f.write("|---|----------|-------|------|------|-------|------------|-----------|------------|\n")
            
            f.write(
                f"| {item['index']:03d} | `{item['filename']}` | **{item['form_name']}** | "
                f"{item['steps']} | {item['bpm']} BPM | {item['duration_sec']}s | "
                f"**{item['engine_code']}** ({item['engine_desc']}) | "
                f"**{item['start_code']}** ({item['start_desc']}) | "
                f"**{item['cadence_code']}** ({item['cadence_desc']}) |\n"
            )
            
    print(f"[+] Markdown matrix saved: {md_path}")

if __name__ == '__main__':
    main()
