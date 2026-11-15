"""
Golden Fond High-Fidelity Studio Renderer & Generator
Renders compositions from D:\\GitHub\\LoopGenerator\\data\\golden_fond
using the authentic Yamaha C5 Concert Grand Piano (Salamander Grand)
and procedural variations engine.
"""

import os
import sys
import json
import time
import argparse
import subprocess
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
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "golden_fond_audio")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# SALAMANDER CONCERT GRAND PIANO SAMPLER ENGINE
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

def parse_note_name(name: str) -> int:
    octave = int(name[-1])
    pitch_name = name[:-1]
    return (octave + 1) * 12 + NOTE_OFFSETS[pitch_name]

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
    
    # Ring time includes note duration + natural acoustic bloom
    ring_s = max(duration_s + 0.45, 1.2)
    max_samples = int(ring_s * SR)
    orig_len = min(len(base_data), int(max_samples * ratio))
    
    # Fast linear interpolation resample
    target_len = int(orig_len / ratio)
    if target_len <= 0: return np.zeros((0, 2), dtype=np.float32)
    
    idx = np.linspace(0, orig_len - 1, target_len)
    l_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 0])
    r_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 1])
    out = np.column_stack([l_ch, r_ch]) * vel
    
    # Soft damper release envelope
    note_n = int(duration_s * SR)
    if note_n < len(out):
        rel_n = int(0.12 * SR)
        end_rel = min(len(out), note_n + rel_n)
        ramp = np.linspace(1.0, 0.0, end_rel - note_n)[:, None]
        out[note_n:end_rel] *= ramp
        out[end_rel:] = 0.0
        
    return out

# ---------------------------------------------------------------------------
# STUDIO CONCERT REVERB
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
        g = room_size * (0.78 + 0.02 * (i % 2))
        y = fast_comb(mono, d, g)
        if i % 2 == 0: comb_l += y
        else: comb_r += y
        
    for d in allpass_delays:
        comb_l = fast_allpass(comb_l, d)
        comb_r = fast_allpass(comb_r, d)
        
    comb_l = signal.sosfilt(SOS_REV, comb_l)
    comb_r = signal.sosfilt(SOS_REV, comb_r)
    rev_stereo = np.column_stack([comb_l, comb_r])
    
    peak_rev = np.max(np.abs(rev_stereo)) + 1e-6
    peak_dry = np.max(np.abs(stereo)) + 1e-6
    rev_stereo = rev_stereo * (peak_dry / peak_rev)
    
    out = stereo * (1.0 - wet * 0.5) + rev_stereo * wet
    out[:, 0] = signal.sosfilt(SOS_HP, out[:, 0])
    out[:, 1] = signal.sosfilt(SOS_HP, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-1.5 / 20.0)
        out = out * (target / pk)
        
    return out

# ---------------------------------------------------------------------------
# LOOP RENDERING & DEVELOPMENT ENGINE (~40-50s)
# ---------------------------------------------------------------------------

def render_golden_loop(json_data: Dict[str, Any], target_duration_s: float = 45.0,
                       output_prefix: str = "golden_track") -> Tuple[str, str]:
    title = json_data.get('name', 'Golden Loop')
    bpm = json_data.get('bpm', 180)
    swing = json_data.get('swing', 0.0)
    notes_raw = json_data.get('notes', [])
    steps_total = json_data.get('steps', 128)
    
    # Timing calculation:
    # 8 steps = 1 beat (quarter note)
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 8.0
    loop_duration = steps_total * step_sec
    
    # Calculate how many cycles to reach target duration (~40-50s)
    num_cycles = max(2, int(round(target_duration_s / loop_duration)))
    actual_duration = num_cycles * loop_duration
    
    # Prepare MIDI
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=title, time=0))
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    track.append(Message('program_change', program=0, channel=0, time=0)) # Acoustic Grand Piano
    
    # Prepare audio buffer
    total_samples = int((actual_duration + 3.0) * SR)
    stereo_buf = np.zeros((total_samples, 2), dtype=np.float32)
    
    midi_events = []
    
    # Render with musical development across cycles (Intro -> Expansion -> Climax -> Resolution)
    for cycle in range(num_cycles):
        cycle_offset_s = cycle * loop_duration
        cycle_factor = 1.0
        # Dynamic progression:
        # Cycle 0: delicate cantabile (0.88x)
        # Middle cycles: growing warmth and passion (1.0x - 1.1x)
        # Climax cycle: passionate fortissimo (1.15x)
        if cycle == 0: cycle_factor = 0.90
        elif cycle == num_cycles - 2: cycle_factor = 1.12
        elif cycle == num_cycles - 1: cycle_factor = 1.00 # gentle resolution
        
        for n_item in notes_raw:
            step = n_item.get('step', 0)
            note_str = n_item.get('note')
            if not note_str: continue
            
            dur_str = n_item.get('duration', '8n')
            vel_base = float(n_item.get('velocity', 0.8)) * cycle_factor
            vel_base = max(0.35, min(1.0, vel_base))
            
            midi_p = parse_note_name(note_str)
            dur_beats = parse_duration_beats(dur_str)
            dur_s = dur_beats * beat_sec
            
            # Swing calculation (if specified, pushes odd 8th-note steps slightly)
            swing_shift = 0.0
            if swing > 0 and (step % 8) == 4:
                swing_shift = (swing / 100.0) * step_sec * 1.5
                
            start_s = cycle_offset_s + step * step_sec + swing_shift
            
            # Audio synthesis via Salamander Grand Piano
            note_audio = get_piano_sample(midi_p, dur_s, vel_base)
            s_idx = int(start_s * SR)
            e_idx = min(total_samples, s_idx + len(note_audio))
            if e_idx > s_idx:
                stereo_buf[s_idx:e_idx] += note_audio[:e_idx - s_idx]
                
            # MIDI event
            start_tick = int((start_s / beat_sec) * TICKS_PER_BEAT)
            dur_tick = int(dur_beats * TICKS_PER_BEAT)
            midi_vel = int(vel_base * 127)
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
    
    midi_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.mid")
    mid.save(midi_path)
    
    # Process audio with concert acoustics
    final_audio = apply_concert_grand_reverb(stereo_buf, room_size=0.82, wet=0.22)
    wav_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.wav")
    mp3_path = os.path.join(OUTPUT_DIR, f"{output_prefix}.mp3")
    
    sf.write(wav_path, final_audio, SR, subtype='PCM_24')
    
    # FFmpeg MP3 encoding with tags
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={title}",
        "-metadata", "artist=Concert Grand Piano (Salamander)",
        "-metadata", "album=Golden Fond Masterpieces",
        "-metadata", f"genre=Classical Piano ({bpm} BPM)",
        "-metadata", f"comment=Golden Fond Studio Piano Loop ({actual_duration:.1f}s)",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return midi_path, mp3_path

# ---------------------------------------------------------------------------
# MAIN BATCH RUNNER
# ---------------------------------------------------------------------------

SHOWCASE_FILES = [
    ("alberti_agitated_presto.json", "01_alberti_agitated_presto"),
    ("alberti_classic_mozartian.json", "02_alberti_classic_mozartian"),
    ("alberti_romantic_tears.json", "03_alberti_romantic_tears"),
    ("amber_resonance.json", "04_neoclassical_amber_resonance"),
    ("ballad-celtic_storm_tide.json", "05_ballad_celtic_storm_tide"),
    ("baroque_elegy_-_toccata_in_f_minor.json", "06_toccata_in_f_minor"),
    ("folia_baroque_virtuoso.json", "07_folia_baroque_virtuoso"),
    ("baroque_lament_-_didos_descending_chromatic.json", "08_didos_descending_chromatic"),
]

def main():
    print("=" * 75)
    print("GOLDEN FOND STUDIO PIANO RENDERER (YAMAHA C5 CONCERT GRAND)")
    print(f"Source: {GOLDEN_DIR}")
    print(f"Destination: {OUTPUT_DIR}")
    print("=" * 75)
    
    load_salamander_samples()
    print("Salamander Concert Grand Piano samples loaded into RAM!\n")
    
    for idx, (json_name, prefix) in enumerate(SHOWCASE_FILES, start=1):
        full_p = os.path.join(GOLDEN_DIR, json_name)
        if not os.path.exists(full_p):
            print(f"[{idx}] Missing: {json_name}")
            continue
            
        with open(full_p, 'r', encoding='utf-8') as fp:
            data = json.load(fp)
            
        bpm = data.get('bpm', 180)
        title = data.get('name', json_name)
        print(f"[{idx:02d}/{len(SHOWCASE_FILES)}] Rendering: {title} ({bpm} BPM)...")
        t0 = time.time()
        midi_p, mp3_p = render_golden_loop(data, target_duration_s=45.0, output_prefix=prefix)
        dt = time.time() - t0
        print(f"   -> Rendered in {dt:.1f}s | MP3: {os.path.basename(mp3_p)}")
        
    print("\n" + "=" * 75)
    print(f"SUCCESS: All showcase tracks rendered into {OUTPUT_DIR}")
    print("=" * 75)

if __name__ == "__main__":
    main()
