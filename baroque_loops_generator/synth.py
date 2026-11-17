"""
Acoustic Sampler, DSP Filters, and File Exporters for Yamaha C5 Grand Piano
"""

import os
import subprocess
import json
import numpy as np
import scipy.signal as signal
import soundfile as sf
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from typing import Dict, List, Tuple, Any

from baroque_loops_generator.models import DURATION_BEATS
from baroque_loops_generator.theory import note_name_to_midi

SR = 44100
TICKS_PER_BEAT = 480
SALAMANDER_DIR = r"D:\GitHub\LoopGenerator\static\audio\salamander"

FFMPEG_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "..", "bin", "ffmpeg.exe"),
    r"C:\ProgramData\chocolatey\bin\ffmpeg.EXE",
    "ffmpeg"
]
FFMPEG_PATH = "ffmpeg"
for c in FFMPEG_CANDIDATES:
    if os.path.exists(c):
        FFMPEG_PATH = c
        break

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
    if loaded_samples: return
    for midi_p, fname in SAMPLE_MAP.items():
        p = os.path.join(SALAMANDER_DIR, fname)
        if os.path.exists(p):
            data, sr = sf.read(p)
            if sr != SR:
                num_s = int(len(data) * SR / sr)
                data = signal.resample(data, num_s)
            loaded_samples[midi_p] = data.astype(np.float32)

def get_piano_sample(midi_p: int, duration_s: float, vel: float) -> np.ndarray:
    if not loaded_samples: load_salamander_samples()
    closest_p = min(loaded_samples.keys(), key=lambda k: abs(k - midi_p))
    base_data = loaded_samples[closest_p]
    semitones = midi_p - closest_p
    ratio = 2.0 ** (semitones / 12.0)
    
    # Allow natural resonance
    ring_s = max(duration_s + 0.60, 1.80)
    max_samples = int(ring_s * SR)
    orig_len = min(len(base_data), int(max_samples * ratio))
    target_len = int(orig_len / ratio)
    if target_len <= 0: return np.zeros((0, 2), dtype=np.float32)
    
    idx = np.linspace(0, orig_len - 1, target_len)
    l_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 0])
    r_ch = np.interp(idx, np.arange(orig_len), base_data[:orig_len, 1])
    out = np.column_stack([l_ch, r_ch]) * vel
    
    # Natural damper decay: 350ms smooth acoustic decay
    note_n = int(duration_s * SR)
    if note_n < len(out):
        rel_n = int(0.35 * SR)
        end_rel = min(len(out), note_n + rel_n)
        ramp = np.linspace(1.0, 0.0, end_rel - note_n)[:, None]
        out[note_n:end_rel] *= ramp
        out[end_rel:] = 0.0
    return out

def fast_comb(x: np.ndarray, d: int, g: float, max_refl: int = 25) -> np.ndarray:
    y = x.copy()
    curr_g, shift = g, d
    for _ in range(max_refl):
        if curr_g < 0.003 or shift >= len(x): break
        y[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return y

def fast_allpass(x: np.ndarray, d: int, g: float = 0.5, max_refl: int = 16) -> np.ndarray:
    w = np.zeros_like(x)
    curr_g, shift = 1.0, d
    for _ in range(max_refl):
        if curr_g < 0.003 or shift >= len(x): break
        w[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return -g * x + (1.0 - g * g) * w

SOS_REV = signal.butter(2, 3800, btype='low', fs=SR, output='sos')
SOS_HP = signal.butter(2, 35, btype='high', fs=SR, output='sos')

def apply_chamber_reverb(stereo: np.ndarray, room_size: float = 0.72, wet: float = 0.16) -> np.ndarray:
    n = len(stereo)
    comb_delays = [1557, 1617, 1491, 1422, 1277, 1356]
    allpass_delays = [225, 441, 341]
    
    mono = (stereo[:, 0] + stereo[:, 1]) * 0.5
    comb_l, comb_r = np.zeros(n), np.zeros(n)
    
    for i, d in enumerate(comb_delays):
        g = room_size * (0.72 + 0.02 * (i % 3))
        filtered = signal.sosfilt(SOS_REV, mono)
        c = fast_comb(filtered, d, g)
        if i % 2 == 0: comb_l += c
        else: comb_r += c
            
    for d in allpass_delays:
        comb_l = fast_allpass(comb_l, d, 0.48)
        comb_r = fast_allpass(comb_r, d + 23, 0.48)
        
    rev_stereo = np.column_stack([comb_l, comb_r]) * 0.22
    out = stereo * (1.0 - wet * 0.4) + rev_stereo * wet
    out[:, 0] = signal.sosfilt(SOS_HP, out[:, 0])
    out[:, 1] = signal.sosfilt(SOS_HP, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-1.5 / 20.0) # -1.50 dBFS True Peak standard
        out = out * (target / pk)
    return out

def parse_dur_beats(dur_str: str) -> float:
    return DURATION_BEATS.get(dur_str, 0.50)

def render_piece(
    item: Dict[str, Any],
    notes: List[Dict[str, Any]],
    output_dir: str
) -> Tuple[str, str, str, float]:
    """
    Renders notes to MP3 (320k), Type 1 MIDI, and Tone.js JSON.
    Returns: (mp3_path, mid_path, json_path, duration_seconds)
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = item['filename']
    bpm = item['bpm']
    meter_str = item['meter']
    key_code = item['key_code']
    steps = item['steps']
    
    mp3_path = os.path.join(output_dir, f"{filename}.mp3")
    mid_path = os.path.join(output_dir, f"{filename}.mid")
    json_path = os.path.join(output_dir, f"{filename}.json")
    
    # 1. Tone.js JSON export
    loop_obj = [{
        "name": f"---{filename}",
        "bpm": bpm,
        "instrument": "piano",
        "steps": steps,
        "key": key_code.split('_')[0].replace('m', ''),
        "scale": "Dorian" if "Dor" in key_code else "Minor",
        "swing": 0.0,
        "notes": notes
    }]
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(loop_obj, f, ensure_ascii=False, indent=2)
        
    # 2. Timing and Audio Synthesis
    beat_sec = 60.0 / bpm
    step_sec = beat_sec / 4.0
    total_audio_s = (steps * step_sec) + 3.5
    total_samples = int(total_audio_s * SR)
    stereo_buf = np.zeros((total_samples, 2), dtype=np.float32)
    
    # MIDI setup
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    track = MidiTrack()
    mid.tracks.append(track)
    track.append(MetaMessage('track_name', name=filename, time=0))
    track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    m_parts = meter_str.split('/')
    track.append(MetaMessage('time_signature', numerator=int(m_parts[0]), denominator=int(m_parts[1]), time=0))
    track.append(Message('program_change', program=0, channel=0, time=0)) # Acoustic Grand
    
    notes_sorted = sorted(notes, key=lambda x: (x['step'], note_name_to_midi(x['note'])))
    midi_events = []
    step_counts: Dict[int, int] = {}
    
    for n in notes_sorted:
        st = n['step']
        p_name = n['note']
        midi_p = note_name_to_midi(p_name)
        dur_beats = parse_dur_beats(n['duration'])
        dur_s = dur_beats * beat_sec
        vel = n['velocity']
        
        # Style Brisé micro-stagger: 32ms between simultaneous chord voices
        order = step_counts.get(st, 0)
        step_counts[st] = order + 1
        stagger_s = 0.032 * order
        start_s = st * step_sec + stagger_s
        
        # Piano synthesis
        note_audio = get_piano_sample(midi_p, dur_s, vel)
        s_idx = int(start_s * SR)
        e_idx = min(total_samples, s_idx + len(note_audio))
        if e_idx > s_idx:
            stereo_buf[s_idx:e_idx] += note_audio[:e_idx - s_idx]
            
        # MIDI events
        start_tick = int((start_s / beat_sec) * TICKS_PER_BEAT)
        dur_tick = int(dur_beats * TICKS_PER_BEAT)
        m_vel = int(np.clip(vel * 127, 25, 127))
        midi_events.append((start_tick, 10, Message('note_on', note=midi_p, velocity=m_vel, channel=0)))
        midi_events.append((start_tick + dur_tick, 5, Message('note_off', note=midi_p, velocity=0, channel=0)))
        
    midi_events.sort(key=lambda x: (x[0], x[1]))
    last_t = 0
    for tick, _, msg in midi_events:
        delta = max(0, tick - last_t)
        msg.time = delta
        track.append(msg)
        last_t = tick
    track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
    mid.save(mid_path)
    
    # Process Reverb & True Peak -1.50 dBFS
    rev_audio = apply_chamber_reverb(stereo_buf, room_size=0.72, wet=0.16)
    wav_temp = os.path.join(output_dir, f"{filename}_temp.wav")
    sf.write(wav_temp, rev_audio, SR, subtype='PCM_24')
    
    # FFmpeg MP3 encoding (320 kbps)
    vol_num = item.get('volume', 1)
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_temp,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={filename}",
        "-metadata", "artist=Yamaha C5 Concert Grand",
        "-metadata", f"album=Early Baroque & Renaissance Masterpieces - Tom {vol_num:02d}",
        "-metadata", f"genre=Early Baroque / Renaissance ({bpm} BPM)",
        "-metadata", f"comment=Strict Matrix Masterpiece ({item.get('form_name','')}, {item.get('key_name','')}, {item.get('texture_name','')})",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_temp):
        os.remove(wav_temp)
        
    actual_dur = len(rev_audio) / SR
    return mp3_path, mid_path, json_path, actual_dur
