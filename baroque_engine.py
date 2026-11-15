"""
Baroque Music Procedural Generation & DSP Synthesis Engine
Provides authentic algorithmic composition across contrasting Baroque archetypes:
1. Toccata (Stylus Fantasticus - virtuosic solo harpsichord cascades)
2. French Overture (Majestic double-dotted royal court fanfare)
3. La Folia con Variazioni (Stately theme accelerating into rapid diminutions)
4. Organ Chorale Prelude (Monumental cathedral organ, 4-part polyphony & 16' pedal)
5. Gigue / Saltarello (Lively bouncing 6/8 compound triple meter dance)
6. Dido's Lament (Passus duriusculus chromatic descent & agonizing suspensions)
7. Chaconne Buildup (3/4 ostinato with bariolage arpeggio waves)
8. Pastoral Siciliana (Gentle swaying 6/8 flauto dolce & lute)
9. Concerto Grosso (Vivaldian motoric driving strings & stile concitato)
"""

import os
import math
import random
import subprocess
import numpy as np
import scipy.signal as signal
import soundfile as sf
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

SR = 44100
TICKS_PER_BEAT = 480
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")

# ---------------------------------------------------------------------------
# PRECOMPUTED FILTERS (ACOUSTIC BODY FORMANTS & ROOM SHAPING)
# ---------------------------------------------------------------------------

SOS_HARPSICHORD = signal.butter(3, [220, 6500], btype='bandpass', fs=SR, output='sos')
SOS_GAMBA = signal.butter(3, 1400, btype='low', fs=SR, output='sos')
SOS_VIOLIN = signal.butter(3, [350, 4800], btype='bandpass', fs=SR, output='sos')
SOS_THEORBO = signal.butter(3, 1200, btype='low', fs=SR, output='sos')
SOS_FLUTE = signal.butter(3, 2800, btype='low', fs=SR, output='sos')
SOS_ORGAN_MANUAL = signal.butter(3, 2400, btype='low', fs=SR, output='sos')
SOS_ORGAN_PEDAL = signal.butter(3, 600, btype='low', fs=SR, output='sos')
SOS_REV_DAMP = signal.butter(2, 2400, btype='low', fs=SR, output='sos')
SOS_HP = signal.butter(2, 35, btype='high', fs=SR, output='sos')

def midi_to_freq(note: int) -> float:
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))

# ---------------------------------------------------------------------------
# HIGH-FIDELITY DSP INSTRUMENT SYNTHESIS
# ---------------------------------------------------------------------------

def render_harpsichord(freq: float, duration_sec: float, velocity: int = 64) -> np.ndarray:
    """Crisp quill plectrum impulse + metallic/gut harmonics with rapid high-frequency decay"""
    ring_sec = min(duration_sec + 0.8, 1.8)
    n = int(ring_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, ring_sec, n, endpoint=False)
    
    # Quill plucking impulse click
    click_len = min(int(0.004 * SR), n)
    click = np.zeros(n)
    click[:click_len] = np.sin(2 * np.pi * 3400 * t[:click_len]) * np.linspace(1, 0, click_len) * 0.38
    
    sig = np.zeros(n)
    harmonics = [(1, 1.0, 2.0), (2, 0.70, 2.9), (3, 0.48, 3.8), (4, 0.32, 4.8), (5, 0.20, 5.8), (6, 0.12, 7.0), (7, 0.06, 8.5)]
    pitch_scale = (freq / 220.0) ** 0.32
    phase_base = 2 * np.pi * freq * t
    for h, amp, decay_rate in harmonics:
        if freq * h < SR * 0.44:
            sig += amp * np.sin(h * phase_base) * np.exp((-decay_rate * pitch_scale) * t)
            
    sig += click
    att_samples = int(0.002 * SR)
    if att_samples < n:
        sig[:att_samples] *= np.sin(np.linspace(0, np.pi / 2, att_samples))
        
    sig = signal.sosfilt(SOS_HARPSICHORD, sig)
    
    # Key release damper
    note_samples = int(duration_sec * SR)
    if note_samples < n:
        rel_len = int(0.035 * SR)
        end_rel = min(n, note_samples + rel_len)
        sig[note_samples:end_rel] *= np.linspace(1.0, 0.0, end_rel - note_samples)
        sig[end_rel:] = 0.0
        
    return sig * (velocity / 127.0) * 0.40

def render_gamba(freq: float, duration_sec: float, velocity: int = 65) -> np.ndarray:
    """Bowed gut strings: warm wood core, gentle bow catch, authentic late vibrato"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    vib_onset = np.clip((t - 0.35) / 0.45, 0, 1)
    vib = np.sin(2 * np.pi * 4.6 * t) * (0.0035 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    harmonics = [1.0, 0.65, 0.40, 0.25, 0.14, 0.08, 0.04, 0.02]
    sig = np.zeros(n)
    for i, h_amp in enumerate(harmonics, start=1):
        if freq * i < SR * 0.44:
            sig += h_amp * np.sin(i * phase)
            
    sig = signal.sosfilt(SOS_GAMBA, sig)
    
    att = int(min(0.09 * SR, n * 0.25))
    rel = int(min(0.18 * SR, n * 0.25))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.36

def render_baroque_violin(freq: float, duration_sec: float, velocity: int = 65) -> np.ndarray:
    """Bright, agile gut-string violin with fast bow response for concertos & toccatas"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    vib_onset = np.clip((t - 0.25) / 0.35, 0, 1)
    vib = np.sin(2 * np.pi * 5.2 * t) * (0.0042 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    harmonics = [1.0, 0.75, 0.55, 0.35, 0.22, 0.14, 0.08, 0.04]
    sig = np.zeros(n)
    for i, h_amp in enumerate(harmonics, start=1):
        if freq * i < SR * 0.44:
            sig += h_amp * np.sin(i * phase)
            
    sig = signal.sosfilt(SOS_VIOLIN, sig)
    
    # Sharp bow attack for motoric 16ths
    att = int(min(0.025 * SR, n * 0.2))
    rel = int(min(0.08 * SR, n * 0.2))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.36

def render_theorbo(freq: float, duration_sec: float, velocity: int = 62) -> np.ndarray:
    """Plucked deep bass strings with long resonant ring and warm wood tone"""
    ring_sec = min(max(duration_sec, 2.5), 3.2)
    n = int(ring_sec * SR)
    t = np.linspace(0, ring_sec, n, endpoint=False)
    
    sig = np.zeros(n)
    harmonics = [(1, 1.0, 0.65), (2, 0.55, 1.1), (3, 0.28, 1.8), (4, 0.12, 2.6), (5, 0.05, 3.4)]
    phase_base = 2 * np.pi * freq * t
    for h, amp, decay_rate in harmonics:
        if freq * h < SR * 0.44:
            sig += amp * np.sin(h * phase_base) * np.exp(-decay_rate * t)
            
    att_samples = int(0.005 * SR)
    if att_samples < n:
        sig[:att_samples] *= np.sin(np.linspace(0, np.pi / 2, att_samples))
        
    sig = signal.sosfilt(SOS_THEORBO, sig)
    return sig * (velocity / 127.0) * 0.35

def render_flauto_dolce(freq: float, duration_sec: float, velocity: int = 62) -> np.ndarray:
    """Baroque Recorder with breath chiff attack and pastoral sweetness"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    vib_onset = np.clip((t - 0.25) / 0.35, 0, 1)
    vib = np.sin(2 * np.pi * 5.0 * t) * (0.0040 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    sig = 1.00 * np.sin(phase) + 0.30 * np.sin(2 * phase) + 0.10 * np.sin(3 * phase) + 0.02 * np.sin(4 * phase)
    
    chiff_len = int(min(0.025 * SR, n))
    if chiff_len > 0:
        chiff = np.sin(2 * np.pi * 2800 * t[:chiff_len]) * 0.14 * np.linspace(1, 0, chiff_len)
        sig[:chiff_len] += chiff
        
    sig = signal.sosfilt(SOS_FLUTE, sig)
    
    att = int(min(0.06 * SR, n * 0.22))
    rel = int(min(0.12 * SR, n * 0.22))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.34

def render_positive_organ(freq: float, duration_sec: float, velocity: int = 65) -> np.ndarray:
    """Chamber / Positive Pipe Organ: 8' Stopped Flute + 4' Principal blend"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    phase = 2 * np.pi * freq * t
    
    sig = (
        1.00 * np.sin(phase) +
        0.48 * np.sin(2 * phase) +
        0.20 * np.sin(3 * phase) +
        0.08 * np.sin(4 * phase) +
        0.03 * np.sin(5 * phase)
    )
    sig = signal.sosfilt(SOS_ORGAN_MANUAL, sig)
    
    att = int(min(0.05 * SR, n * 0.18))
    rel = int(min(0.12 * SR, n * 0.18))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.35

def render_organ_pedal(freq: float, duration_sec: float, velocity: int = 70) -> np.ndarray:
    """Deep 16' Sub-bass Pedal Organ Pipe (reverberant subterranean cathedral foundation)"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    # 16' pipe sounds an octave lower
    sub_freq = freq * 0.5
    phase = 2 * np.pi * sub_freq * t
    
    sig = (
        1.00 * np.sin(phase) +
        0.60 * np.sin(2 * phase) +
        0.25 * np.sin(3 * phase) +
        0.10 * np.sin(4 * phase)
    )
    sig = signal.sosfilt(SOS_ORGAN_PEDAL, sig)
    
    att = int(min(0.08 * SR, n * 0.20))
    rel = int(min(0.20 * SR, n * 0.20))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.42

INSTRUMENT_RENDERERS = {
    'harpsichord': render_harpsichord,
    'gamba': render_gamba,
    'violin': render_baroque_violin,
    'theorbo': render_theorbo,
    'flute': render_flauto_dolce,
    'organ': render_positive_organ,
    'organ_pedal': render_organ_pedal,
}

INSTRUMENT_PANS = {
    'harpsichord': (0.55, 0.45),
    'gamba': (0.44, 0.56),
    'violin': (0.62, 0.38),
    'theorbo': (0.38, 0.62),
    'flute': (0.50, 0.50),
    'organ': (0.52, 0.48),
    'organ_pedal': (0.50, 0.50),
}

MIDI_PROGRAMS = {
    'harpsichord': (6, "Harpsichord"),
    'gamba': (42, "Cello / Viola da Gamba"),
    'violin': (40, "Baroque Violin"),
    'theorbo': (24, "Theorbo / Lute"),
    'flute': (74, "Recorder / Flauto Dolce"),
    'organ': (19, "Church Organ (Manual)"),
    'organ_pedal': (19, "Church Organ (16' Pedal)"),
}

# ---------------------------------------------------------------------------
# VECTORIZED ACOUSTIC REVERBERATION (ADAPTABLE ROOM SPACES)
# ---------------------------------------------------------------------------

def fast_comb(x: np.ndarray, d: int, g: float, max_refl: int = 30) -> np.ndarray:
    y = x.copy()
    curr_g = g
    shift = d
    for _ in range(max_refl):
        if curr_g < 0.002 or shift >= len(x):
            break
        y[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return y

def fast_allpass(x: np.ndarray, d: int, g: float = 0.5, max_refl: int = 20) -> np.ndarray:
    w = np.zeros_like(x)
    curr_g = 1.0
    shift = d
    for _ in range(max_refl):
        if curr_g < 0.002 or shift >= len(x):
            break
        w[shift:] += x[:-shift] * curr_g
        curr_g *= g
        shift += d
    return -g * x + (1.0 - g * g) * w

def apply_baroque_acoustics(stereo: np.ndarray, room_size: float = 0.86, wet: float = 0.28) -> np.ndarray:
    """
    Simulates customizable historic European spaces:
    - Intimate Chamber / Salon: room_size=0.72, wet=0.18
    - Stone Hall / Library: room_size=0.84, wet=0.28
    - Monumental Cathedral: room_size=0.92, wet=0.45
    """
    n = len(stereo)
    comb_delays = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
    allpass_delays = [225, 556, 441, 341]
    
    mono = (stereo[:, 0] + stereo[:, 1]) * 0.5
    comb_out_l = np.zeros(n)
    comb_out_r = np.zeros(n)
    
    for i, d in enumerate(comb_delays):
        g = room_size * (0.80 + 0.02 * (i % 3))
        y = fast_comb(mono, d, g)
        if i % 2 == 0:
            comb_out_l += y
        else:
            comb_out_r += y
            
    rev_l = comb_out_l
    rev_r = comb_out_r
    for d in allpass_delays:
        rev_l = fast_allpass(rev_l, d, g=0.5)
        rev_r = fast_allpass(rev_r, d, g=0.5)
        
    rev_l = signal.sosfilt(SOS_REV_DAMP, rev_l)
    rev_r = signal.sosfilt(SOS_REV_DAMP, rev_r)
    
    rev_stereo = np.column_stack([rev_l, rev_r])
    peak_rev = np.max(np.abs(rev_stereo)) + 1e-6
    peak_dry = np.max(np.abs(stereo)) + 1e-6
    rev_stereo = rev_stereo * (peak_dry / peak_rev)
    
    out = stereo * (1.0 - wet * 0.5) + rev_stereo * wet
    
    out[:, 0] = signal.sosfilt(SOS_HP, out[:, 0])
    out[:, 1] = signal.sosfilt(SOS_HP, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-1.5 / 20.0) # -1.5 dBFS
        out = out * (target / pk)
        
    return out

# ---------------------------------------------------------------------------
# AUDIO SYNTHESIS & MIDI EXPORT
# ---------------------------------------------------------------------------

def render_and_export(notes_by_inst: Dict[str, List[Tuple[float, float, int, int]]],
                      title: str, key_name: str, meter: Tuple[int, int],
                      total_duration_sec: float, output_prefix: str,
                      output_dir: str, bpm: int = 40,
                      room_size: float = 0.85, wet: float = 0.28) -> Tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    midi_path = os.path.join(output_dir, f"{output_prefix}.mid")
    wav_path = os.path.join(output_dir, f"{output_prefix}.wav")
    mp3_path = os.path.join(output_dir, f"{output_prefix}.mp3")
    
    # 1. MIDI Export
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    num, denom = meter
    meta_track = MidiTrack()
    mid.tracks.append(meta_track)
    meta_track.append(MetaMessage('track_name', name=title, time=0))
    meta_track.append(MetaMessage('time_signature', numerator=num, denominator=denom, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))
    meta_track.append(MetaMessage('key_signature', key=key_name, time=0))
    meta_track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    meta_track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT * 32))
    
    ch = 0
    for inst_name, notes in notes_by_inst.items():
        if not notes: continue
        prog_num, track_title = MIDI_PROGRAMS.get(inst_name, (0, inst_name.title()))
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('track_name', name=track_title, time=0))
        track.append(Message('program_change', program=prog_num, channel=ch % 16, time=0))
        track.append(Message('control_change', control=91, value=90, channel=ch % 16, time=0))
        track.append(Message('control_change', control=7, value=100, channel=ch % 16, time=0))
        
        events = []
        for start_s, dur_s, note, vel in notes:
            start_tick = int((start_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            dur_tick = int((dur_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            events.append((start_tick, 10, Message('note_on', note=note, velocity=vel, channel=ch % 16)))
            events.append((start_tick + dur_tick, 5, Message('note_off', note=note, velocity=0, channel=ch % 16)))
            
        events.sort(key=lambda x: (x[0], x[1]))
        last_t = 0
        for tick, _, msg in events:
            delta = max(0, tick - last_t)
            msg.time = delta
            track.append(msg)
            last_t = tick
        track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
        ch += 1
    mid.save(midi_path)
    
    # 2. Audio Synthesis
    total_samples = int((total_duration_sec + 4.5) * SR)
    left = np.zeros(total_samples)
    right = np.zeros(total_samples)
    
    for inst_name, notes in notes_by_inst.items():
        if inst_name not in INSTRUMENT_RENDERERS or not notes:
            continue
        renderer = INSTRUMENT_RENDERERS[inst_name]
        pan_l, pan_r = INSTRUMENT_PANS.get(inst_name, (0.5, 0.5))
        
        inst_buf = np.zeros(total_samples)
        for start_s, dur_s, note, vel in notes:
            s_idx = int(start_s * SR)
            freq = midi_to_freq(note)
            audio = renderer(freq, dur_s, vel)
            end_idx = min(total_samples, s_idx + len(audio))
            if end_idx > s_idx:
                inst_buf[s_idx:end_idx] += audio[:end_idx - s_idx]
                
        left += inst_buf * pan_l
        right += inst_buf * pan_r
        
    stereo = np.column_stack([left, right])
    final_audio = apply_baroque_acoustics(stereo, room_size=room_size, wet=wet)
    sf.write(wav_path, final_audio, SR, subtype='PCM_24')
    
    # 3. MP3 Encoding via FFmpeg
    cmd = [
        FFMPEG_PATH, "-y",
        "-i", wav_path,
        "-codec:a", "libmp3lame",
        "-b:a", "320k",
        "-metadata", f"title={title}",
        "-metadata", "artist=Baroque AI Factory",
        "-metadata", "album=Baroque Forms & Archetypes",
        "-metadata", f"genre=Baroque ({key_name})",
        "-metadata", f"comment=Authentic algorithmic Baroque loop ({len(final_audio)/SR:.1f}s)",
        mp3_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if os.path.exists(wav_path):
        os.remove(wav_path)
        
    return midi_path, mp3_path

# Timing utilities
def bar_time(bar: int, beat: float, meter_beats: int = 4, beat_sec: float = 1.5) -> float:
    return (bar - 1) * meter_beats * beat_sec + (beat - 1.0) * beat_sec

def dur_sec(beats: float, beat_sec: float = 1.5) -> float:
    return beats * beat_sec

def arpeggio_roll(notes: List[int], start_s: float, base_vel: int = 56,
                   step_s: float = 0.038, dur_beats: float = 2.0, beat_sec: float = 1.5) -> List[Tuple[float, float, int, int]]:
    res = []
    dur_s = dur_sec(dur_beats, beat_sec)
    for i, n in enumerate(notes):
        res.append((start_s + i * step_s, dur_s - i * step_s, n, max(38, min(80, base_vel + (i % 2) * 3))))
    return res


# ---------------------------------------------------------------------------
# PROCEDURAL COMPOSITION GENERATORS FOR 9 CONTRASTING ARCHETYPES
# ---------------------------------------------------------------------------

@dataclass
class TrackConfig:
    track_id: int
    title: str
    archetype: str
    key_root: int      # MIDI pitch of tonic (e.g. 50 = D, 45 = A, 48 = C, 43 = G)
    key_name: str      # e.g. "Dm", "Gm", "Cm", "Am", "F", "G", "D"
    is_minor: bool
    bpm: int = 40
    duration_target: float = 45.0
    meter: Tuple[int, int] = (4, 4)
    room_size: float = 0.85
    wet_mix: float = 0.28
    seed: int = 42

def scale_pitches(root: int, is_minor: bool) -> List[int]:
    """Generates 4 octaves of diatonic pitches for the key"""
    intervals = [0, 2, 3, 5, 7, 8, 10] if is_minor else [0, 2, 4, 5, 7, 9, 11]
    res = []
    for oct_shift in [-24, -12, 0, 12, 24, 36]:
        for iv in intervals:
            p = root + oct_shift + iv
            if 24 <= p <= 96:
                res.append(p)
    return sorted(list(set(res)))

# 1. TOCCATA (Stylus Fantasticus - Solo Harpsichord Cascades)
def compose_toccata(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm # 1.5s per beat
    harpsichord = []
    root = cfg.key_root
    scale = scale_pitches(root, cfg.is_minor)
    
    # 7 bars of 4/4 @ 40 BPM = 42s
    # Bar 1: Majestic opening chord + instant 16th-note cascade downwards
    harpsichord += arpeggio_roll([root - 12, root, root + 4 if not cfg.is_minor else root + 3, root + 7, root + 12],
                                 bar_time(1, 1.0, 4, bs), base_vel=74, step_s=0.03, dur_beats=2.0, beat_sec=bs)
    
    # Cascade down (16th notes: duration = bs / 4 = 0.375s)
    step16 = bs / 4.0
    t_curr = bar_time(1, 3.0, 4, bs)
    high_notes = [p for p in scale if root + 12 <= p <= root + 28]
    desc_cascade = sorted(high_notes, reverse=True)[:8]
    for i, p in enumerate(desc_cascade):
        harpsichord.append((t_curr + i * step16, step16 * 1.2, p, rng.randint(62, 75)))
        
    # Bar 2-3: Rapid scalar motoric figures & pedal point
    t_curr = bar_time(2, 1.0, 4, bs)
    pedal_pitch = root - 12
    for b in range(8): # 8 beats = 2 bars
        t_b = t_curr + b * bs
        # Staccato low pedal note on the beat
        harpsichord.append((t_b, 0.45, pedal_pitch, 68))
        # Sweeping 16th-note arpeggiando above
        chord_triad = [root + (0 if cfg.is_minor else 0), root + (3 if cfg.is_minor else 4), root + 7, root + 12]
        if b % 2 == 1:
            chord_triad = [root + 2, root + 5, root + 8 if cfg.is_minor else root + 9, root + 14]
        for s in range(3):
            p = chord_triad[(s + b) % len(chord_triad)] + 12
            harpsichord.append((t_b + (s + 1) * step16, step16 * 1.1, p, rng.randint(58, 70)))
            
    # Bar 4: Dramatic rhetorical pause (fermata) on Diminished 7th chord!
    t_dim = bar_time(4, 1.0, 4, bs)
    dim_chord = [root - 1, root + 2, root + 5, root + 8 if cfg.is_minor else root + 9]
    harpsichord += arpeggio_roll(dim_chord + [p + 12 for p in dim_chord[:2]], t_dim, base_vel=72, step_s=0.045, dur_beats=3.2, beat_sec=bs)
    
    # Bar 5: Dazzling 32nd-note scale flourish upwards!
    t_flourish = bar_time(4, 3.5, 4, bs)
    step32 = bs / 8.0
    asc_notes = [p for p in scale if root - 5 <= p <= root + 22]
    for i, p in enumerate(asc_notes[:14]):
        harpsichord.append((t_flourish + i * step32, step32 * 1.3, p, 58 + i))
        
    # Bar 6: Sequential broken chords (style luthé)
    for bar_num in [5, 6]:
        t_bar = bar_time(bar_num, 1.0, 4, bs)
        for beat_num in range(4):
            t_beat = t_bar + beat_num * bs
            ch_notes = [root - 12 + (beat_num * 2), root + 3 + beat_num, root + 7 + beat_num, root + 12 + beat_num]
            harpsichord += arpeggio_roll(ch_notes, t_beat, base_vel=64, step_s=0.035, dur_beats=1.2, beat_sec=bs)
            
    # Bar 7: Grand Toccata Cadence with Picardy Third
    t_cad = bar_time(7, 1.0, 4, bs)
    # Dominant chord with trill
    harpsichord += arpeggio_roll([root - 5, root - 1, root + 2, root + 7], t_cad, base_vel=70, step_s=0.04, dur_beats=2.0, beat_sec=bs)
    trill_pitch = root - 1
    for tr in range(6):
        harpsichord.append((t_cad + dur_sec(1.0, bs) + tr * 0.15, 0.18, trill_pitch + (tr % 2), 62))
    # Final tonic chord (Major Picardy Third!)
    t_fin = bar_time(7, 3.0, 4, bs)
    major_third = root + 4 # Picardy!
    harpsichord += arpeggio_roll([root - 24, root - 12, root, major_third, root + 7, root + 12, major_third + 12],
                                 t_fin, base_vel=78, step_s=0.04, dur_beats=4.0, beat_sec=bs)
    return {'harpsichord': harpsichord}

# 2. FRENCH OVERTURE (Majestic Double-Dotted Royal Court Grandeur)
def compose_french_overture(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm
    harpsichord = []
    gamba = []
    organ = []
    root = cfg.key_root
    
    # 7 bars of 4/4 @ 40 BPM
    # Characteristic French Overture rhythm: Double-dotted quarter (1.75 beats) + 16th (0.25 beats) + quarter
    for bar_num in range(1, 7):
        t_b1 = bar_time(bar_num, 1.0, 4, bs)
        t_b2_end = bar_time(bar_num, 2.75, 4, bs) # 16th note pickup
        t_b3 = bar_time(bar_num, 3.0, 4, bs)
        t_b4_end = bar_time(bar_num, 4.75, 4, bs) # 16th note pickup
        
        # Harmonic progressions (Grave & Ceremonial)
        harmonies = [
            (root - 12, [root, root + 4 if not cfg.is_minor else root + 3, root + 7]),
            (root - 10, [root + 2, root + 5, root + 9]),
            (root - 14, [root - 2, root + 2, root + 5]),
            (root - 17, [root - 5, root - 1, root + 2, root + 7]),
            (root - 12, [root, root + 4 if not cfg.is_minor else root + 3, root + 7]),
            (root - 17, [root - 5, root - 1, root + 2]),
        ]
        bass_p, chord_ps = harmonies[(bar_num - 1) % len(harmonies)]
        
        # Double-dotted hit on Beat 1 (Gamba & Organ hold, Harpsichord strikes)
        gamba.append((t_b1, dur_sec(1.7, bs), bass_p, 72))
        organ.append((t_b1, dur_sec(1.7, bs), bass_p + 12, 60))
        harpsichord += arpeggio_roll([bass_p] + chord_ps, t_b1, base_vel=74, step_s=0.03, dur_beats=1.7, beat_sec=bs)
        
        # Explosive 16th-note pickup on beat 2.75
        pickup_note = bass_p + (2 if bar_num % 2 == 0 else 4)
        gamba.append((t_b2_end, dur_sec(0.24, bs), pickup_note, 66))
        harpsichord.append((t_b2_end, dur_sec(0.24, bs), pickup_note + 12, 68))
        
        # Second dotted hit on Beat 3
        gamba.append((t_b3, dur_sec(1.7, bs), bass_p, 70))
        harpsichord += arpeggio_roll(chord_ps + [chord_ps[0] + 12], t_b3, base_vel=72, step_s=0.03, dur_beats=1.7, beat_sec=bs)
        
        # 16th pickup on beat 4.75
        gamba.append((t_b4_end, dur_sec(0.24, bs), bass_p + 7, 66))
        harpsichord.append((t_b4_end, dur_sec(0.24, bs), bass_p + 19, 68))
        
    # Bar 7: Grand Cadential Fanfare
    t_cad = bar_time(7, 1.0, 4, bs)
    gamba.append((t_cad, dur_sec(4.0, bs), root - 24, 75))
    organ.append((t_cad, dur_sec(4.0, bs), root - 12, 70))
    maj_third = root + 4 # Royal major
    harpsichord += arpeggio_roll([root - 24, root - 12, root, maj_third, root + 7, root + 12, maj_third + 12],
                                 t_cad, base_vel=80, step_s=0.035, dur_beats=4.0, beat_sec=bs)
    return {'gamba': gamba, 'harpsichord': harpsichord, 'organ': organ}

# 3. LA FOLIA CON VARIAZIONI (Theme & Accelerating Diminutions)
def compose_folia_variations(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm # 1.5s per quarter in 3/4
    gamba = []
    harpsichord = []
    violin = []
    root = cfg.key_root
    scale = scale_pitches(root, True) # Folia is classic minor
    
    # 10 bars in 3/4 @ 40 BPM = 45s
    # Folia Ground Bass: 1: i, 2: V, 3: i, 4: VII, 5: III, 6: VII, 7: i, 8: V, 9: i, 10: I
    folia_bass = [
        root - 12, root - 17, root - 12, root - 14,
        root - 9, root - 14, root - 12, root - 17,
        root - 12, root - 12
    ]
    
    for bar_num, bp in enumerate(folia_bass, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        # Gamba plays solemn steady bass
        gamba.append((t_b, dur_sec(2.8, bs), bp, 62))
        
        # Harpsichord broken chords
        ch = [bp + 12, bp + 15, bp + 19] if bar_num not in [2, 8] else [bp + 12, bp + 16, bp + 19]
        harpsichord += arpeggio_roll(ch, t_b + 0.1, base_vel=52, step_s=0.04, dur_beats=2.5, beat_sec=bs)
        
        # Violin Variations:
        # Bars 1-3: Stately theme
        if bar_num == 1:
            violin.append((t_b, dur_sec(1.8, bs), root + 12, 65))
            violin.append((t_b + dur_sec(2.0, bs), dur_sec(0.9, bs), root + 14, 60))
        elif bar_num == 2:
            violin.append((t_b, dur_sec(2.8, bs), root + 15, 68))
        elif bar_num == 3:
            violin.append((t_b, dur_sec(1.8, bs), root + 14, 64))
            violin.append((t_b + dur_sec(2.0, bs), dur_sec(0.9, bs), root + 12, 60))
        # Bars 4-6: Acceleration to 8th notes (broken arpeggios)
        elif bar_num in [4, 5, 6]:
            step8 = bs / 2.0
            for s in range(6): # 6 eighths in 3/4
                p = ch[s % len(ch)] + (12 if s % 2 == 1 else 0)
                violin.append((t_b + s * step8, step8 * 1.1, p, 60 + (s % 3) * 4))
        # Bars 7-9: Virtuosic 16th-note diminutions (Corelli fireworks!)
        elif bar_num in [7, 8, 9]:
            step16 = bs / 4.0
            run_notes = [p for p in scale if root + 7 <= p <= root + 24]
            for s in range(12): # 12 sixteenths in 3/4
                p = run_notes[(s * 2 + bar_num) % len(run_notes)]
                violin.append((t_b + s * step16, step16 * 1.05, p, rng.randint(62, 74)))
        # Bar 10: Grand Corelli Cadence
        elif bar_num == 10:
            violin.append((t_b, dur_sec(4.0, bs), root + 16, 68)) # Picardy third!
            
    return {'gamba': gamba, 'harpsichord': harpsichord, 'violin': violin}

# 4. ORGAN CHORALE PRELUDE (Cathedral Organ, 4-Part Polyphony & 16' Pedal)
def compose_organ_chorale(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm
    organ = []
    organ_pedal = []
    root = cfg.key_root
    
    # 7 bars of 4/4 @ 40 BPM = 42s
    # Solemn 4-part polyphony with deep subterranean pedal
    pedal_prog = [root - 24, root - 19, root - 21, root - 24, root - 22, root - 24, root - 24]
    
    for bar_num in range(1, 8):
        t_b = bar_time(bar_num, 1.0, 4, bs)
        pedal_n = pedal_prog[(bar_num - 1) % len(pedal_prog)]
        
        # Deep 16' Pedal pipe holding fundamental
        organ_pedal.append((t_b, dur_sec(3.8, bs), pedal_n, 74))
        
        # 3 Manual voices with moving suspensions
        ch_root = root + (0 if cfg.is_minor else 0)
        # Suspended 4-3 resolution on beats 1 -> 2
        sus_note = ch_root + (6 if cfg.is_minor else 5)
        res_note = ch_root + (3 if cfg.is_minor else 4)
        
        # Soprano (Cantus Firmus)
        organ.append((t_b, dur_sec(1.8, bs), root + 12 + (bar_num % 4), 65))
        organ.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 10 + (bar_num % 3), 62))
        
        # Alto (Suspension 4-3)
        organ.append((t_b, dur_sec(1.4, bs), sus_note + 12, 60))
        organ.append((t_b + dur_sec(1.5, bs), dur_sec(2.2, bs), res_note + 12, 58))
        
        # Tenor
        organ.append((t_b, dur_sec(3.8, bs), ch_root + 7, 56))
        
    return {'organ': organ, 'organ_pedal': organ_pedal}

# 5. GIGUE / SALTARELLO (Lively Bouncing 6/8 Dance)
def compose_gigue_dance(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    # In 6/8 @ 40 BPM, dotted quarter = 1.5s, 1 eighth = 0.5s, 1 measure = 3.0s
    bar_sec = 3.0
    eighth_sec = 0.5
    violin = []
    flute = []
    harpsichord = []
    gamba = []
    root = cfg.key_root
    scale = scale_pitches(root, cfg.is_minor)
    
    # 14 bars in 6/8 = 42s
    # Jaunty galloping motif: quaver - quaver - quaver (bouncy staccato!)
    for b in range(14):
        t_b = b * bar_sec
        bass_pitch = root - 12 + (b % 4) * 2
        gamba.append((t_b, 1.2, bass_pitch, 60))
        gamba.append((t_b + 1.5, 1.2, bass_pitch + 7, 56))
        
        # Harpsichord continuo rhythm
        harpsichord += arpeggio_roll([bass_pitch + 12, bass_pitch + 16, bass_pitch + 19], t_b + 0.1, base_vel=50, step_s=0.03, dur_beats=1.5)
        harpsichord += arpeggio_roll([bass_pitch + 12, bass_pitch + 16, bass_pitch + 19], t_b + 1.6, base_vel=48, step_s=0.03, dur_beats=1.5)
        
        # Flute and Violin playful imitative dancing figures (triplets feel)
        for s in range(6):
            t_s = t_b + s * eighth_sec
            p_flute = scale[(s + b * 2) % len(scale)] + 12
            p_viol = scale[(s + b * 2 + 3) % len(scale)]
            if b % 2 == 0:
                flute.append((t_s, eighth_sec * 0.85, p_flute, rng.randint(58, 70))) # Crisp articulation
            else:
                violin.append((t_s, eighth_sec * 0.85, p_viol, rng.randint(60, 72)))
                
    return {'violin': violin, 'flute': flute, 'harpsichord': harpsichord, 'gamba': gamba}

# 6. DIDO'S LAMENT (Chromatic Ground Bass & Agonizing Suspensions)
def compose_dido_lament(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm
    gamba = []
    theorbo = []
    root = cfg.key_root
    
    # 7 bars of 4/4 @ 40 BPM = 42s
    # Pure Passus Duriusculus chromatic ground bass:
    # 1 -> 7 -> b7 -> 6 -> b6 -> 5 -> 1
    chrom_bass = [root - 12, root - 13, root - 14, root - 15, root - 16, root - 17, root - 24]
    
    for bar_num, bp in enumerate(chrom_bass, start=1):
        t_b = bar_time(bar_num, 1.0, 4, bs)
        
        # Deep bowed chromatic bass on Gamba
        gamba.append((t_b, dur_sec(3.8, bs), bp, 65))
        
        # Theorbo delicate broken chords
        ch = [bp + 12, bp + 15, bp + 19, bp + 22] if bar_num < 6 else [bp + 12, bp + 16, bp + 19, bp + 24]
        theorbo += arpeggio_roll(ch, t_b + 0.2, base_vel=52, step_s=0.045, dur_beats=3.2, beat_sec=bs)
        
        # Gamba Upper Melodic Line: Weeping Seufzer Motifs & Minor 9th Suspensions
        if bar_num == 1:
            gamba.append((t_b + dur_sec(1.5, bs), dur_sec(2.2, bs), root + 7, 62))
        elif bar_num == 2:
            # Agonizing suspension (Ab over F#) resolving to G
            gamba.append((t_b, dur_sec(1.8, bs), root + 8, 66))
            gamba.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 7, 58))
        elif bar_num == 3:
            # Suspension resolving down
            gamba.append((t_b, dur_sec(1.8, bs), root + 10, 64))
            gamba.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 9, 58))
        elif bar_num == 4:
            gamba.append((t_b, dur_sec(1.8, bs), root + 8, 62))
            gamba.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 7, 56))
        elif bar_num == 5:
            # Diminished sigh
            gamba.append((t_b, dur_sec(1.8, bs), root + 5, 62))
            gamba.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 4, 56))
        elif bar_num == 6:
            # Leading tone tension
            gamba.append((t_b, dur_sec(1.8, bs), root + 2, 60))
            gamba.append((t_b + dur_sec(2.0, bs), dur_sec(1.8, bs), root + 1, 56))
        elif bar_num == 7:
            # Final quiet resting note
            gamba.append((t_b, dur_sec(4.0, bs), root, 50))
            
    return {'gamba': gamba, 'theorbo': theorbo}

# 7. CHACONNE BUILDUP (3/4 Ostinato with Accelerating Bariolage Arpeggios)
def compose_chaconne_buildup(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm
    harpsichord = []
    root = cfg.key_root
    
    # 10 bars in 3/4 @ 40 BPM = 45s
    # Chaconne ground with distinct beat 2 emphasis, progressively multiplying rhythmic speed
    chords = [
        [root, root + 3, root + 7, root + 12],
        [root - 2, root + 2, root + 5, root + 10],
        [root - 4, root, root + 3, root + 8],
        [root - 5, root - 1, root + 2, root + 7],
        [root, root + 3, root + 7, root + 12],
        [root - 4, root, root + 3, root + 8],
        [root - 5, root - 1, root + 2, root + 7],
        [root, root + 3, root + 7, root + 12],
        [root - 5, root - 1, root + 2, root + 7],
        [root, root + 4, root + 7, root + 12], # Picardy
    ]
    
    for bar_num, ch in enumerate(chords, start=1):
        t_b = (bar_num - 1) * 3.0 * bs
        bass_n = ch[0] - 12
        # Beat 1: Strong bass
        harpsichord.append((t_b, dur_sec(0.9, bs), bass_n, 65))
        
        # Variation 1 (Bars 1-3): Solid dramatic chord roll on Beat 2
        if bar_num <= 3:
            harpsichord += arpeggio_roll(ch, t_b + dur_sec(1.0, bs), base_vel=64, step_s=0.04, dur_beats=1.8, beat_sec=bs)
        # Variation 2 (Bars 4-6): 8th-note undulating broken chords
        elif bar_num <= 6:
            step8 = bs / 2.0
            for s in range(4): # Beats 2 and 3
                t_s = t_b + dur_sec(1.0, bs) + s * step8
                p = ch[s % len(ch)] + (12 if s % 2 == 1 else 0)
                harpsichord.append((t_s, step8 * 1.1, p, 62 + (s % 2) * 4))
        # Variation 3 (Bars 7-9): Rapid 16th-note bariolage cascades!
        elif bar_num <= 9:
            step16 = bs / 4.0
            for s in range(8): # Beats 2 and 3 filled with 16ths
                t_s = t_b + dur_sec(1.0, bs) + s * step16
                p = ch[s % len(ch)] + (12 if s >= 4 else 0)
                harpsichord.append((t_s, step16 * 1.1, p, rng.randint(62, 74)))
        # Final Bar 10: Grand resolution
        else:
            harpsichord += arpeggio_roll(ch + [ch[0] + 24], t_b + dur_sec(1.0, bs), base_vel=75, step_s=0.04, dur_beats=3.5, beat_sec=bs)
            
    return {'harpsichord': harpsichord}

# 8. SICILIANA PASTORALE (Gentle Swaying 6/8 Flute & Lute)
def compose_siciliana_pastorale(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bar_sec = 3.0
    flute = []
    theorbo = []
    gamba = []
    root = cfg.key_root
    
    # 14 bars in 6/8 = 42s
    # Tender dotted rhythm (dotted 8th + 16th + 8th)
    for b in range(14):
        t_b = b * bar_sec
        bp = root - 12 + (b % 3) * 2
        gamba.append((t_b, 1.4, bp, 52))
        theorbo += arpeggio_roll([bp + 12, bp + 16, bp + 19], t_b + 0.15, base_vel=50, step_s=0.04, dur_beats=1.8)
        
        # Flute cantabile in sweet parallel intervals
        # Beat 1: dotted 8th (0.9s) + 16th (0.45s) + 8th (1.4s)
        mel_p = root + 12 + (b % 5)
        flute.append((t_b, 0.85, mel_p, 58))
        flute.append((t_b + 0.88, 0.45, mel_p + 2, 54))
        flute.append((t_b + 1.45, 1.35, mel_p + 4, 62))
        
    return {'flute': flute, 'theorbo': theorbo, 'gamba': gamba}

# 9. CONCERTO GROSSO (Vivaldian Stile Concitato / Motoric Driving Strings)
def compose_concerto_grosso(cfg: TrackConfig) -> Dict[str, List[Tuple[float, float, int, int]]]:
    rng = random.Random(cfg.seed)
    bs = 60.0 / cfg.bpm
    violin = []
    gamba = []
    harpsichord = []
    root = cfg.key_root
    step16 = bs / 4.0 # 0.375s per 16th note
    
    # 7 bars of 4/4 @ 40 BPM = 42s
    # Vivaldi Stile Concitato: driving repeated 16th notes on the same pitch!
    for bar_num in range(1, 8):
        t_bar = bar_time(bar_num, 1.0, 4, bs)
        bp = root - 12 + (bar_num % 3) * 2
        
        # Gamba driving walking bass
        for beat_num in range(4):
            t_beat = t_bar + beat_num * bs
            gamba.append((t_beat, bs * 0.8, bp + (beat_num % 2) * 7, 65))
            harpsichord += arpeggio_roll([bp + 12, bp + 15, bp + 19], t_beat, base_vel=54, step_s=0.03, dur_beats=0.9, beat_sec=bs)
            
        # Violins: rapid repeated 16th-note martellato bowing (Stile Concitato)
        # 16 notes per bar!
        repeat_pitch = root + 12 + (bar_num % 4) * 2
        for s in range(16):
            t_s = t_bar + s * step16
            # Accent on the first of every 4 notes
            vel = 72 if s % 4 == 0 else 58
            p = repeat_pitch if s < 12 else repeat_pitch + (s % 3)
            violin.append((t_s, step16 * 0.9, p, vel))
            
    return {'violin': violin, 'gamba': gamba, 'harpsichord': harpsichord}

# ---------------------------------------------------------------------------
# ARCHETYPE DISPATCH TABLE & HIGH-LEVEL TRACK GENERATOR
# ---------------------------------------------------------------------------

ARCHETYPE_GENERATORS = {
    'TOCCATA': (compose_toccata, (4, 4), 0.72, 0.16),           # Solo Harpsichord, dry, brilliant
    'FRENCH_OVERTURE': (compose_french_overture, (4, 4), 0.86, 0.30), # Royal Court, pompous
    'FOLIA_VARIATIONS': (compose_folia_variations, (3, 4), 0.82, 0.25), # Virtuosic violin diminutions
    'ORGAN_CHORALE': (compose_organ_chorale, (4, 4), 0.92, 0.45), # Massive cathedral organ
    'GIGUE_DANCE': (compose_gigue_dance, (6, 8), 0.80, 0.24),      # Bouncing triple dance
    'DIDO_LAMENT': (compose_dido_lament, (4, 4), 0.84, 0.28),      # Deep chromatic ground of tears
    'CHACONNE_BUILDUP': (compose_chaconne_buildup, (3, 4), 0.85, 0.26), # Accelerating bariolage
    'SICILIANA_PASTORALE': (compose_siciliana_pastorale, (6, 8), 0.82, 0.25), # Gentle swaying pastoral
    'CONCERTO_GROSSO': (compose_concerto_grosso, (4, 4), 0.85, 0.28), # Vivaldian motoric strings
}

KEYS_CATALOG = [
    (50, "Dm", True), (45, "Am", True), (48, "Cm", True), (43, "Gm", True), (40, "Em", True),
    (53, "F", False), (55, "G", False), (50, "D", False), (48, "C", False), (46, "Bb", False)
]

def generate_baroque_track(track_id: int, archetype_name: str, key_tuple: Tuple[int, str, bool],
                           output_dir: str, seed: Optional[int] = None, bpm: int = 40) -> Tuple[str, str]:
    if archetype_name not in ARCHETYPE_GENERATORS:
        raise ValueError(f"Unknown archetype: {archetype_name}")
        
    comp_fn, meter, room_size, wet = ARCHETYPE_GENERATORS[archetype_name]
    root_midi, key_name, is_minor = key_tuple
    used_seed = seed if seed is not None else (track_id * 1000 + root_midi)
    
    clean_style = archetype_name.replace('_', ' ').title()
    title = f"{clean_style} in {key_name} (Op. {track_id:03d})"
    
    cfg = TrackConfig(
        track_id=track_id,
        title=title,
        archetype=archetype_name,
        key_root=root_midi,
        key_name=key_name,
        is_minor=is_minor,
        bpm=bpm,
        duration_target=45.0,
        meter=meter,
        room_size=room_size,
        wet_mix=wet,
        seed=used_seed
    )
    
    notes_by_inst = comp_fn(cfg)
    prefix = f"baroque_{track_id:03d}_{archetype_name.lower()}_{key_name.lower()}"
    
    midi_p, mp3_p = render_and_export(
        notes_by_inst=notes_by_inst,
        title=title,
        key_name=key_name,
        meter=meter,
        total_duration_sec=cfg.duration_target,
        output_prefix=prefix,
        output_dir=output_dir,
        bpm=bpm,
        room_size=room_size,
        wet=wet
    )
    return midi_p, mp3_p
