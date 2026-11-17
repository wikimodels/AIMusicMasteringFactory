"""
Baroque Master Matrix 300 Generator & Markdown Exporter
Creates baroque_master_matrix_300.json and baroque_master_matrix_300.md
Guaranteeing:
1. Exact 300 tracks across 10 volumes (30 per volume).
2. 12 Playing styles / textures (T01 - T12) cyclically rotated.
3. 8 Minor keys rotated with zero adjacent collisions.
4. 12 Contrasting genres with distinct meters (4/4, 3/4, 6/8).
5. Historical grounds from FORM_PROGRESSIONS_CATALOG.
6. Historical BPMs from FORM_TEMPO_RANGES (wide variance, std > 10).
7. Strict 8 starts (S01-S08) and 8 cadences (C01-C08).
"""

import json
import os
from typing import Dict, List, Any
import numpy as np

from baroque_loops_generator.models import (
    KEY_MODES, FORM_PROGRESSIONS_CATALOG, FORM_TEMPO_RANGES
)

# 12 Genres in contrasting order (Duple slow -> Triple fast -> Duple expressive -> Triple ground -> etc.)
GENRE_ROTATION_ORDER = [
    ('Pavane', '4/4'),
    ('Galliard', '3/4'),
    ('Lamento', '4/4'),
    ('Ciaccona', '3/4'),
    ('Toccata', '4/4'),
    ('Sarabande', '3/4'),
    ('Canzona', '4/4'),
    ('Siciliana', '6/8'),
    ('La_Folia', '3/4'),
    ('Ricercar', '4/4'),
    ('La_Monica', '4/4'),
    ('Spagnoletta', '4/4'),
]

KEY_ROTATION = ['Dm', 'Am', 'Gm', 'Em', 'Bm', 'Cm', 'Fsm', 'D_Dor']
TEXTURE_ROTATION = [f'T{i:02d}' for i in range(1, 13)]
START_ROTATION = [f'S{i:02d}' for i in range(1, 9)]
CADENCE_ROTATION = [f'C{i:02d}' for i in range(1, 9)]

TEXTURE_INFO = {
    'T01': ('Style Brisé (Lute Flow)', 'Лютневый стиль: расслоенный арпеджированный перебор с микросдвигом голосов 32 мс'),
    'T02': ('Tasto Solo (Pedal Drone)', 'Бурдонная органная педаль в басу и парящая сольная монодия в сопрано'),
    'T03': ('Chiaroscuro (Dynamic Echo)', 'Террасная светотень: чередование плотного Forte и далекого прозрачного Piano эхо'),
    'T04': ('Tirata di Note (Cascades)', 'Виртуозные пассажи шестнадцатыми: стремительные каскадные взлеты к кульминации'),
    'T05': ('Suspiratio (Weeping Sighs)', 'Прерывистые вздохи скорби: пауза на первой доле и щемящее задержание 7-6/4-3'),
    'T06': ('Stretto (Polyphonic Canon)', 'Имитационный полифонический канон: тема баса подхватывается верхними голосами'),
    'T07': ('Campanella (Bell Chime)', 'Колокольный звон: звенящие высокие октавы на слабых долях (образ вечернего колокола)'),
    'T08': ('Staccato Portato (Walking Bass)', 'Шагающий церемониальный бас: упругие короткие шаги под плавным певучим легато'),
    'T09': ('Accordo Arpeggiato (Grandioso)', 'Монументальные перекатные аккорды с глубоким дыханием и задержанием 4-3'),
    'T10': ('Groppo & Trillo (Ornamental Cadences)', 'Ренессансные трели и группетто: орнаментальные опевания и тремоло вокруг задержаний (Diruta 1593)'),
    'T11': ('Cantus Firmus Legatissimo (Sacred Polyphony)', 'Хоральный стиль cantus firmus: строгие протяжные легатные аккорды целыми и половинными нотами (Sweelinck 1610)'),
    'T12': ('Arpeggio Spezzato (Broken Virtuoso Arpeggio)', 'Расщепленное арпеджио: виртуозные броски между глубоким басом и верхними регистрами с перекрещиванием рук (Pasquini / Scarlatti)'),
}

START_INFO = {
    'S01': ('Solo Melodic Pickup', 'Сольный затактовый вздох сопрано'),
    'S02': ('First-Inversion Bass', 'Старт с терцового тона / секстаккорд'),
    'S03': ('Dominant Tension Opening', 'Старт с напряженного доминантового неустоя'),
    'S04': ('Imitative Tenor Entry', 'Полифонический зачин среднего голоса'),
    'S05': ('Silent Downbeat', 'Пауза на сильную долю (дыхание сарабанды)'),
    'S06': ('Subdominant Opening', 'Вход через субдоминанту или параллель'),
    'S07': ('Ostinato Pulse First', 'Остинато баса или перебор соло'),
    'S08': ('Dotted Rhetorical Question', 'Пунктирный риторический вызов оратора'),
}

CADENCE_INFO = {
    'C01': ('Picardy Cadence & Octave Anchor', 'Пикардийская мажорная терция с открытой октавой'),
    'C02': ('Half-Cadence Open Question', 'Половинный каданс-вопрос на доминанте'),
    'C03': ('Deceptive Resolution to VI', 'Прерванный драматический каданс в VI ступень'),
    'C04': ('Solo Melodic Echo / Fade', 'Затихающее сольное эхо верхнего голоса'),
    'C05': ('Phrygian Cadence Descent', 'Фригийский полутоновый спуск баса iv6 -> V'),
    'C06': ('Tierce-Free Open Fifth', 'Чистая открытая квинта без терции (архаика)'),
    'C07': ('Plagal Amen Echo', 'Плагальное созерцательное завершение iv -> i'),
    'C08': ('Anacrusis Loop Bridge', 'Затактовый мостик, втягивающий в начало цикла'),
}

GENRE_RUSSIAN_NAMES = {
    'Pavane': 'Павана',
    'Galliard': 'Гальярда',
    'Lamento': 'Ламенто',
    'Ciaccona': 'Чакона',
    'Toccata': 'Токката',
    'Sarabande': 'Сарабанда',
    'Canzona': 'Канцона',
    'Siciliana': 'Сицилиана',
    'La_Folia': 'Ла Фолия',
    'Ricercar': 'Ричеркар',
    'La_Monica': 'Ла Моника',
    'Spagnoletta': 'Спаньолетта',
}

def generate_matrix() -> List[Dict[str, Any]]:
    matrix: List[Dict[str, Any]] = []
    
    genre_prog_counters = {g: 0 for g, _ in GENRE_ROTATION_ORDER}
    genre_tempo_counters = {g: 0 for g, _ in GENRE_ROTATION_ORDER}
    
    for i in range(300):
        idx = i + 1
        vol = (i // 30) + 1
        vol_title = f"Том {vol:02d}: Собрание {vol} (Multi-Key Minor)"
        
        # 1. Contrasting Genre: cycles through 12 genres
        genre, meter = GENRE_ROTATION_ORDER[i % len(GENRE_ROTATION_ORDER)]
        genre_name = GENRE_RUSSIAN_NAMES[genre]
        
        # 2. Key: Stride of 3 is coprime to 8 (gcd(3, 8) = 1), shifted with volume offset.
        # Strictly guarantees no adjacent duplicate keys, and covers all 8 keys evenly.
        key_idx = (i * 3 + (i // 8)) % len(KEY_ROTATION)
        key_code = KEY_ROTATION[key_idx]
        key_name = KEY_MODES[key_code]['name']
        
        # 3. Progression Variant: advance per genre occurrence, rotating through all catalog variants
        prog_items = list(FORM_PROGRESSIONS_CATALOG[genre].items())
        p_offset = (genre_prog_counters[genre] + (vol - 1)) % len(prog_items)
        prog_variant, degrees = prog_items[p_offset]
        prog_desc = f"{prog_variant}: {' -> '.join(degrees[:4])}"
        genre_prog_counters[genre] += 1
        
        # 4. Tempo & Duration: historical ranges with organic micro-variance
        min_bpm, max_bpm = FORM_TEMPO_RANGES[genre]
        span = max_bpm - min_bpm + 1
        t_offset = (genre_tempo_counters[genre] * 7 + (i * 5) + (vol * 3)) % span
        bpm = min_bpm + t_offset
        genre_tempo_counters[genre] += 1
        
        # Steps based on genre/meter
        if meter == '4/4':
            steps = 128
        elif genre == 'La_Folia':
            steps = 96
        else:
            steps = 144
            
        step_sec = (60.0 / bpm) / 4.0
        dur_sec = round((steps * step_sec) + 3.5, 1)
        
        # 5. Texture T01-T12: Stride of 5 is coprime to 12 (gcd(5, 12) = 1).
        # Shifted by (i // 12) so genre is NEVER locked to the same texture!
        # Every genre explores different textures across volumes!
        tex_idx = (i * 5 + (i // 12)) % len(TEXTURE_ROTATION)
        tex_code = TEXTURE_ROTATION[tex_idx]
        tex_name, tex_desc = TEXTURE_INFO[tex_code]
        
        # 6. Start & Cadence: Stride of 5 and 7 (coprime to 8) with volume shift
        start_idx = (i * 5 + (i // 24)) % len(START_ROTATION)
        start_code = START_ROTATION[start_idx]
        start_name, start_desc = START_INFO[start_code]
        
        cadence_idx = (i * 7 + (i // 16)) % len(CADENCE_ROTATION)
        cadence_code = CADENCE_ROTATION[cadence_idx]
        cadence_name, cadence_desc = CADENCE_INFO[cadence_code]
        
        filename = f"Loop_{idx:03d}_{key_code}_{genre}_{tex_code}_{start_code}_{cadence_code}"
        
        track = {
            "index": idx,
            "volume": vol,
            "volume_title": vol_title,
            "key_code": key_code,
            "key_name": key_name,
            "instrument": "Chamber Piano",
            "form_code": genre,
            "form_name": genre_name,
            "progression_variant": prog_variant,
            "progression_desc": prog_desc,
            "steps": steps,
            "meter": meter,
            "bpm": bpm,
            "duration_sec": dur_sec,
            "texture_code": tex_code,
            "texture_name": tex_name,
            "texture_desc": tex_desc,
            "start_code": start_code,
            "start_desc": f"{start_name} ({start_desc})",
            "cadence_code": cadence_code,
            "cadence_desc": f"{cadence_name} ({cadence_desc})",
            "filename": filename
        }
        matrix.append(track)
        
    return matrix

def update_markdown_document(matrix: List[Dict[str, Any]], doc_path: str):
    """Updates the 10 volume markdown tables and specification in baroque_master_matrix_300.md."""
    with open(doc_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Split content before the first volume
    vol1_marker = "## Том 01:"
    if vol1_marker in content:
        header_part = content.split(vol1_marker)[0]
    else:
        raise ValueError(f"Marker '{vol1_marker}' not found in {doc_path}")
        
    # Update Section 11 in header_part if necessary
    old_sec11_title = "### 11. Спецификация 9 стилей клавирного исполнения и фактур (T01–T09)"
    new_sec11_title = "### 11. Спецификация 12 стилей клавирного исполнения и фактур (T01–T12)"
    if old_sec11_title in header_part:
        header_part = header_part.replace(old_sec11_title, new_sec11_title)
        
    old_intro_tex = "Ротация 9 стилей клавирного исполнения и фактур (T01–T09)"
    new_intro_tex = "Ротация 12 стилей клавирного исполнения и фактур (T01–T12)"
    if old_intro_tex in header_part:
        header_part = header_part.replace(old_intro_tex, new_intro_tex)
        
    # Check if T10-T12 are described in section 11
    t09_line = "* **T09 — Accordo Arpeggiato (Монументальное величие):** Медленные, царственные аккордовые полотна с глубоким перекатом пальцев и задержанием $4 \\to 3$."
    if t09_line in header_part and "* **T10 — Groppo & Trillo" not in header_part:
        t10_12_text = (
            t09_line + "\n"
            "* **T10 — Groppo & Trillo (Орнаментальные опевания и ренессансные трели):** "
            "Виртуозные группетто и тремоло вокруг кадансовых задержаний и вводных тонов (трактат Джироламо Дируты 1593 г. «Трансильванец»). "
            "Мелодия закручивается в стремительные 16-е опевания ($4 \\to 3$, $\\sharp 7 \\to 8$), создавая утонченное мерцание.\n"
            "* **T11 — Cantus Firmus Legatissimo (Хоральная сакральная полифония):** "
            "Строгий, молитвенный стиль cantus firmus (школа Яна Свелинка и Самуэля Шейдта). Полный запрет мелких пассажей и арпеджиато. "
            "Все голоса поют непрерывным широким легато целыми (`1n`) и половинными (`2n`) нотами, рождая чистейший кристальный соборный резонанс.\n"
            "* **T12 — Arpeggio Spezzato (Расщеплённое виртуозное арпеджио):** "
            "Блестящий стиль итальянского барокко (Бернардо Пасквини, Доменико Скарлатти). Драматические броски с перекрещиванием рук: "
            "глубокий бас мгновенно взлетает к звенящему верхнему сопрано через расщепленные ступени трезвучия, создавая эффект сверкающей арфы или двухмануального клавесина."
        )
        header_part = header_part.replace(t09_line, t10_12_text)
        
    # Build markdown tables for all 10 volumes
    vol_tables = []
    for v in range(1, 11):
        vol_tracks = [t for t in matrix if t['volume'] == v]
        v_title = f"## Том {v:02d}: Собрание {v} | Инструмент: Chamber Piano (Yamaha C5)"
        
        table_lines = [
            v_title,
            "",
            "| # | ID Файла | Форма | Прогрессия / Граунд | Метр | Шаги | Темп | Длит. | Тональность | Стиль игры (T) | Старт (S) | Каданс (C) |",
            "|---|----------|-------|---------------------|------|------|------|-------|-------------|----------------|-----------|------------|"
        ]
        
        for t in vol_tracks:
            i_str = f"{t['index']:03d}"
            f_id = t['filename']
            form = f"**{t['form_code']}**"
            prog = t['progression_desc']
            meter = t['meter']
            steps = str(t['steps'])
            tempo = f"{t['bpm']} BPM"
            dur = f"{t['duration_sec']:.1f}s"
            key = t['key_name']
            tex = f"**{t['texture_code']}** ({t['texture_name']})"
            start = f"**{t['start_code']}** ({START_INFO[t['start_code']][0]})"
            cad = f"**{t['cadence_code']}** ({CADENCE_INFO[t['cadence_code']][0]})"
            
            line = f"| {i_str} | {f_id} | {form} | {prog} | {meter} | {steps} | {tempo} | {dur} | {key} | {tex} | {start} | {cad} |"
            table_lines.append(line)
            
        vol_tables.append("\n".join(table_lines))
        
    full_markdown = header_part.rstrip() + "\n\n" + "\n\n---\n\n".join(vol_tables) + "\n"
    
    with open(doc_path, 'w', encoding='utf-8') as f:
        f.write(full_markdown)

def build_and_save():
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(root_dir, "baroque_master_matrix_300.json")
    md_path = os.path.join(root_dir, "baroque_master_matrix_300.md")
    
    print("[*] Generating diverse 300-track master matrix (T01 - T12)...")
    matrix = generate_matrix()
    
    bpms = [t['bpm'] for t in matrix]
    print(f"[+] Generated {len(matrix)} tracks.")
    print(f"[+] BPM range: min={min(bpms)}, max={max(bpms)}, mean={np.mean(bpms):.1f}, std={np.std(bpms):.2f}")
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(matrix, f, ensure_ascii=False, indent=2)
    print(f"[+] Saved JSON matrix: {json_path}")
    
    print("[*] Updating baroque_master_matrix_300.md documentation...")
    update_markdown_document(matrix, md_path)
    print(f"[+] Updated Markdown document: {md_path}")

if __name__ == '__main__':
    build_and_save()
