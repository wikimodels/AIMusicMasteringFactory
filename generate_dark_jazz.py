"""
Dark Jazz Collection Generator (Clean, Acoustic & Lyrical)
Instruments:
  - Clarinet (Lead / Noir Melodic Solo in Chalumeau & Clarion registers)
  - Cello (Warm acoustic bowed bass & counterpoint, D2-A3, no sub-rumble)
  - Electric Jazz Guitar (Hollowbody archtop chords: m9, m11, 6/9, maj7#11, 7alt)
Tempo: 40 BPM
Duration: ~1 minute each + natural reverb decay (~64.5s)
Outputs: MIDI (.mid) and High-Quality MP3 (320 kbps)
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

SR = 44100
BPM = 40
TICKS_PER_BEAT = 480
TICKS_PER_BAR = TICKS_PER_BEAT * 4
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "dark_jazz_collection")
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# PURE ACOUSTIC SYNTHESIS (NO CRACKLE, NO RANDOM NOISE)
# ---------------------------------------------------------------------------

def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))

def render_clarinet(freq, duration_sec, velocity=65):
    """Warm wooden clarinet tone with gradual vibrato (no noise)"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    vib_onset = np.clip((t - duration_sec * 0.35) / (duration_sec * 0.35 + 1e-5), 0, 1)
    vib = np.sin(2 * np.pi * 4.6 * t) * (0.0055 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    # Pure odd harmonics
    sig = (
        1.00 * np.sin(phase) +
        0.35 * np.sin(3 * phase) +
        0.10 * np.sin(5 * phase) +
        0.02 * np.sin(7 * phase)
    )
    
    sos = signal.butter(4, 1800, btype='low', fs=SR, output='sos')
    sig = signal.sosfilt(sos, sig)
    
    att = int(0.12 * SR)
    rel = int(0.18 * SR)
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.32

def render_cello(freq, duration_sec, velocity=65):
    """Deep, warm bowed cello in natural acoustic register (D2-A3, no noise)"""
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    vib_onset = np.clip((t - duration_sec * 0.3) / (duration_sec * 0.3 + 1e-5), 0, 1)
    vib = np.sin(2 * np.pi * 4.2 * t) * (0.0045 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    harmonics = [1.0, 0.60, 0.35, 0.18, 0.08, 0.03]
    sig = np.zeros(n)
    for i, h_amp in enumerate(harmonics, start=1):
        if freq * i < SR * 0.45:
            sig += h_amp * np.sin(i * phase)
            
    sos = signal.butter(3, 1100, btype='low', fs=SR, output='sos')
    sig = signal.sosfilt(sos, sig)
    
    att = int(0.20 * SR)
    rel = int(0.28 * SR)
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.35

def render_guitar(freq, duration_sec, velocity=60):
    """Mellow hollowbody jazz guitar with warm neck pickup (no noise)"""
    ring_sec = max(duration_sec, 2.5)
    n = int(ring_sec * SR)
    t = np.linspace(0, ring_sec, n, endpoint=False)
    
    sig = np.zeros(n)
    harmonics = [(1, 1.0, 0.85), (2, 0.45, 1.4), (3, 0.18, 2.1), (4, 0.06, 3.0)]
    for h, amp, decay_rate in harmonics:
        f_h = freq * h
        if f_h < SR * 0.45:
            sig += amp * np.sin(2 * np.pi * f_h * t) * np.exp(-decay_rate * t)
            
    att_samples = int(0.006 * SR)
    sig[:att_samples] *= np.sin(np.linspace(0, np.pi / 2, att_samples))
    
    sos = signal.butter(3, 1300, btype='low', fs=SR, output='sos')
    sig = signal.sosfilt(sos, sig)
    
    return sig * (velocity / 127.0) * 0.30

def clean_schroeder_reverb(stereo, sr=SR, room_size=0.82, wet=0.28):
    """Clean Schroeder algorithmic reverb without any random noise"""
    n = len(stereo)
    comb_delays = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
    allpass_delays = [225, 556, 441, 341]
    
    mono = (stereo[:, 0] + stereo[:, 1]) * 0.5
    comb_out_l = np.zeros(n)
    comb_out_r = np.zeros(n)
    
    for i, d in enumerate(comb_delays):
        g = room_size * (0.83 + 0.02 * (i % 3))
        a = np.zeros(d + 1)
        a[0] = 1.0
        a[d] = -g
        y = signal.lfilter([1.0], a, mono)
        if i % 2 == 0:
            comb_out_l += y
        else:
            comb_out_r += y
            
    rev_l = comb_out_l
    rev_r = comb_out_r
    for d in allpass_delays:
        g_ap = 0.5
        b_ap = np.zeros(d + 1)
        b_ap[0] = -g_ap
        b_ap[d] = 1.0
        a_ap = np.zeros(d + 1)
        a_ap[0] = 1.0
        a_ap[d] = -g_ap
        rev_l = signal.lfilter(b_ap, a_ap, rev_l)
        rev_r = signal.lfilter(b_ap, a_ap, rev_r)
        
    sos_rev = signal.butter(2, 1800, btype='low', fs=sr, output='sos')
    rev_l = signal.sosfilt(sos_rev, rev_l)
    rev_r = signal.sosfilt(sos_rev, rev_r)
    
    rev_stereo = np.column_stack([rev_l, rev_r])
    peak_rev = np.max(np.abs(rev_stereo)) + 1e-6
    peak_dry = np.max(np.abs(stereo)) + 1e-6
    rev_stereo = rev_stereo * (peak_dry / peak_rev)
    
    out = stereo * (1.0 - wet * 0.5) + rev_stereo * wet
    
    sos_hp = signal.butter(2, 45, btype='high', fs=sr, output='sos')
    out[:, 0] = signal.sosfilt(sos_hp, out[:, 0])
    out[:, 1] = signal.sosfilt(sos_hp, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-2.0 / 20.0) # -2.0 dBFS
        out = out * (target / pk)
        
    return out

def synthesize_audio(notes_by_inst, total_duration_sec=60.0):
    total_samples = int((total_duration_sec + 4.5) * SR)
    cello_buf = np.zeros(total_samples)
    guitar_buf = np.zeros(total_samples)
    clarinet_buf = np.zeros(total_samples)
    
    for start_s, dur_s, note, vel in notes_by_inst['cello']:
        s_idx = int(start_s * SR)
        freq = midi_to_freq(note)
        audio = render_cello(freq, dur_s, vel)
        end_idx = min(total_samples, s_idx + len(audio))
        cello_buf[s_idx:end_idx] += audio[:end_idx - s_idx]
        
    for start_s, dur_s, note, vel in notes_by_inst['guitar']:
        s_idx = int(start_s * SR)
        freq = midi_to_freq(note)
        audio = render_guitar(freq, dur_s, vel)
        end_idx = min(total_samples, s_idx + len(audio))
        guitar_buf[s_idx:end_idx] += audio[:end_idx - s_idx]
        
    for start_s, dur_s, note, vel in notes_by_inst['clarinet']:
        s_idx = int(start_s * SR)
        freq = midi_to_freq(note)
        audio = render_clarinet(freq, dur_s, vel)
        end_idx = min(total_samples, s_idx + len(audio))
        clarinet_buf[s_idx:end_idx] += audio[:end_idx - s_idx]
        
    left = cello_buf * 0.58 + guitar_buf * 0.40 + clarinet_buf * 0.50
    right = cello_buf * 0.42 + guitar_buf * 0.60 + clarinet_buf * 0.50
    stereo = np.column_stack([left, right])
    
    return clean_schroeder_reverb(stereo, sr=SR, room_size=0.82, wet=0.26)

# ---------------------------------------------------------------------------
# MIDI EXPORTER
# ---------------------------------------------------------------------------

def export_midi(notes_by_inst, title, key_name, output_path, bpm=BPM):
    mid = MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    
    meta_track = MidiTrack()
    mid.tracks.append(meta_track)
    meta_track.append(MetaMessage('track_name', name=title, time=0))
    meta_track.append(MetaMessage('time_signature', numerator=4, denominator=4, clocks_per_click=24, notated_32nd_notes_per_beat=8, time=0))
    meta_track.append(MetaMessage('key_signature', key=key_name, time=0))
    meta_track.append(MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm), time=0))
    meta_track.append(MetaMessage('end_of_track', time=TICKS_PER_BAR * 11))
    
    track_configs = [
        ('cello', 'Cello', 0, 42),
        ('guitar', 'Electric Jazz Guitar', 1, 26),
        ('clarinet', 'Clarinet', 2, 71),
    ]
    
    for inst_key, track_name, channel, program in track_configs:
        track = MidiTrack()
        mid.tracks.append(track)
        track.append(MetaMessage('track_name', name=track_name, time=0))
        track.append(Message('program_change', program=program, channel=channel, time=0))
        track.append(Message('control_change', control=91, value=95, channel=channel, time=0))
        track.append(Message('control_change', control=7, value=100, channel=channel, time=0))
        track.append(Message('control_change', control=11, value=90, channel=channel, time=0))
        
        events = []
        for start_s, dur_s, note, vel in notes_by_inst[inst_key]:
            start_tick = int((start_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            dur_tick = int((dur_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            events.append((start_tick, 10, Message('note_on', note=note, velocity=vel, channel=channel)))
            events.append((start_tick + dur_tick, 5, Message('note_off', note=note, velocity=0, channel=channel)))
            
        events.sort(key=lambda x: (x[0], x[1]))
        last_t = 0
        for tick, _, msg in events:
            delta = max(0, tick - last_t)
            msg.time = delta
            track.append(msg)
            last_t = tick
            
        track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
        
    mid.save(output_path)

# ---------------------------------------------------------------------------
# 10 COMPOSITIONS
# ---------------------------------------------------------------------------

def t(b, beat):
    return (b - 1) * 6.0 + (beat - 1.0) * 1.5

def sec(beats):
    return beats * 1.5

def strum(notes, start_s, base_vel=52, delay_s=0.038, dur_beats=2.8):
    res = []
    dur_s = sec(dur_beats)
    for i, n in enumerate(notes):
        n_start = start_s + i * delay_s
        n_vel = max(38, min(80, base_vel + i * 2 + random.randint(-1, 1)))
        res.append((n_start, dur_s - i * delay_s, n, n_vel))
    return res

def compose_01():
    cello = [
        (t(1, 1.0), sec(3.8), 38, 54), (t(2, 1.0), sec(2.0), 38, 52), (t(2, 3.2), sec(1.6), 41, 50),
        (t(3, 1.0), sec(3.8), 43, 56), (t(4, 1.0), sec(2.0), 40, 52), (t(4, 3.0), sec(1.8), 39, 53),
        (t(5, 1.0), sec(3.8), 45, 55), (t(6, 1.0), sec(3.8), 46, 56), (t(7, 1.0), sec(3.8), 43, 54),
        (t(8, 1.0), sec(2.0), 40, 52), (t(8, 3.0), sec(1.8), 45, 54), (t(9, 1.0), sec(3.8), 38, 52),
        (t(10, 1.0), sec(5.0), 38, 48),
    ]
    guitar = []
    guitar += strum([50, 57, 60, 64, 65], t(1, 2.1), 50) # Dm9
    guitar += strum([50, 59, 65, 69], t(2, 2.2), 48)     # Dm6
    guitar += strum([55, 62, 65, 69, 70], t(3, 2.1), 52) # Gm9
    guitar += strum([52, 58, 62, 67], t(4, 1.2), 48)     # Em7b5
    guitar += strum([51, 57, 61, 67], t(4, 3.2), 50)     # Eb7#11
    guitar += strum([57, 61, 65, 70], t(5, 2.1), 52)     # A7b9b13
    guitar += strum([58, 62, 65, 69], t(6, 1.5), 52)     # Bbmaj7#11
    guitar += strum([55, 60, 65, 67], t(7, 2.1), 50)     # Gm11
    guitar += strum([57, 61, 65, 69], t(8, 2.2), 50)     # A7alt
    guitar += strum([50, 57, 62, 64], t(9, 2.0), 48)     # Dm(add9)
    guitar += strum([50, 53, 59, 64, 69], t(10, 1.3), 46, delay_s=0.05, dur_beats=5.0) # Dm6/9
    clarinet = [
        (t(2, 2.8), sec(1.2), 57, 48), (t(2, 4.0), sec(2.0), 62, 55),
        (t(3, 2.2), sec(0.8), 65, 54), (t(3, 3.2), sec(2.0), 67, 58),
        (t(4, 2.2), sec(1.0), 68, 60), (t(4, 3.4), sec(1.8), 67, 56),
        (t(5, 2.0), sec(0.8), 65, 54), (t(5, 3.0), sec(2.0), 64, 58),
        (t(6, 2.0), sec(2.2), 64, 62), (t(6, 4.4), sec(1.2), 62, 54),
        (t(7, 2.0), sec(1.0), 65, 56), (t(7, 3.2), sec(1.8), 67, 60),
        (t(8, 2.0), sec(1.4), 69, 64), (t(8, 3.6), sec(1.2), 65, 56), (t(8, 4.8), sec(1.0), 61, 50),
        (t(9, 2.0), sec(2.0), 62, 54), (t(10, 1.8), sec(4.5), 64, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 01 - Harlem Midnight", "Dm"

def compose_02():
    cello = [
        (t(1, 1.0), sec(3.8), 36, 54), (t(2, 1.0), sec(2.0), 36, 52), (t(2, 3.0), sec(1.8), 47, 50),
        (t(3, 1.0), sec(2.0), 46, 50), (t(3, 3.0), sec(1.8), 45, 48), (t(4, 1.0), sec(3.8), 41, 56),
        (t(5, 1.0), sec(3.8), 44, 55), (t(6, 1.0), sec(2.0), 38, 52), (t(6, 3.0), sec(1.8), 43, 54),
        (t(7, 1.0), sec(3.8), 36, 52), (t(8, 1.0), sec(3.8), 44, 54), (t(9, 1.0), sec(2.0), 38, 50),
        (t(9, 3.0), sec(1.8), 43, 52), (t(10, 1.0), sec(5.0), 36, 46),
    ]
    guitar = []
    guitar += strum([48, 55, 58, 62, 63], t(1, 2.1), 50)
    guitar += strum([48, 55, 59, 63], t(2, 1.5), 48)
    guitar += strum([48, 55, 58, 63], t(2, 3.5), 48)
    guitar += strum([53, 56, 60, 63, 65], t(4, 2.0), 52)
    guitar += strum([56, 60, 63, 67], t(5, 1.8), 52)
    guitar += strum([50, 56, 60, 65], t(6, 1.3), 48)
    guitar += strum([55, 59, 63, 67], t(6, 3.2), 50)
    guitar += strum([48, 55, 60, 62], t(7, 2.0), 50)
    guitar += strum([56, 60, 63, 67], t(8, 2.1), 50)
    guitar += strum([55, 59, 62, 65], t(9, 2.2), 50)
    guitar += strum([48, 51, 57, 62, 67], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.8), 55, 48), (t(2, 3.2), sec(1.8), 60, 54),
        (t(3, 2.0), sec(1.0), 63, 56), (t(3, 3.2), sec(1.8), 62, 54),
        (t(4, 2.2), sec(0.8), 56, 50), (t(4, 3.2), sec(1.0), 60, 54), (t(4, 4.3), sec(1.8), 63, 58),
        (t(5, 2.2), sec(2.0), 62, 56), (t(6, 2.0), sec(1.0), 65, 60), (t(6, 3.2), sec(1.6), 59, 52),
        (t(7, 2.0), sec(2.0), 60, 55), (t(8, 2.0), sec(1.2), 63, 56), (t(8, 3.5), sec(1.5), 65, 60),
        (t(9, 2.0), sec(1.4), 67, 64), (t(9, 3.6), sec(1.2), 63, 54), (t(9, 4.8), sec(1.0), 59, 48),
        (t(10, 1.8), sec(4.5), 62, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 02 - Rain on Cobblestones", "Cm"

def compose_03():
    cello = [
        (t(1, 1.0), sec(3.8), 43, 54), (t(2, 1.0), sec(3.8), 43, 52), (t(3, 1.0), sec(3.8), 39, 56),
        (t(4, 1.0), sec(3.8), 48, 54), (t(5, 1.0), sec(2.0), 45, 50), (t(5, 3.0), sec(1.8), 38, 54),
        (t(6, 1.0), sec(3.8), 46, 55), (t(7, 1.0), sec(3.8), 39, 54), (t(8, 1.0), sec(2.0), 45, 50),
        (t(8, 3.0), sec(1.8), 38, 54), (t(9, 1.0), sec(3.8), 43, 52), (t(10, 1.0), sec(5.0), 43, 46),
    ]
    guitar = []
    guitar += strum([55, 62, 65, 69, 70], t(1, 2.1), 52)
    guitar += strum([55, 60, 65, 67], t(2, 2.0), 50)
    guitar += strum([51, 55, 58, 62, 65], t(3, 1.8), 52)
    guitar += strum([48, 55, 58, 62, 63], t(4, 2.0), 50)
    guitar += strum([45, 51, 55, 60], t(5, 1.3), 48)
    guitar += strum([50, 54, 58, 61, 64], t(5, 3.2), 52)
    guitar += strum([46, 53, 57, 62, 65], t(6, 2.0), 50)
    guitar += strum([51, 55, 58, 62], t(7, 2.1), 50)
    guitar += strum([50, 54, 58, 61], t(8, 2.2), 50)
    guitar += strum([55, 58, 62, 64], t(9, 2.0), 48)
    guitar += strum([55, 58, 64, 69], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.5), sec(0.9), 58, 50), (t(2, 3.6), sec(1.8), 62, 54),
        (t(3, 2.2), sec(2.0), 65, 58), (t(4, 2.0), sec(1.0), 63, 54), (t(4, 3.2), sec(1.5), 60, 50),
        (t(5, 2.0), sec(1.0), 61, 54), (t(5, 3.2), sec(1.8), 62, 58),
        (t(6, 2.0), sec(1.8), 65, 58), (t(7, 2.0), sec(1.2), 67, 62), (t(7, 3.5), sec(1.5), 69, 65),
        (t(8, 2.0), sec(1.2), 67, 58), (t(8, 3.4), sec(1.4), 62, 52), (t(8, 4.8), sec(1.0), 58, 48),
        (t(9, 2.0), sec(2.0), 55, 50), (t(10, 1.8), sec(4.5), 69, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 03 - Whispering Alley", "Gm"

def compose_04():
    cello = [
        (t(1, 1.0), sec(3.8), 45, 54), (t(2, 1.0), sec(3.8), 45, 52), (t(3, 1.0), sec(3.8), 41, 56),
        (t(4, 1.0), sec(3.8), 38, 54), (t(5, 1.0), sec(2.0), 47, 50), (t(5, 3.0), sec(1.8), 46, 52),
        (t(6, 1.0), sec(3.8), 40, 55), (t(7, 1.0), sec(3.8), 45, 52), (t(8, 1.0), sec(3.8), 41, 54),
        (t(9, 1.0), sec(2.0), 47, 50), (t(9, 3.0), sec(1.8), 40, 52), (t(10, 1.0), sec(5.0), 45, 46),
    ]
    guitar = []
    guitar += strum([57, 60, 64, 67, 71], t(1, 2.1), 50)
    guitar += strum([53, 57, 60, 64, 66], t(3, 1.8), 52)
    guitar += strum([50, 57, 60, 64, 65], t(4, 2.0), 50)
    guitar += strum([47, 53, 57, 62], t(5, 1.3), 48)
    guitar += strum([46, 52, 56, 62], t(5, 3.2), 50)
    guitar += strum([52, 56, 60, 63, 65], t(6, 2.1), 52)
    guitar += strum([57, 60, 64, 66], t(7, 2.0), 48)
    guitar += strum([53, 57, 60, 64], t(8, 2.1), 50)
    guitar += strum([52, 56, 59, 63], t(9, 2.2), 50)
    guitar += strum([57, 60, 66, 71], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.5), sec(1.0), 60, 50), (t(2, 3.8), sec(1.8), 64, 55),
        (t(3, 2.2), sec(2.0), 66, 60), (t(4, 2.0), sec(1.2), 65, 54), (t(4, 3.4), sec(1.6), 62, 50),
        (t(5, 2.0), sec(1.0), 60, 52), (t(5, 3.2), sec(1.8), 58, 54),
        (t(6, 2.0), sec(1.8), 59, 56), (t(7, 2.0), sec(1.2), 64, 56), (t(7, 3.5), sec(1.5), 67, 62),
        (t(8, 2.0), sec(1.4), 69, 65), (t(8, 3.6), sec(1.4), 66, 56),
        (t(9, 2.0), sec(1.2), 64, 52), (t(9, 3.5), sec(1.2), 60, 48), (t(10, 1.8), sec(4.5), 59, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 04 - Black Velvet", "Am"

def compose_05():
    cello = [
        (t(1, 1.0), sec(3.8), 40, 54), (t(2, 1.0), sec(3.8), 40, 52), (t(3, 1.0), sec(3.8), 48, 55),
        (t(4, 1.0), sec(3.8), 45, 54), (t(5, 1.0), sec(2.0), 42, 50), (t(5, 3.0), sec(1.8), 47, 54),
        (t(6, 1.0), sec(3.8), 43, 52), (t(7, 1.0), sec(3.8), 48, 54), (t(8, 1.0), sec(2.0), 42, 50),
        (t(8, 3.0), sec(1.8), 47, 52), (t(9, 1.0), sec(3.8), 40, 50), (t(10, 1.0), sec(5.0), 40, 46),
    ]
    guitar = []
    guitar += strum([52, 59, 62, 66, 67], t(1, 2.1), 50)
    guitar += strum([52, 57, 62, 64], t(2, 2.0), 48)
    guitar += strum([48, 55, 59, 62, 66], t(3, 1.8), 52)
    guitar += strum([45, 52, 55, 59, 60], t(4, 2.0), 50)
    guitar += strum([42, 48, 52, 57], t(5, 1.3), 48)
    guitar += strum([47, 53, 57, 60, 63], t(5, 3.2), 52)
    guitar += strum([43, 50, 54, 59, 62], t(6, 2.0), 50)
    guitar += strum([48, 52, 55, 59], t(7, 2.1), 50)
    guitar += strum([47, 53, 56, 59], t(8, 2.2), 50)
    guitar += strum([52, 55, 59, 61], t(9, 2.0), 48)
    guitar += strum([52, 55, 61, 66], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 55, 48), (t(2, 3.3), sec(1.8), 59, 54),
        (t(3, 2.0), sec(2.0), 62, 58), (t(4, 2.0), sec(1.2), 60, 52), (t(4, 3.4), sec(1.5), 57, 48),
        (t(5, 2.0), sec(1.0), 58, 52), (t(5, 3.2), sec(1.8), 59, 56),
        (t(6, 2.0), sec(1.8), 62, 58), (t(7, 2.0), sec(1.2), 64, 60), (t(7, 3.5), sec(1.5), 66, 64),
        (t(8, 2.0), sec(1.2), 64, 56), (t(8, 3.4), sec(1.4), 59, 52), (t(8, 4.8), sec(1.0), 55, 48),
        (t(9, 2.0), sec(2.0), 52, 50), (t(10, 1.8), sec(4.5), 54, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 05 - Neon Shadows", "Em"

def compose_06():
    cello = [
        (t(1, 1.0), sec(3.8), 47, 54), (t(2, 1.0), sec(3.8), 47, 52), (t(3, 1.0), sec(3.8), 40, 55),
        (t(4, 1.0), sec(3.8), 43, 54), (t(5, 1.0), sec(2.0), 49, 50), (t(5, 3.0), sec(1.8), 42, 54),
        (t(6, 1.0), sec(3.8), 47, 52), (t(7, 1.0), sec(3.8), 43, 54), (t(8, 1.0), sec(2.0), 49, 50),
        (t(8, 3.0), sec(1.8), 42, 52), (t(9, 1.0), sec(3.8), 47, 50), (t(10, 1.0), sec(5.0), 47, 46),
    ]
    guitar = []
    guitar += strum([59, 62, 66, 69, 73], t(1, 2.1), 50)
    guitar += strum([59, 62, 68, 71], t(2, 2.0), 48)
    guitar += strum([52, 59, 62, 66, 67], t(3, 1.8), 52)
    guitar += strum([55, 59, 62, 66, 68], t(4, 2.0), 52)
    guitar += strum([49, 55, 59, 64], t(5, 1.3), 48)
    guitar += strum([54, 58, 62, 65, 68], t(5, 3.2), 52)
    guitar += strum([59, 62, 66, 68], t(6, 2.0), 50)
    guitar += strum([55, 59, 62, 66], t(7, 2.1), 50)
    guitar += strum([54, 58, 61, 64], t(8, 2.2), 50)
    guitar += strum([59, 62, 66, 69], t(9, 2.0), 48)
    guitar += strum([59, 62, 68, 73], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 54, 48), (t(2, 3.3), sec(1.8), 59, 54),
        (t(3, 2.0), sec(2.0), 62, 58), (t(4, 2.0), sec(1.2), 66, 60), (t(4, 3.4), sec(1.5), 62, 52),
        (t(5, 2.0), sec(1.0), 61, 50), (t(5, 3.2), sec(1.8), 58, 54),
        (t(6, 2.0), sec(1.8), 59, 56), (t(7, 2.0), sec(1.2), 62, 58), (t(7, 3.5), sec(1.5), 66, 62),
        (t(8, 2.0), sec(1.4), 69, 65), (t(8, 3.6), sec(1.4), 66, 56),
        (t(9, 2.0), sec(1.2), 61, 52), (t(9, 3.5), sec(1.2), 59, 48), (t(10, 1.8), sec(4.5), 61, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 06 - The Long Goodbye", "Bm"

def compose_07():
    cello = [
        (t(1, 1.0), sec(3.8), 41, 54), (t(2, 1.0), sec(3.8), 41, 52), (t(3, 1.0), sec(3.8), 49, 55),
        (t(4, 1.0), sec(3.8), 46, 54), (t(5, 1.0), sec(2.0), 43, 50), (t(5, 3.0), sec(1.8), 48, 54),
        (t(6, 1.0), sec(3.8), 41, 52), (t(7, 1.0), sec(3.8), 49, 54), (t(8, 1.0), sec(2.0), 43, 50),
        (t(8, 3.0), sec(1.8), 48, 52), (t(9, 1.0), sec(3.8), 41, 50), (t(10, 1.0), sec(5.0), 41, 46),
    ]
    guitar = []
    guitar += strum([53, 60, 63, 67, 68], t(1, 2.1), 50)
    guitar += strum([53, 58, 63, 65], t(2, 2.0), 48)
    guitar += strum([49, 56, 60, 63, 67], t(3, 1.8), 52)
    guitar += strum([46, 53, 56, 60, 61], t(4, 2.0), 50)
    guitar += strum([43, 49, 53, 58], t(5, 1.3), 48)
    guitar += strum([48, 52, 56, 59, 62], t(5, 3.2), 52)
    guitar += strum([53, 56, 60, 62], t(6, 2.0), 50)
    guitar += strum([49, 53, 56, 60], t(7, 2.1), 50)
    guitar += strum([48, 52, 55, 58], t(8, 2.2), 50)
    guitar += strum([53, 56, 60, 63], t(9, 2.0), 48)
    guitar += strum([53, 56, 62, 67], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 56, 48), (t(2, 3.3), sec(1.8), 60, 54),
        (t(3, 2.0), sec(2.0), 63, 58), (t(4, 2.0), sec(1.2), 61, 52), (t(4, 3.4), sec(1.5), 58, 48),
        (t(5, 2.0), sec(1.0), 59, 52), (t(5, 3.2), sec(1.8), 60, 56),
        (t(6, 2.0), sec(1.8), 63, 58), (t(7, 2.0), sec(1.2), 65, 60), (t(7, 3.5), sec(1.5), 68, 64),
        (t(8, 2.0), sec(1.2), 65, 56), (t(8, 3.4), sec(1.4), 60, 52), (t(8, 4.8), sec(1.0), 56, 48),
        (t(9, 2.0), sec(2.0), 53, 50), (t(10, 1.8), sec(4.5), 55, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 07 - Smoke Rings", "Fm"

def compose_08():
    cello = [
        (t(1, 1.0), sec(3.8), 37, 54), (t(2, 1.0), sec(3.8), 37, 52), (t(3, 1.0), sec(3.8), 45, 55),
        (t(4, 1.0), sec(3.8), 42, 54), (t(5, 1.0), sec(2.0), 39, 50), (t(5, 3.0), sec(1.8), 44, 54),
        (t(6, 1.0), sec(3.8), 37, 52), (t(7, 1.0), sec(3.8), 45, 54), (t(8, 1.0), sec(2.0), 39, 50),
        (t(8, 3.0), sec(1.8), 44, 52), (t(9, 1.0), sec(3.8), 37, 50), (t(10, 1.0), sec(5.0), 37, 46),
    ]
    guitar = []
    guitar += strum([49, 56, 59, 63, 64], t(1, 2.1), 50)
    guitar += strum([45, 52, 56, 59, 63], t(3, 1.8), 52)
    guitar += strum([54, 57, 61, 64, 66], t(4, 2.0), 50)
    guitar += strum([51, 57, 61, 66], t(5, 1.3), 48)
    guitar += strum([44, 50, 54, 58, 61], t(5, 3.2), 52)
    guitar += strum([49, 56, 61, 63], t(6, 2.0), 50)
    guitar += strum([45, 52, 56, 61], t(7, 2.1), 50)
    guitar += strum([44, 50, 54, 57], t(8, 2.2), 50)
    guitar += strum([49, 56, 61, 63], t(9, 2.0), 48)
    guitar += strum([49, 52, 58, 63], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 56, 48), (t(2, 3.3), sec(1.8), 61, 54),
        (t(3, 2.0), sec(2.0), 64, 58), (t(4, 2.0), sec(1.2), 62, 52), (t(4, 3.4), sec(1.5), 59, 48),
        (t(5, 2.0), sec(1.0), 60, 52), (t(5, 3.2), sec(1.8), 61, 56),
        (t(6, 2.0), sec(1.8), 64, 58), (t(7, 2.0), sec(1.2), 66, 60), (t(7, 3.5), sec(1.5), 69, 64),
        (t(8, 2.0), sec(1.2), 66, 56), (t(8, 3.4), sec(1.4), 61, 52), (t(8, 4.8), sec(1.0), 57, 48),
        (t(9, 2.0), sec(2.0), 54, 50), (t(10, 1.8), sec(4.5), 63, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 08 - Boulevard at 3 AM", "C#m"

def compose_09():
    cello = [
        (t(1, 1.0), sec(3.8), 46, 54), (t(2, 1.0), sec(3.8), 46, 52), (t(3, 1.0), sec(3.8), 39, 55),
        (t(4, 1.0), sec(3.8), 42, 54), (t(5, 1.0), sec(2.0), 48, 50), (t(5, 3.0), sec(1.8), 41, 54),
        (t(6, 1.0), sec(3.8), 46, 52), (t(7, 1.0), sec(3.8), 42, 54), (t(8, 1.0), sec(2.0), 48, 50),
        (t(8, 3.0), sec(1.8), 41, 52), (t(9, 1.0), sec(3.8), 46, 50), (t(10, 1.0), sec(5.0), 46, 46),
    ]
    guitar = []
    guitar += strum([46, 53, 56, 60, 61], t(1, 2.1), 50)
    guitar += strum([46, 55, 61, 65], t(2, 2.0), 48)
    guitar += strum([51, 54, 58, 61, 65], t(3, 1.8), 52)
    guitar += strum([54, 58, 61, 65, 67], t(4, 2.0), 52)
    guitar += strum([48, 54, 58, 63], t(5, 1.3), 48)
    guitar += strum([53, 57, 61, 64, 67], t(5, 3.2), 52)
    guitar += strum([46, 53, 58, 60], t(6, 2.0), 50)
    guitar += strum([54, 58, 61, 65], t(7, 2.1), 50)
    guitar += strum([53, 57, 60, 63], t(8, 2.2), 50)
    guitar += strum([46, 53, 58, 60], t(9, 2.0), 48)
    guitar += strum([46, 49, 55, 60], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 53, 48), (t(2, 3.3), sec(1.8), 58, 54),
        (t(3, 2.0), sec(2.0), 61, 58), (t(4, 2.0), sec(1.2), 65, 60), (t(4, 3.4), sec(1.5), 61, 52),
        (t(5, 2.0), sec(1.0), 60, 50), (t(5, 3.2), sec(1.8), 57, 54),
        (t(6, 2.0), sec(1.8), 58, 56), (t(7, 2.0), sec(1.2), 61, 58), (t(7, 3.5), sec(1.5), 65, 62),
        (t(8, 2.0), sec(1.4), 68, 65), (t(8, 3.6), sec(1.4), 65, 56),
        (t(9, 2.0), sec(1.2), 60, 52), (t(9, 3.5), sec(1.2), 58, 48), (t(10, 1.8), sec(4.5), 60, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 09 - Dimmed Lanterns", "Bbm"

def compose_10():
    cello = [
        (t(1, 1.0), sec(3.8), 39, 54), (t(2, 1.0), sec(3.8), 39, 52), (t(3, 1.0), sec(3.8), 47, 55),
        (t(4, 1.0), sec(3.8), 44, 54), (t(5, 1.0), sec(2.0), 41, 50), (t(5, 3.0), sec(1.8), 40, 52),
        (t(6, 1.0), sec(3.8), 46, 54), (t(7, 1.0), sec(3.8), 39, 52), (t(8, 1.0), sec(3.8), 47, 54),
        (t(9, 1.0), sec(2.0), 41, 50), (t(9, 3.0), sec(1.8), 46, 52), (t(10, 1.0), sec(5.0), 39, 46),
    ]
    guitar = []
    guitar += strum([51, 58, 61, 65, 66], t(1, 2.1), 50)
    guitar += strum([47, 54, 58, 63, 65], t(3, 1.8), 52)
    guitar += strum([56, 59, 63, 66, 68], t(4, 2.0), 50)
    guitar += strum([41, 47, 51, 56], t(5, 1.3), 48)
    guitar += strum([40, 46, 50, 56], t(5, 3.2), 50)
    guitar += strum([46, 50, 54, 57, 61], t(6, 2.1), 52)
    guitar += strum([51, 58, 63, 65], t(7, 2.0), 50)
    guitar += strum([47, 54, 58, 63], t(8, 2.1), 50)
    guitar += strum([46, 50, 53, 57], t(9, 2.2), 50)
    guitar += strum([51, 58, 63, 65], t(9, 3.8), 48)
    guitar += strum([51, 54, 60, 65], t(10, 1.4), 46, delay_s=0.05, dur_beats=5.0)
    clarinet = [
        (t(2, 2.2), sec(0.9), 58, 48), (t(2, 3.3), sec(1.8), 63, 54),
        (t(3, 2.0), sec(2.0), 65, 58), (t(4, 2.0), sec(1.2), 63, 54), (t(4, 3.4), sec(1.5), 60, 50),
        (t(5, 2.0), sec(1.0), 59, 52), (t(5, 3.2), sec(1.8), 58, 56),
        (t(6, 2.0), sec(1.8), 61, 58), (t(7, 2.0), sec(1.2), 63, 60), (t(7, 3.5), sec(1.5), 66, 64),
        (t(8, 2.0), sec(1.4), 65, 58), (t(8, 3.6), sec(1.4), 63, 54),
        (t(9, 2.0), sec(1.2), 58, 50), (t(9, 3.5), sec(1.2), 54, 46), (t(10, 1.8), sec(4.5), 65, 46),
    ]
    return {'cello': cello, 'guitar': guitar, 'clarinet': clarinet}, "Track 10 - The Final Clue", "Ebm"

COMPOSERS = [
    compose_01, compose_02, compose_03, compose_04, compose_05,
    compose_06, compose_07, compose_08, compose_09, compose_10,
]

def main():
    print("=== Generating Dark Jazz Collection (Clean, Melodic, 40 BPM) ===")
    for idx, comp_fn in enumerate(COMPOSERS, start=1):
        notes_by_inst, title, key_name = comp_fn()
        file_prefix = f"dark_jazz_{idx:02d}"
        midi_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.mid")
        wav_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.wav")
        mp3_path = os.path.join(OUTPUT_DIR, f"{file_prefix}.mp3")
        
        print(f"[{idx}/10] {title} ({key_name})...")
        export_midi(notes_by_inst, title, key_name, midi_path, bpm=BPM)
        audio_data = synthesize_audio(notes_by_inst, total_duration_sec=60.0)
        sf.write(wav_path, audio_data, SR, subtype='PCM_24')
        
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", wav_path,
            "-codec:a", "libmp3lame",
            "-b:a", "320k",
            "-metadata", f"title={title}",
            "-metadata", "artist=Dark Jazz Trio",
            "-metadata", "genre=Dark Jazz",
            mp3_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(wav_path):
            os.remove(wav_path)
            
    print(f"\nAll 10 tracks generated in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
