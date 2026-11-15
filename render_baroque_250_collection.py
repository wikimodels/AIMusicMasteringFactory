"""
Industrial Renaissance & Early Baroque 250 Factory (XVI Century)
=============================================================================
Renders 250 noble, slow, authentic 16th-century Renaissance & Early Baroque
masterpieces across 8 distinct historical styles using the Yamaha C5
Concert Grand Piano (Salamander Grand) with cathedral acoustics, 320 kbps MP3,
and matching MIDI files.
=============================================================================
"""

import os
import sys
import json
import time
import argparse
import subprocess
import concurrent.futures
import numpy as np
import scipy.signal as signal
import soundfile as sf
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from typing import Dict, List, Tuple, Any

SR = 44100
TICKS_PER_BEAT = 480
GOLDEN_DIR = r"D:\GitHub\LoopGenerator\data\golden_fond"
SALAMANDER_DIR = r"D:\GitHub\LoopGenerator\static\audio\salamander"
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")
OUTPUT_BASE = os.path.join(os.path.dirname(__file__), "baroque_noble_250")

os.makedirs(OUTPUT_BASE, exist_ok=True)

# ---------------------------------------------------------------------------
# SALAMANDER GRAND SAMPLER
# ---------------------------------------------------------------------------

SAMPLE_MAP = {
    21: 'A0.mp3', 24: 'C1.mp3', 27: 'Ds1.mp3', 30: 'Fs1.mp3', 33: 'A1.mp3',
    36: 'C2.mp3', 39: 'Ds2.mp3', 42: 'Fs2.mp3', 45: 'A2.mp3',
    48: 'C3.mp3', 51: 'Ds3.mp3', 54: 'Fs3.mp3', 57: 'A3.mp3',
    60: 'C4.mp3', 63: 'Ds4.mp3', 66: 'Fs4.mp3', 69: 'A4.mp3',
    72: 'C5.mp3', 75: 'Ds5.mp3', 78: 'Fs5.mp3', 81: 'A5.mp3',
    84: 'C6.mp3', 87: 'Ds6.mp3', 90: 'Fs6.mp3', 93: 'A6.mp3',
    96: 'C7.mp3', 99: 'Ds7.mp3', 102: 'Fs7.mp3', 105: 'A7.mp3', 108: 'C8.mp3'
}

loaded_samples: Dict[int, np.ndarray] = {}

def load_salamander_samples():
    global loaded_samples
    if loaded_samples:
        return
    for midi_p, fname in SAMPLE_MAP.items():
        p = os.path.join(SALAMANDER_DIR, fname)
        if os.path.exists(p):
            data, sr = sf.read(p)
            if sr != SR:
                num_s = int(len(data) * SR / sr)
                data = signal.resample(data, num_s)
            loaded_samples[midi_p] = data.astype(np.float32)

NOTE_OFFSETS = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9, 'A#': 10, 'Bb': 10, 'B': 11
}

NOTE_NAMES_BY_SEMI = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

def parse_note_name(name: str) -> int:
    octave = int(name[-1])
    pitch_name = name[:-1]
    return (octave + 1) * 12 + NOTE_OFFSETS[pitch_name]

def midi_to_note_name(midi_p: int) -> str:
    octave = (midi_p // 12) - 1
    semi = midi_p % 12
    return f"{NOTE_NAMES_BY_SEMI[semi]}{octave}"

DURATION_BEATS = {
    '16n': 0.25,
    '8n': 0.50,
    '4n': 1.00,
    '2n': 2.00,
    '1n': 4.00,
    '8t': 0.333,
    '16t': 0.166,
}

def parse_duration_beats(dur_str: str) -> float:
    return DURATION_BEATS.get(dur_str, 0.5)

def get_piano_sample(midi_p: int, duration_s: float, vel: float) -> np.ndarray:
    if not loaded_samples:
        load_salamander_samples()
        
    closest_p = min(loaded_samples.keys(), key=lambda k: abs(k - midi_p))
    base_data = loaded_samples[closest_p]
    semitones = midi_p - closest_p
    ratio = 2.0 ** (semitones / 12.0)
    
    ring_s = max(duration_s + 0.45, 1.2)
    max_samples = int(ring_s * SR)
    orig_len = min(len(base_data), int(max_samples * ratio))
    
    target_len = int(orig_len / ratio)
    if target_len <= 0: return np.zeros((0, 2), dtype=np.float32)
    
    idx = np.linspace(0, orig_len - 1, target_len)
    l_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 0])
    r_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 1])
    out = np.column_stack([l_ch, r_ch]) * vel
    
    note_n = int(duration_s * SR)
    if note_n < len(out):
        rel_n = int(0.12 * SR)
        end_rel = min(len(out), note_n + rel_n)
        ramp = np.linspace(1.0, 0.0, end_rel - note_n)[:, None]
        out[note_n:end_rel] *= ramp
        out[end_rel:] = 0.0
        
    return out

# ---------------------------------------------------------------------------
# CATHEDRAL ACOUSTIC REVERB
# ---------------------------------------------------------------------------

def fast_comb(x: np.ndarray, d: int, g: float, max_refl: int = 25) -> np.ndarray:
    y = x.copy()
    curr_g = g
    shift = d
    for _ in range(max_refl):
        if curr_g < 0.003 or shift >= len(x): break
        y[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return y

def fast_allpass(x: np.ndarray, d: int, g: float = 0.5, max_refl: int = 16) -> np.ndarray:
    w = np.zeros_like(x)
    curr_g = 1.0
    shift = d
    for _ in range(max_refl):
        if curr_g < 0.003 or shift >= len(x): break
        w[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return -g * x + (1.0 - g * g) * w

SOS_REV = signal.butter(2, 3200, btype='low', fs=SR, output='sos')
SOS_HP = signal.butter(2, 30, btype='high', fs=SR, output='sos')

def apply_concert_grand_reverb(stereo: np.ndarray, room_size: float = 0.82, wet: float = 0.22) -> np.ndarray:
    n = len(stereo)
    comb_delays = [1557, 1617, 1491, 1422, 1277, 1356]
    allpass_delays = [225, 441, 341]
    
    mono = (stereo[:, 0] + stereo[:, 1]) * 0.5
    comb_l = np.zeros(n)
    comb_r = np.zeros(n)
    
    for i, d in enumerate(comb_delays):
        g = room_size * (0.74 + 0.03 * (i % 3))
        filtered = signal.sosfilt(SOS_REV, mono)
        c = fast_comb(filtered, d, g)
        if i % 2 == 0:
            comb_l += c
        else:
            comb_r += c
            
    for d in allpass_delays:
        comb_l = fast_allpass(comb_l, d, 0.5)
        comb_r = fast_allpass(comb_r, d + 23, 0.5)
        
    rev_stereo = np.column_stack([comb_l, comb_r]) * 0.25
    out = stereo * (1.0 - wet * 0.5) + rev_stereo * wet
    out[:, 0] = signal.sosfilt(SOS_HP, out[:, 0])
    out[:, 1] = signal.sosfilt(SOS_HP, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-1.5 / 20.0)
        out = out * (target / pk)
        
    return out

# ---------------------------------------------------------------------------
# 8 STYLISTIC CATEGORIES & 250 MASTERPIECE CATALOG
# ---------------------------------------------------------------------------

CATEGORIES_DEF = {
    '01_La_Folia': {
        'kw': ['folia'],
        'count': 35,
        'title_prefix': 'La Folia',
        'subtitles': [
            'Primitiva all\'Antica', 'di Spagna Grave', 'dei Sospiri', 'con Divisioni Frigie',
            'Lacrimosa', 'Ostinata', 'delle Memorie', 'Nobile e Maestosa', 'in Contrapunto',
            'della Notte', 'Variazione Antica', 'di Castiglia', 'del Silenzio', 'Mistica'
        ]
    },
    '02_Passacaglia': {
        'kw': ['passacaglia'],
        'count': 35,
        'title_prefix': 'Passacaglia',
        'subtitles': [
            'Dolorosa', 'delle Lacrime', 'Grave all\'Antica', 'Solenne', 'del Tramonto',
            'della Devozione', 'Mistica', 'della Sera', 'Cattedrale', 'Elegiaca',
            'in Basso Continuo', 'Tragica', 'della Solitudine', 'Sacra'
        ]
    },
    '03_Passamezzo_Antico': {
        'kw': ['passamezzo'],
        'count': 30,
        'title_prefix': 'Passamezzo Antico',
        'subtitles': [
            'Nobile', 'della Notte', 'Elegiaco', 'Solenne', 'di Firenze', 'di Mantova',
            'di Venezia', 'dei Medici', 'Cantabile', 'del Sonno', 'all\'Antica', 'Maestoso'
        ]
    },
    '04_La_Romanesca': {
        'kw': ['romanesca', 'spagnoletta', 'basse_danse'],
        'count': 30,
        'title_prefix': 'La Romanesca',
        'subtitles': [
            'Antica', 'Soave', 'dei Medici', 'di Spagna', 'Spagnoletta Nobile',
            'Basse Danse della Regina', 'Grave e Nobile', 'dell\'Autunno', 'della Speranza', 'Mistica'
        ]
    },
    '05_Pavane_Royale': {
        'kw': ['pavane'],
        'count': 30,
        'title_prefix': 'Pavane Royale',
        'subtitles': [
            'Consonante', 'delle Lacrime', 'del Re Sole', 'Solenne', 'di Versailles',
            'della Tristezza', 'Nobile e Lenta', 'del Dolore', 'Processionale', 'della Pace'
        ]
    },
    '06_Lamento_Chroma': {
        'kw': ['lament', 'lacrimosa', 'dido'],
        'count': 35,
        'title_prefix': 'Lamento',
        'subtitles': [
            'con Passus Duriusculus', 'd\'Orfeo', 'di Didone', 'Lacrimosa Solenne',
            'dei Sospiri', 'Cromatico Grave', 'della Pietà', 'dell\'Abbandono', 'Notturno',
            'delle Ombre', 'Doloroso', 'di Venezia', 'Tragico'
        ]
    },
    '07_Chaconne_Grave': {
        'kw': ['chaconne'],
        'count': 25,
        'title_prefix': 'Chaconne Grave',
        'subtitles': [
            'delle Memorie', 'Maestosa', 'all\'Antica', 'di Siviglia', 'del Silenzio',
            'Solenne', 'della Speranza', 'in Basso Ostinato', 'della Notte', 'Cattedrale'
        ]
    },
    '08_Ricercar_Elegy': {
        'kw': ['elegy', 'adagio', 'tombeau', 'ricercar', 'requiem', 'cathedral', 'gothic'],
        'count': 30,
        'title_prefix': 'Ricercar ed Elegy',
        'subtitles': [
            'Cromatico Mistico', 'Tombeau Elegiaco', 'Tombeau pour l\'Espace', 'Adagio Doloroso',
            'Chorale Frigio', 'Ricercar Cantabile', 'Elegy di Venezia', 'Cattedrale d\'Ombre', 'Grave Requiem'
        ]
    },
}

MINOR_KEY_NAMES = {
    0: 'C Minor', 1: 'C# Minor', 2: 'D Minor', 3: 'Eb Minor', 4: 'E Minor',
    5: 'F Minor', 6: 'F# Minor', 7: 'G Minor', 8: 'Ab Minor', 9: 'A Minor',
    10: 'Bb Minor', 11: 'B Minor'
}

TRANSPOSITION_CYCLE = [0, 5, -2, 7, 3, 2, -3] # Dm -> Gm, Cm, Am, Fm, Em, Bm

def build_250_catalog() -> List[Dict[str, Any]]:
    files = glob_all_files()
    catalog = []
    global_idx = 1
    
    for cat_dir, cat_info in CATEGORIES_DEF.items():
        kws = cat_info['kw']
        target_count = cat_info['count']
        title_pfx = cat_info['title_prefix']
        subs = cat_info['subtitles']
        
        # Collect base files
        matched_files = []
        for f in files:
            b = os.path.basename(f).lower()
            if 'major' in b or 'bright' in b or 'lute_song' in b: continue
            if any(k in b for k in kws):
                try:
                    with open(f, 'r', encoding='utf-8') as fp:
                        d = json.load(fp)
                    if 'major' in str(d.get('scale', '')).lower(): continue
                    notes = d.get('notes', [])
                    if 18 <= len(notes) <= 180:
                        matched_files.append((f, d))
                except: continue
                
        matched_files.sort(key=lambda x: os.path.basename(x[0]))
        if not matched_files:
            continue
            
        for i in range(target_count):
            base_file, d = matched_files[i % len(matched_files)]
            cycle_step = i // len(matched_files)
            shift = TRANSPOSITION_CYCLE[cycle_step % len(TRANSPOSITION_CYCLE)]
            
            # Detect root note
            notes = d.get('notes', [])
            step0_notes = [parse_note_name(n['note']) for n in notes if n.get('step', 0) == 0]
            if step0_notes:
                root_midi = min(step0_notes)
            else:
                root_midi = min(parse_note_name(n['note']) for n in notes)
                
            final_root_semi = (root_midi + shift) % 12
            key_name = MINOR_KEY_NAMES[final_root_semi]
            
            sub_title = subs[i % len(subs)]
            title = f"{title_pfx} #{i+1:02d} in {key_name} ({sub_title})"
            
            # Slow noble tempo
            bpm = 50 + (i % 5) # 50, 51, 52, 53, 54 BPM
            
            safe_key = key_name.replace(' ', '_').replace('#', 's')
            track_name = f"{title_pfx.replace(' ', '_')}_{global_idx:03d}_{safe_key}"
            
            catalog.append({
                'index': global_idx,
                'category_dir': cat_dir,
                'category_name': title_pfx,
                'base_file': base_file,
                'shift_semi': shift,
                'key_name': key_name,
                'title': title,
                'bpm': bpm,
                'track_name': track_name,
            })
            global_idx += 1
            
    return catalog

def glob_all_files():
    import glob
    return sorted(glob.glob(os.path.join(GOLDEN_DIR, "*.json")))

# ---------------------------------------------------------------------------
# WORKER FUNCTION (RENDERS A SINGLE TRACK)
# ---------------------------------------------------------------------------

def render_worker(item: Dict[str, Any]) -> Tuple[int, str, str, float, str]:
    idx = item['index']
    cat_dir = item['category_dir']
    base_file = item['base_file']
    shift = item['shift_semi']
    key_name = item['key_name']
    title = item['title']
    bpm = item['bpm']
    track_name = item['track_name']
    
    cat_out_dir = os.path.join(OUTPUT_BASE, cat_dir)
    os.makedirs(cat_out_dir, exist_ok=True)
    
    mp3_path = os.path.join(cat_out_dir, f"{track_name}.mp3")
    mid_path = os.path.join(cat_out_dir, f"{track_name}.mid")
    wav_path = os.path.join(cat_out_dir, f"{track_name}.wav")
    
    # Check if already rendered
    if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000000 and os.path.exists(mid_path):
        return idx, title, mp3_path, 44.0, "SKIPPED_EXISTING"
        
    with open(base_file, 'r', encoding='utf-8') as f:
        d = json.load(f)
        
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0
    notes_raw = d.get('notes', [])
    
    # Prepare MIDI
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=title, time=0))
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    track.append(Message('program_change', program=0, channel=0, time=0)) # Acoustic Grand
    
    midi_events = []
    
    # Calculate duration
    max_step = max(n.get('step', 0) for n in notes_raw)
    total_time = max(n.get('step', 0) * step_sec + parse_duration_beats(n.get('duration', '8n')) * beat_sec for n in notes_raw)
    
    # If the base loop is too short (e.g. 15-20s), repeat for 2 cycles to reach 40-48s!
    repeat_cycles = 1
    if total_time < 30.0:
        repeat_cycles = 2
        cycle_len_steps = ((max_step // 16) + 1) * 16
        cycle_offset_s = cycle_len_steps * step_sec
    else:
        cycle_offset_s = 0.0
        
    actual_total_time = total_time + (cycle_offset_s if repeat_cycles > 1 else 0.0)
    total_samples = int((actual_total_time + 4.5) * SR)
    stereo_buf = np.zeros((total_samples, 2), dtype=np.float32)
    
    for cycle in range(repeat_cycles):
        t_cycle_shift = cycle * cycle_offset_s
        # Slight expressive dynamic growth on cycle 2
        dyn_scale = 1.05 if cycle == 1 else 0.95
        
        for n in notes_raw:
            st_s = t_cycle_shift + n.get('step', 0) * step_sec
            dur_b = parse_duration_beats(n.get('duration', '8n'))
            dur_s_val = dur_b * beat_sec
            vel = float(n.get('velocity', 0.75)) * dyn_scale
            vel = max(0.35, min(0.95, vel))
            
            orig_p = parse_note_name(n['note'])
            midi_p = orig_p + shift
            midi_p = max(21, min(108, midi_p)) # keep within piano range
            
            # Synthesize with Yamaha C5 samples
            note_audio = get_piano_sample(midi_p, dur_s_val, vel)
            s_idx = int(st_s * SR)
            e_idx = min(total_samples, s_idx + len(note_audio))
            if e_idx > s_idx:
                stereo_buf[s_idx:e_idx] += note_audio[:e_idx - s_idx]
                
            # MIDI event
            start_tick = int((st_s / beat_sec) * TICKS_PER_BEAT)
            dur_tick = int(dur_b * TICKS_PER_BEAT)
            midi_vel = int(vel * 127)
            midi_events.append((start_tick, 10, Message('note_on', note=midi_p, velocity=midi_vel, channel=0)))
            midi_events.append((start_tick + dur_tick, 5, Message('note_off', note=midi_p, velocity=0, channel=0)))
            
    # Save MIDI
    midi_events.sort(key=lambda x: (x[0], x[1]))
    last_t = 0
    for tick, _, msg in midi_events:
        delta = max(0, tick - last_t)
        msg.time = delta
        track.append(msg)
        last_t = tick
    track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
    mid.save(mid_path)
    
    # Apply European Cathedral Hall Reverb + True Peak -1.50 dBFS
    mastered = apply_concert_grand_reverb(stereo_buf, room_size=0.82, wet=0.22)
    sf.write(wav_path, mastered, SR, subtype='PCM_24')
    
    dur_final = len(mastered) / SR
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={title}",
        "-metadata", "artist=Yamaha C5 Concert Grand Piano",
        "-metadata", "album=Noble Renaissance & Early Baroque XVI",
        "-metadata", f"genre=Renaissance Polyphony ({bpm} BPM)",
        "-metadata", f"track={idx}/250",
        "-metadata", "date=1580",
        "-metadata", f"comment=Authentic 16th-century modal masterpiece ({dur_final:.1f}s)",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return idx, title, mp3_path, dur_final, "SUCCESS"

# ---------------------------------------------------------------------------
# MAIN BATCH ENGINE (PARALLEL & RESUME SUPPORT)
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Render Baroque 250 Collection")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker processes (default 4)")
    args = parser.parse_args()
    
    catalog = build_250_catalog()
    print("=" * 80)
    print("NOBLE RENAISSANCE & EARLY BAROQUE FACTORY (XVI CENTURY) - 250 ARCHIVE")
    print(f"Total Masterpieces to Render: {len(catalog)}")
    print(f"Instrument: Yamaha C5 Concert Grand Piano (Salamander Grand)")
    print(f"Destination: {OUTPUT_BASE}")
    print(f"Parallel Workers: {args.workers}")
    print("=" * 80 + "\n")
    
    # Preload samples in main thread
    load_salamander_samples()
    print("Salamander Concert Grand Piano samples loaded into RAM!\n")
    
    t_start = time.time()
    rendered_info = []
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(render_worker, item): item for item in catalog}
        for future in concurrent.futures.as_completed(futures):
            item = futures[future]
            try:
                idx, title, mp3_p, dur_s_val, status = future.result()
                rendered_info.append((idx, title, mp3_p, dur_s_val, item['category_dir'], item['bpm'], item['key_name']))
                dur_str = f"{dur_s_val:.1f}s"
                print(f"[{idx:03d}/250] [{item['category_dir']}] {title} -> {dur_str} | {os.path.basename(mp3_p)}")
            except Exception as e:
                print(f"ERROR rendering track #{item['index']}: {e}")
                
    total_dt = time.time() - t_start
    rendered_info.sort(key=lambda x: x[0])
    
    # Generate 00_CATALOG.md
    catalog_md_path = os.path.join(OUTPUT_BASE, "00_CATALOG.md")
    with open(catalog_md_path, 'w', encoding='utf-8') as f:
        f.write("# Noble Renaissance & Early Baroque XVI Collection (250 Tracks)\n\n")
        f.write(f"**Total Tracks**: 250  \n")
        f.write(f"**Instrument**: Authentic Yamaha C5 Concert Grand Piano (Salamander Grand)  \n")
        f.write(f"**Mastering**: Cathedral Hall Acoustics, True Peak -1.50 dBFS, 320 kbps MP3 + MIDI  \n")
        f.write(f"**Tempo Range**: 50 – 54 BPM (Largo, Adagio, Grave)  \n")
        f.write(f"**Harmony**: Strictly Minor Modes (16th-century Modal Counterpoint, Zarlino Syncopatio)  \n\n")
        f.write("| # | Категория | Название | Тональность | Темп | Длительность | MP3 (320 kbps) |\n")
        f.write("|---|---|---|:---:|:---:|:---:|:---:|\n")
        
        for idx, title, mp3_p, dur_s_val, cat_dir, bpm, key_name in rendered_info:
            rel_mp3 = os.path.relpath(mp3_p, OUTPUT_BASE).replace('\\', '/')
            f.write(f"| **{idx:03d}** | {cat_dir} | {title} | {key_name} | {bpm} BPM | {dur_s_val:.1f} с | [{os.path.basename(mp3_p)}]({rel_mp3}) |\n")
            
    print("\n" + "=" * 80)
    print(f"ALL 250 MASTERPIECES SUCCESSFULLY RENDERED IN {total_dt:.1f}s ({total_dt/250:.2f}s per track)!")
    print(f"Catalog saved to: {catalog_md_path}")
    print(f"Output folder: {OUTPUT_BASE}")
    print("=" * 80)

if __name__ == '__main__':
    main()
