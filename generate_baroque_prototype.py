"""
Baroque Music Collection Prototype Generator
Generates 14 authentic Baroque tracks (2 tracks for each of 7 styles)
Tempo: 40 BPM (Grave / Adagio)
Duration: ~40 - 50 seconds each (musical period + natural reverb decay)
Outputs: MIDI (.mid) and High-Quality MP3 (320 kbps) with metadata

Styles:
1. La Folia
2. Passacaglia
3. Chaconne
4. Sarabande
5. Lamento (Ground Bass)
6. Siciliana
7. Invention / Polyphonic Canon
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
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "baroque_collection")
FFMPEG_PATH = os.path.join(os.path.dirname(__file__), "bin", "ffmpeg.exe")

os.makedirs(OUTPUT_DIR, exist_ok=True)

def midi_to_freq(note):
    return 440.0 * (2.0 ** ((note - 69.0) / 12.0))

# ---------------------------------------------------------------------------
# PRECOMPUTED DIGITAL FILTERS (ACOUSTIC BODY FORMANTS & SYSTEM SHAPING)
# ---------------------------------------------------------------------------

SOS_HARPSICHORD = signal.butter(3, [200, 6500], btype='bandpass', fs=SR, output='sos')
SOS_GAMBA = signal.butter(3, 1400, btype='low', fs=SR, output='sos')
SOS_THEORBO = signal.butter(3, 1300, btype='low', fs=SR, output='sos')
SOS_FLUTE = signal.butter(3, 2600, btype='low', fs=SR, output='sos')
SOS_FLUTE_CHIFF = signal.butter(2, [1800, 5000], btype='bandpass', fs=SR, output='sos')
SOS_ORGAN = signal.butter(3, 2200, btype='low', fs=SR, output='sos')
SOS_REV = signal.butter(2, 2200, btype='low', fs=SR, output='sos')
SOS_HP = signal.butter(2, 40, btype='high', fs=SR, output='sos')

# ---------------------------------------------------------------------------
# BAROQUE DSP ACOUSTIC SYNTHESIS ENGINE
# ---------------------------------------------------------------------------

def render_harpsichord(freq, duration_sec, velocity=64):
    """
    Authentic Harpsichord synthesis:
    Plucked quill plectrum impulse + rich metallic/gut harmonic spectrum + rapid high-freq decay.
    """
    ring_sec = min(duration_sec + 0.9, 1.8)
    n = int(ring_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, ring_sec, n, endpoint=False)
    
    # 1. Quill plucking impulse (burst of transient)
    click_len = min(int(0.005 * SR), n)
    click = np.zeros(n)
    click[:click_len] = np.sin(2 * np.pi * 3200 * t[:click_len]) * np.linspace(1, 0, click_len) * 0.35
    
    # 2. Harmonics with frequency-dependent decay
    sig = np.zeros(n)
    harmonics = [(1, 1.0, 2.0), (2, 0.65, 2.8), (3, 0.45, 3.6), (4, 0.30, 4.5), (5, 0.18, 5.5), (6, 0.10, 6.8), (7, 0.05, 8.0)]
    pitch_scale = (freq / 220.0) ** 0.30
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
        rel_len = int(0.04 * SR)
        end_rel = min(n, note_samples + rel_len)
        sig[note_samples:end_rel] *= np.linspace(1.0, 0.0, end_rel - note_samples)
        sig[end_rel:] = 0.0
        
    return sig * (velocity / 127.0) * 0.38

def render_gamba(freq, duration_sec, velocity=65):
    """
    Authentic Viola da Gamba / Baroque Cello:
    Bowed gut strings, rich woody core, gentle onset (bow catch), subtle authentic vibrato.
    """
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    # Baroque gut string vibrato: develops slowly after 0.4s, low depth (0.35%)
    vib_onset = np.clip((t - 0.40) / 0.50, 0, 1)
    vib = np.sin(2 * np.pi * 4.6 * t) * (0.0038 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    # Harmonic spectrum of bowed gut string
    harmonics = [1.0, 0.65, 0.40, 0.25, 0.14, 0.08, 0.04, 0.02]
    sig = np.zeros(n)
    for i, h_amp in enumerate(harmonics, start=1):
        if freq * i < SR * 0.44:
            sig += h_amp * np.sin(i * phase)
            
    sig = signal.sosfilt(SOS_GAMBA, sig)
    
    # Expressive bowed envelope: smooth cosine attack (no click) and natural release
    att = int(min(0.12 * SR, n * 0.3))
    rel = int(min(0.22 * SR, n * 0.3))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.36

def render_theorbo(freq, duration_sec, velocity=62):
    """
    Baroque Theorbo / Archlute:
    Plucked deep bass strings with long resonant ring and warm wood tone.
    """
    ring_sec = min(max(duration_sec, 2.5), 3.2)
    n = int(ring_sec * SR)
    t = np.linspace(0, ring_sec, n, endpoint=False)
    
    sig = np.zeros(n)
    harmonics = [(1, 1.0, 0.65), (2, 0.55, 1.1), (3, 0.28, 1.8), (4, 0.12, 2.6), (5, 0.05, 3.4)]
    phase_base = 2 * np.pi * freq * t
    for h, amp, decay_rate in harmonics:
        if freq * h < SR * 0.44:
            sig += amp * np.sin(h * phase_base) * np.exp(-decay_rate * t)
            
    # Attack ramp
    att_samples = int(0.005 * SR)
    if att_samples < n:
        sig[:att_samples] *= np.sin(np.linspace(0, np.pi / 2, att_samples))
        
    sig = signal.sosfilt(SOS_THEORBO, sig)
    return sig * (velocity / 127.0) * 0.34

def render_flauto_dolce(freq, duration_sec, velocity=62):
    """
    Baroque Flauto Dolce (Recorder):
    Woodwind breath chiff transient, pure fundamental, warm wooden tone.
    """
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    
    # Delicate vibrato
    vib_onset = np.clip((t - 0.30) / 0.40, 0, 1)
    vib = np.sin(2 * np.pi * 5.0 * t) * (0.0040 * vib_onset)
    phase = 2 * np.pi * np.cumsum(freq * (1.0 + vib)) / SR
    
    sig = 1.00 * np.sin(phase) + 0.28 * np.sin(2 * phase) + 0.08 * np.sin(3 * phase) + 0.02 * np.sin(4 * phase)
    
    # Breath chiff attack
    chiff_len = int(min(0.035 * SR, n))
    if chiff_len > 0:
        chiff = np.sin(2 * np.pi * 2800 * t[:chiff_len]) * 0.12 * np.linspace(1, 0, chiff_len)
        sig[:chiff_len] += chiff
        
    sig = signal.sosfilt(SOS_FLUTE, sig)
    
    att = int(min(0.08 * SR, n * 0.25))
    rel = int(min(0.14 * SR, n * 0.25))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.32

def render_positive_organ(freq, duration_sec, velocity=65):
    """
    Baroque Positive Organ (Portative Chamber Organ):
    Pure pipe tones, gentle tracker attack, steady 8' and 4' pipe blend.
    """
    n = int(duration_sec * SR)
    if n <= 0: return np.zeros(0)
    t = np.linspace(0, duration_sec, n, endpoint=False)
    phase = 2 * np.pi * freq * t
    
    sig = (
        1.00 * np.sin(phase) +
        0.45 * np.sin(2 * phase) +
        0.18 * np.sin(3 * phase) +
        0.08 * np.sin(4 * phase) +
        0.03 * np.sin(5 * phase)
    )
    
    sig = signal.sosfilt(SOS_ORGAN, sig)
    
    att = int(min(0.06 * SR, n * 0.2))
    rel = int(min(0.12 * SR, n * 0.2))
    env = np.ones(n)
    if n > att + rel:
        env[:att] = 0.5 * (1.0 - np.cos(np.linspace(0, np.pi, att)))
        env[-rel:] = 0.5 * (1.0 + np.cos(np.linspace(0, np.pi, rel)))
    else:
        env = signal.windows.hann(n)
        
    return sig * env * (velocity / 127.0) * 0.34

# ---------------------------------------------------------------------------
# BAROQUE STONE CHAMBER REVERB (ULTRA-FAST VECTORIZED SCHROEDER)
# ---------------------------------------------------------------------------

def fast_comb(x, d, g, max_refl=30):
    """Vectorized infinite impulse response comb filter using reflection expansion"""
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

def fast_allpass(x, d, g=0.5, max_refl=20):
    """Vectorized allpass filter using exact analytical decomposition: -g*x + (1-g^2)*w"""
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

def baroque_stone_reverb(stereo, sr=SR, room_size=0.86, wet=0.28):
    """
    Acoustics of a European Baroque stone chapel or library room:
    Warm reverberation without muddy sub-rumble or digital harshness.
    Runs in sub-second vectorized time via NumPy slice shifting.
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
        
    sos_rev = signal.butter(2, 2200, btype='low', fs=sr, output='sos')
    rev_l = signal.sosfilt(sos_rev, rev_l)
    rev_r = signal.sosfilt(sos_rev, rev_r)
    
    rev_stereo = np.column_stack([rev_l, rev_r])
    peak_rev = np.max(np.abs(rev_stereo)) + 1e-6
    peak_dry = np.max(np.abs(stereo)) + 1e-6
    rev_stereo = rev_stereo * (peak_dry / peak_rev)
    
    out = stereo * (1.0 - wet * 0.5) + rev_stereo * wet
    
    # Clean highpass for pristine low end
    sos_hp = signal.butter(2, 40, btype='high', fs=sr, output='sos')
    out[:, 0] = signal.sosfilt(sos_hp, out[:, 0])
    out[:, 1] = signal.sosfilt(sos_hp, out[:, 1])
    
    pk = np.max(np.abs(out))
    if pk > 1e-4:
        target = 10.0 ** (-1.5 / 20.0) # -1.5 dBFS
        out = out * (target / pk)
        
    return out

# ---------------------------------------------------------------------------
# AUDIO SYNTHESIS & MIDI EXPORT PIPELINE
# ---------------------------------------------------------------------------

INSTRUMENT_RENDERERS = {
    'harpsichord': render_harpsichord,
    'gamba': render_gamba,
    'theorbo': render_theorbo,
    'flute': render_flauto_dolce,
    'organ': render_positive_organ,
}

# Stereo Panning (L, R balance)
INSTRUMENT_PANS = {
    'harpsichord': (0.55, 0.45),
    'gamba': (0.45, 0.55),
    'theorbo': (0.40, 0.60),
    'flute': (0.52, 0.48),
    'organ': (0.50, 0.50),
}

# General MIDI program numbers
MIDI_PROGRAMS = {
    'harpsichord': (6, "Harpsichord"),
    'gamba': (42, "Cello"),
    'theorbo': (24, "Acoustic Guitar (Nylon)"),
    'flute': (74, "Recorder"),
    'organ': (19, "Church Organ"),
}

def synthesize_baroque_audio(notes_by_inst, total_duration_sec):
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
    return baroque_stone_reverb(stereo, sr=SR, room_size=0.86, wet=0.28)

def export_baroque_midi(notes_by_inst, title, key_name, meter, output_path, bpm=BPM):
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
        track.append(Message('program_change', program=prog_num, channel=ch, time=0))
        track.append(Message('control_change', control=91, value=90, channel=ch, time=0)) # Reverb
        track.append(Message('control_change', control=7, value=100, channel=ch, time=0))  # Volume
        
        events = []
        for start_s, dur_s, note, vel in notes:
            start_tick = int((start_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            dur_tick = int((dur_s / (60.0 / bpm)) * TICKS_PER_BEAT)
            events.append((start_tick, 10, Message('note_on', note=note, velocity=vel, channel=ch)))
            events.append((start_tick + dur_tick, 5, Message('note_off', note=note, velocity=0, channel=ch)))
            
        events.sort(key=lambda x: (x[0], x[1]))
        last_t = 0
        for tick, _, msg in events:
            delta = max(0, tick - last_t)
            msg.time = delta
            track.append(msg)
            last_t = tick
            
        track.append(MetaMessage('end_of_track', time=TICKS_PER_BEAT))
        ch += 1
        
    mid.save(output_path)

# Helper timing functions for 3/4 and 4/4 at 40 BPM
# At 40 BPM, quarter note = 1.5s
def t3(bar, beat, beat_sec=1.5):
    """Bar (1-based), beat (1.0 - 3.99) in 3/4"""
    return (bar - 1) * 3.0 * beat_sec + (beat - 1.0) * beat_sec

def t4(bar, beat, beat_sec=1.5):
    """Bar (1-based), beat (1.0 - 4.99) in 4/4"""
    return (bar - 1) * 4.0 * beat_sec + (beat - 1.0) * beat_sec

def dur(beats, beat_sec=1.5):
    return beats * beat_sec

def arpeggio(notes, start_s, base_vel=56, step_s=0.045, dur_beats=2.5, beat_sec=1.5):
    """Generates an authentic baroque arpeggiated broken chord (style luthé)"""
    res = []
    dur_s = dur(dur_beats, beat_sec)
    for i, n in enumerate(notes):
        n_start = start_s + i * step_s
        n_vel = max(40, min(80, base_vel + (i % 2) * 3))
        res.append((n_start, dur_s - i * step_s, n, n_vel))
    return res

# ---------------------------------------------------------------------------
# 14 BAROQUE COMPOSITIONS (2 TRACKS PER STYLE, ~40-50s)
# ---------------------------------------------------------------------------

# === STYLE 1: LA FOLIA ===

def compose_folia_01():
    """
    Track 01: La Folia in D minor (Corelli Grave Style)
    Instruments: Harpsichord + Viola da Gamba
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Chord cycle: Dm - A7 - Dm - C - F - C - Dm - A7 - Dm(cadence)
    """
    bs = 1.5
    # Gamba Ground Bass
    gamba = [
        (t3(1, 1.0), dur(2.8, bs), 38, 55), # D2
        (t3(2, 1.0), dur(2.8, bs), 45, 54), # A2
        (t3(3, 1.0), dur(2.8, bs), 38, 55), # D2
        (t3(4, 1.0), dur(2.8, bs), 48, 54), # C3
        (t3(5, 1.0), dur(2.8, bs), 41, 56), # F2
        (t3(6, 1.0), dur(2.8, bs), 48, 54), # C3
        (t3(7, 1.0), dur(1.8, bs), 38, 54), # D2
        (t3(7, 3.0), dur(0.9, bs), 43, 50), # G2
        (t3(8, 1.0), dur(2.8, bs), 45, 55), # A2
        (t3(9, 1.0), dur(2.8, bs), 38, 54), # D2
        (t3(10, 1.0), dur(3.8, bs), 38, 48), # D2 final
    ]
    
    # Harpsichord Chords (Style luthé / broken chords)
    harpsichord = []
    harpsichord += arpeggio([50, 57, 62, 65], t3(1, 1.2), 52) # Dm
    harpsichord += arpeggio([49, 57, 61, 64], t3(2, 1.2), 50) # A7/C#
    harpsichord += arpeggio([50, 57, 62, 65], t3(3, 1.2), 52) # Dm
    harpsichord += arpeggio([48, 55, 60, 64], t3(4, 1.2), 50) # C
    harpsichord += arpeggio([53, 57, 60, 65], t3(5, 1.2), 54) # F
    harpsichord += arpeggio([48, 55, 60, 64], t3(6, 1.2), 50) # C
    harpsichord += arpeggio([50, 57, 62, 65], t3(7, 1.2), 52) # Dm
    harpsichord += arpeggio([45, 52, 57, 61, 64], t3(8, 1.2), 54) # A7
    harpsichord += arpeggio([50, 57, 61, 65], t3(9, 1.2), 50) # Dm / dim
    harpsichord += arpeggio([38, 50, 57, 62, 66], t3(10, 1.0), 48, step_s=0.06, dur_beats=4.0) # D major (Picardy Third!)
    
    # Harpsichord Upper Melodic Ornamentation (La Folia theme)
    harpsichord += [
        (t3(1, 1.0), dur(1.8, bs), 62, 60), # D4
        (t3(1, 3.0), dur(0.9, bs), 64, 55), # E4
        (t3(2, 1.0), dur(2.8, bs), 65, 62), # F4
        (t3(3, 1.0), dur(1.8, bs), 64, 58), # E4
        (t3(3, 3.0), dur(0.9, bs), 62, 54), # D4
        (t3(4, 1.0), dur(2.8, bs), 60, 60), # C4
        (t3(5, 1.0), dur(1.8, bs), 65, 62), # F4
        (t3(5, 3.0), dur(0.9, bs), 67, 56), # G4
        (t3(6, 1.0), dur(2.8, bs), 69, 64), # A4
        (t3(7, 1.0), dur(1.4, bs), 67, 60), # G4
        (t3(7, 2.5), dur(0.5, bs), 65, 54), # F4
        (t3(7, 3.0), dur(0.9, bs), 64, 52), # E4
        (t3(8, 1.0), dur(1.8, bs), 61, 60), # C#4 (leading tone trill)
        (t3(8, 2.8), dur(0.4, bs), 62, 54), # D4
        (t3(8, 3.2), dur(0.6, bs), 61, 52), # C#4
        (t3(9, 1.0), dur(2.8, bs), 62, 58), # D4
        (t3(10, 1.0), dur(4.0, bs), 66, 52), # F#4 (Tiers de Picardie)
    ]
    
    return {'gamba': gamba, 'harpsichord': harpsichord}, "01 - La Folia in D minor (Grave & Noble)", "Dm", (3, 4), 45.0

def compose_folia_02():
    """
    Track 02: La Folia in G minor (Marin Marais / Flute & Theorbo)
    Instruments: Flauto Dolce + Theorbo + Viola da Gamba
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Gm - D7 - Gm - F - Bb - F - Gm - D7 - Gm
    """
    bs = 1.5
    theorbo = []
    theorbo += arpeggio([43, 50, 55, 58, 62], t3(1, 1.0), 54) # Gm
    theorbo += arpeggio([42, 50, 54, 57, 62], t3(2, 1.0), 52) # D7/F#
    theorbo += arpeggio([43, 50, 55, 58], t3(3, 1.0), 54)     # Gm
    theorbo += arpeggio([41, 48, 53, 57], t3(4, 1.0), 52)     # F
    theorbo += arpeggio([46, 50, 53, 58], t3(5, 1.0), 55)     # Bb
    theorbo += arpeggio([41, 48, 53, 57], t3(6, 1.0), 52)     # F
    theorbo += arpeggio([43, 50, 55, 58], t3(7, 1.0), 54)     # Gm
    theorbo += arpeggio([38, 45, 50, 54, 57], t3(8, 1.0), 54) # D7
    theorbo += arpeggio([43, 50, 55, 58], t3(9, 1.0), 52)     # Gm
    theorbo += arpeggio([31, 43, 50, 55, 59], t3(10, 1.0), 50, dur_beats=4.0) # G major
    
    gamba = [
        (t3(1, 1.0), dur(2.8, bs), 43, 52), (t3(2, 1.0), dur(2.8, bs), 42, 50),
        (t3(3, 1.0), dur(2.8, bs), 43, 52), (t3(4, 1.0), dur(2.8, bs), 41, 50),
        (t3(5, 1.0), dur(2.8, bs), 46, 54), (t3(6, 1.0), dur(2.8, bs), 41, 50),
        (t3(7, 1.0), dur(1.8, bs), 43, 52), (t3(7, 3.0), dur(0.9, bs), 48, 48),
        (t3(8, 1.0), dur(2.8, bs), 50, 52), (t3(9, 1.0), dur(2.8, bs), 43, 50),
        (t3(10, 1.0), dur(3.8, bs), 31, 46),
    ]
    
    # Flauto Dolce solo (florid baroque diminutions)
    flute = [
        (t3(1, 1.0), dur(1.8, bs), 67, 58), (t3(1, 3.0), dur(0.9, bs), 69, 54),
        (t3(2, 1.0), dur(2.8, bs), 70, 60),
        (t3(3, 1.0), dur(1.4, bs), 69, 56), (t3(3, 2.5), dur(0.5, bs), 67, 52), (t3(3, 3.0), dur(0.9, bs), 65, 54),
        (t3(4, 1.0), dur(2.8, bs), 65, 58),
        (t3(5, 1.0), dur(1.8, bs), 70, 62), (t3(5, 3.0), dur(0.9, bs), 72, 58),
        (t3(6, 1.0), dur(2.8, bs), 74, 64),
        (t3(7, 1.0), dur(1.0, bs), 72, 58), (t3(7, 2.0), dur(1.0, bs), 70, 56), (t3(7, 3.0), dur(0.9, bs), 69, 54),
        (t3(8, 1.0), dur(1.8, bs), 66, 60), (t3(8, 3.0), dur(0.9, bs), 67, 56),
        (t3(9, 1.0), dur(2.8, bs), 67, 56),
        (t3(10, 1.0), dur(4.0, bs), 71, 50), # B natural (G major picardy)
    ]
    
    return {'theorbo': theorbo, 'gamba': gamba, 'flute': flute}, "02 - La Folia in G minor (Florid Flute & Theorbo)", "Gm", (3, 4), 45.0

# === STYLE 2: PASSACAGLIA ===

def compose_passacaglia_01():
    """
    Track 03: Passacaglia in C minor (Bachian Ground Counterpoint)
    Instruments: Positive Organ + Viola da Gamba
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Ground Bass: C - Bb - Ab - G (with suspensions in the organ manual)
    """
    bs = 1.5
    # Gamba Ostinato
    gamba = [
        # Phrase 1
        (t3(1, 1.0), dur(2.8, bs), 36, 56), # C2
        (t3(2, 1.0), dur(2.8, bs), 34, 54), # Bb1
        (t3(3, 1.0), dur(2.8, bs), 32, 54), # Ab1
        (t3(4, 1.0), dur(2.8, bs), 31, 58), # G1
        # Phrase 2 (variation)
        (t3(5, 1.0), dur(1.8, bs), 36, 56), (t3(5, 3.0), dur(0.9, bs), 43, 50),
        (t3(6, 1.0), dur(1.8, bs), 34, 54), (t3(6, 3.0), dur(0.9, bs), 41, 48),
        (t3(7, 1.0), dur(1.8, bs), 32, 54), (t3(7, 3.0), dur(0.9, bs), 44, 50),
        (t3(8, 1.0), dur(2.8, bs), 31, 56),
        # Cadence
        (t3(9, 1.0), dur(1.4, bs), 36, 52), (t3(9, 2.5), dur(1.4, bs), 31, 54),
        (t3(10, 1.0), dur(4.0, bs), 36, 50),
    ]
    
    # Organ Polyphonic Counterpoint with famous 4-3 and 7-6 suspensions
    organ = [
        # Bar 1: C minor with suspended 4th (F4 -> Eb4)
        (t3(1, 1.0), dur(1.4, bs), 65, 58), (t3(1, 2.5), dur(1.4, bs), 63, 54),
        (t3(1, 1.0), dur(2.8, bs), 60, 52), (t3(1, 1.0), dur(2.8, bs), 55, 50),
        # Bar 2: Bb major (Eb4 -> D4)
        (t3(2, 1.0), dur(1.4, bs), 63, 56), (t3(2, 2.5), dur(1.4, bs), 62, 52),
        (t3(2, 1.0), dur(2.8, bs), 58, 50),
        # Bar 3: Ab major (D4 -> C4)
        (t3(3, 1.0), dur(1.4, bs), 62, 56), (t3(3, 2.5), dur(1.4, bs), 60, 52),
        (t3(3, 1.0), dur(2.8, bs), 56, 50),
        # Bar 4: G dominant (C4 -> B3)
        (t3(4, 1.0), dur(1.4, bs), 60, 60), (t3(4, 2.5), dur(1.4, bs), 59, 56),
        (t3(4, 1.0), dur(2.8, bs), 55, 52),
        # Bar 5-8: Higher octave polyphony
        (t3(5, 1.0), dur(1.8, bs), 72, 60), (t3(5, 3.0), dur(0.9, bs), 70, 54),
        (t3(6, 1.0), dur(1.8, bs), 70, 58), (t3(6, 3.0), dur(0.9, bs), 68, 52),
        (t3(7, 1.0), dur(1.8, bs), 68, 58), (t3(7, 3.0), dur(0.9, bs), 67, 54),
        (t3(8, 1.0), dur(1.4, bs), 67, 62), (t3(8, 2.5), dur(1.4, bs), 65, 56), # Leading tone resolution
        # Bar 9-10: Grand cadence
        (t3(9, 1.0), dur(1.4, bs), 63, 56), (t3(9, 2.5), dur(1.4, bs), 62, 58),
        (t3(9, 1.0), dur(2.8, bs), 55, 52),
        (t3(10, 1.0), dur(4.0, bs), 64, 54), # E natural (C major picardy)
        (t3(10, 1.0), dur(4.0, bs), 60, 52),
        (t3(10, 1.0), dur(4.0, bs), 48, 50),
    ]
    
    return {'gamba': gamba, 'organ': organ}, "03 - Passacaglia in C minor (Bachian Counterpoint)", "Cm", (3, 4), 45.0

def compose_passacaglia_02():
    """
    Track 04: Passacaglia in G minor (Handel Arpeggiato)
    Instruments: Harpsichord solo + Viola da Gamba
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    """
    bs = 1.5
    gamba = [
        (t3(1, 1.0), dur(2.8, bs), 43, 54), (t3(2, 1.0), dur(2.8, bs), 42, 52),
        (t3(3, 1.0), dur(2.8, bs), 41, 52), (t3(4, 1.0), dur(2.8, bs), 40, 50),
        (t3(5, 1.0), dur(2.8, bs), 39, 54), (t3(6, 1.0), dur(2.8, bs), 38, 55),
        (t3(7, 1.0), dur(2.8, bs), 39, 52), (t3(8, 1.0), dur(2.8, bs), 38, 54),
        (t3(9, 1.0), dur(2.8, bs), 43, 52), (t3(10, 1.0), dur(4.0, bs), 43, 46),
    ]
    
    harpsichord = []
    # Virtuosic broken arpeggio passes in Handel style
    harpsichord += arpeggio([43, 50, 55, 58, 62, 67], t3(1, 1.0), 54, step_s=0.04)
    harpsichord += arpeggio([42, 50, 54, 57, 62, 66], t3(2, 1.0), 52, step_s=0.04)
    harpsichord += arpeggio([41, 46, 53, 58, 62, 65], t3(3, 1.0), 52, step_s=0.04)
    harpsichord += arpeggio([40, 46, 52, 55, 58, 64], t3(4, 1.0), 52, step_s=0.04)
    harpsichord += arpeggio([39, 46, 51, 55, 58, 63], t3(5, 1.0), 54, step_s=0.04)
    harpsichord += arpeggio([38, 45, 50, 54, 57, 62], t3(6, 1.0), 56, step_s=0.04)
    harpsichord += arpeggio([39, 46, 51, 55, 58, 63], t3(7, 1.0), 52, step_s=0.04)
    harpsichord += arpeggio([38, 45, 50, 54, 57, 62], t3(8, 1.0), 54, step_s=0.04)
    harpsichord += arpeggio([43, 50, 55, 58, 62, 67], t3(9, 1.0), 52, step_s=0.04)
    harpsichord += arpeggio([31, 43, 50, 55, 59, 67], t3(10, 1.0), 48, step_s=0.06, dur_beats=4.0)
    
    return {'gamba': gamba, 'harpsichord': harpsichord}, "04 - Passacaglia in G minor (Handel Arpeggiato)", "Gm", (3, 4), 45.0

# === STYLE 3: CHACONNE ===

def compose_chaconne_01():
    """
    Track 05: Chaconne in D minor (Ciaccona Arpeggiata / Bach Style)
    Instruments: Harpsichord solo
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Strong accent on Beat 2 with rolling broken chords
    """
    bs = 1.5
    harpsichord = []
    
    # Bars 1 to 10: Beat 1 is a firm bass note, Beat 2 is a rolling arpeggiated chord
    chords_seq = [
        (38, [50, 57, 62, 65]),       # Dm
        (36, [48, 57, 60, 65]),       # Dm/C
        (34, [46, 53, 58, 62, 65]),   # Bbmaj7
        (33, [45, 52, 57, 61, 64]),   # A7
        (38, [50, 57, 62, 65]),       # Dm
        (35, [47, 53, 56, 62]),       # G#dim7
        (33, [45, 52, 57, 61, 64]),   # A7sus4
        (45, [52, 57, 61, 64, 69]),   # A7
        (38, [50, 57, 62, 65]),       # Dm
        (26, [38, 50, 57, 62, 66]),   # D major (Picardy)
    ]
    
    for bar_idx, (bass_pitch, chord_pitches) in enumerate(chords_seq, start=1):
        # Beat 1 bass note
        harpsichord.append((t3(bar_idx, 1.0), dur(1.0, bs), bass_pitch, 60))
        # Beat 2 dramatic accented arpeggio (Baroque Chaconne signature!)
        harpsichord += arpeggio(chord_pitches, t3(bar_idx, 2.0), base_vel=64, step_s=0.035, dur_beats=1.8)
        
    return {'harpsichord': harpsichord}, "05 - Chaconne in D minor (Ciaccona Arpeggiata)", "Dm", (3, 4), 45.0

def compose_chaconne_02():
    """
    Track 06: Chaconne in G major (Lully Royal Court)
    Instruments: Flauto Dolce + Viola da Gamba + Harpsichord
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Bright, noble, majestic French court style
    """
    bs = 1.5
    gamba = [
        (t3(1, 1.0), dur(2.8, bs), 43, 56), (t3(2, 1.0), dur(2.8, bs), 42, 54),
        (t3(3, 1.0), dur(2.8, bs), 40, 54), (t3(4, 1.0), dur(2.8, bs), 38, 52),
        (t3(5, 1.0), dur(2.8, bs), 36, 54), (t3(6, 1.0), dur(2.8, bs), 35, 52),
        (t3(7, 1.0), dur(2.8, bs), 33, 54), (t3(8, 1.0), dur(2.8, bs), 38, 56),
        (t3(9, 1.0), dur(2.8, bs), 43, 54), (t3(10, 1.0), dur(4.0, bs), 43, 48),
    ]
    
    harpsichord = []
    harpsichord += arpeggio([43, 50, 55, 59, 62], t3(1, 2.0), 52) # G
    harpsichord += arpeggio([42, 50, 54, 57, 62], t3(2, 2.0), 50) # D/F#
    harpsichord += arpeggio([40, 47, 52, 55, 59], t3(3, 2.0), 52) # Em
    harpsichord += arpeggio([38, 47, 50, 54, 59], t3(4, 2.0), 50) # Bm/D
    harpsichord += arpeggio([36, 48, 52, 55, 60], t3(5, 2.0), 52) # C
    harpsichord += arpeggio([35, 47, 50, 55, 59], t3(6, 2.0), 50) # G/B
    harpsichord += arpeggio([33, 45, 48, 52, 57], t3(7, 2.0), 52) # Am7
    harpsichord += arpeggio([38, 45, 50, 54, 57], t3(8, 2.0), 55) # D7
    harpsichord += arpeggio([43, 50, 55, 59, 62], t3(9, 2.0), 52) # G
    harpsichord += arpeggio([31, 43, 50, 55, 59], t3(10, 1.0), 48, dur_beats=4.0)
    
    flute = [
        (t3(1, 2.0), dur(1.8, bs), 71, 60), (t3(2, 2.0), dur(1.8, bs), 69, 58),
        (t3(3, 2.0), dur(1.8, bs), 67, 58), (t3(4, 2.0), dur(1.8, bs), 66, 56),
        (t3(5, 2.0), dur(1.8, bs), 67, 60), (t3(6, 2.0), dur(1.8, bs), 71, 62),
        (t3(7, 2.0), dur(1.8, bs), 72, 64), (t3(8, 2.0), dur(1.8, bs), 74, 62),
        (t3(9, 2.0), dur(1.8, bs), 71, 58), (t3(10, 1.0), dur(4.0, bs), 67, 52),
    ]
    
    return {'gamba': gamba, 'harpsichord': harpsichord, 'flute': flute}, "06 - Chaconne in G major (Lully Royal Court)", "G", (3, 4), 45.0

# === STYLE 4: SARABANDE ===

def compose_sarabande_01():
    """
    Track 07: Sarabande in A minor (Intimate Harpsichord)
    Instruments: Harpsichord solo
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    Solemn Spanish/French dance with elongated second beat and ornaments
    """
    bs = 1.5
    harpsichord = []
    
    # Am -> E7 -> Am -> Dm -> G -> C -> F -> Bdim -> E7 -> Am
    sarabande_score = [
        (45, [52, 57, 60, 64], 69), # Bar 1: Am (melody A4)
        (40, [47, 52, 56, 59], 68), # Bar 2: E7 (melody G#4)
        (45, [52, 57, 60, 64], 69), # Bar 3: Am (melody A4)
        (38, [50, 53, 57, 62], 72), # Bar 4: Dm (melody C5)
        (43, [47, 50, 55, 59], 71), # Bar 5: G7 (melody B4)
        (36, [48, 52, 55, 60], 72), # Bar 6: C (melody C5)
        (41, [45, 48, 53, 57], 69), # Bar 7: F (melody A4)
        (35, [47, 50, 53, 56], 68), # Bar 8: Bdim (melody G#4)
        (40, [46, 52, 56, 59], 64), # Bar 9: E7 (melody E4)
        (33, [45, 52, 57, 60], 69), # Bar 10: Am final
    ]
    
    for bar_idx, (bass_n, chord_ns, mel_n) in enumerate(sarabande_score, start=1):
        # Beat 1: bass note
        harpsichord.append((t3(bar_idx, 1.0), dur(1.0, bs), bass_n, 56))
        # Beat 2: accented sustained chord with melody on top (Sarabande hallmark)
        full_chord = chord_ns + [mel_n]
        harpsichord += arpeggio(full_chord, t3(bar_idx, 2.0), base_vel=62, step_s=0.038, dur_beats=1.9)
        # Subtle ornament / mordent on beat 3 of select bars
        if bar_idx in [2, 4, 8]:
            harpsichord.append((t3(bar_idx, 3.4), dur(0.5, bs), mel_n + 1, 50))
            harpsichord.append((t3(bar_idx, 3.7), dur(0.4, bs), mel_n, 52))
            
    return {'harpsichord': harpsichord}, "07 - Sarabande in A minor (Intimate Harpsichord)", "Am", (3, 4), 45.0

def compose_sarabande_02():
    """
    Track 08: Sarabande in D minor (Gamba Meditations & Theorbo / Handel Vibe)
    Instruments: Viola da Gamba + Theorbo
    10 bars in 3/4 @ 40 BPM = 45.0 seconds
    """
    bs = 1.5
    theorbo = []
    theorbo += arpeggio([38, 45, 50, 53, 57], t3(1, 1.0), 54) # Dm
    theorbo += arpeggio([37, 45, 49, 52, 57], t3(2, 1.0), 52) # A/C#
    theorbo += arpeggio([38, 45, 50, 53, 57], t3(3, 1.0), 54) # Dm
    theorbo += arpeggio([35, 43, 46, 50, 55], t3(4, 1.0), 54) # Gm
    theorbo += arpeggio([36, 43, 48, 52, 55], t3(5, 1.0), 52) # C
    theorbo += arpeggio([33, 41, 45, 48, 53], t3(6, 1.0), 54) # F
    theorbo += arpeggio([34, 41, 46, 50, 53], t3(7, 1.0), 52) # Bb
    theorbo += arpeggio([40, 43, 46, 49, 52], t3(8, 1.0), 52) # Edim
    theorbo += arpeggio([33, 40, 45, 49, 52], t3(9, 1.0), 56) # A7
    theorbo += arpeggio([26, 38, 45, 50, 54], t3(10, 1.0), 50, dur_beats=4.0) # D major
    
    # Gamba soulful bowed cantilena with Sarabande accent on beat 2
    gamba = [
        (t3(1, 1.5), dur(2.2, bs), 62, 62), # D3
        (t3(2, 1.5), dur(2.2, bs), 61, 60), # C#3
        (t3(3, 1.5), dur(2.2, bs), 62, 62), # D3
        (t3(4, 1.5), dur(2.2, bs), 67, 65), # G3
        (t3(5, 1.5), dur(2.2, bs), 65, 62), # F3
        (t3(6, 1.5), dur(2.2, bs), 64, 60), # E3
        (t3(7, 1.5), dur(2.2, bs), 65, 62), # F3
        (t3(8, 1.5), dur(2.2, bs), 64, 60), # E3
        (t3(9, 1.5), dur(2.2, bs), 61, 58), # C#3
        (t3(10, 1.0), dur(4.0, bs), 62, 50), # D3
    ]
    
    return {'theorbo': theorbo, 'gamba': gamba}, "08 - Sarabande in D minor (Gamba Meditations)", "Dm", (3, 4), 45.0

# === STYLE 5: LAMENTO (GROUND BASS) ===

def compose_lamento_01():
    """
    Track 09: Lamento in G minor (Purcell Passus Duriusculus)
    Instruments: Flauto Dolce + Viola da Gamba + Harpsichord
    7 bars in 4/4 @ 40 BPM = 42.0 seconds (+ 4.5s tail = 46.5s)
    Chromatic descending ground bass (G - F# - F - E - Eb - D)
    Heart-wrenching baroque suspensions (7-6, 4-3, 9-8)
    """
    bs = 1.5
    # Gamba Passus Duriusculus
    gamba = [
        (t4(1, 1.0), dur(3.8, bs), 43, 56), # G2
        (t4(2, 1.0), dur(3.8, bs), 42, 54), # F#2
        (t4(3, 1.0), dur(3.8, bs), 41, 54), # F2
        (t4(4, 1.0), dur(3.8, bs), 40, 52), # E2
        (t4(5, 1.0), dur(3.8, bs), 39, 54), # Eb2
        (t4(6, 1.0), dur(3.8, bs), 38, 56), # D2
        (t4(7, 1.0), dur(4.5, bs), 31, 50), # G1 final
    ]
    
    harpsichord = []
    harpsichord += arpeggio([43, 50, 55, 58], t4(1, 1.0), 50)
    harpsichord += arpeggio([42, 50, 54, 57], t4(2, 1.0), 50)
    harpsichord += arpeggio([41, 46, 53, 58], t4(3, 1.0), 50)
    harpsichord += arpeggio([40, 46, 52, 55], t4(4, 1.0), 50)
    harpsichord += arpeggio([39, 46, 51, 55], t4(5, 1.0), 52)
    harpsichord += arpeggio([38, 45, 50, 54, 57], t4(6, 1.0), 54)
    harpsichord += arpeggio([31, 43, 50, 55, 59], t4(7, 1.0), 48, dur_beats=4.5)
    
    # Flute weeping lamento with poignant suspensions
    flute = [
        (t4(1, 2.0), dur(2.8, bs), 67, 60), # G4
        (t4(2, 1.0), dur(1.8, bs), 68, 62), # Ab4 (poignant minor 9th tension!)
        (t4(2, 3.0), dur(1.8, bs), 67, 58), # G4 resolution
        (t4(3, 1.0), dur(1.8, bs), 70, 62), # Bb4
        (t4(3, 3.0), dur(1.8, bs), 69, 58), # A4 resolution
        (t4(4, 1.0), dur(1.8, bs), 67, 60), # G4
        (t4(4, 3.0), dur(1.8, bs), 66, 56), # F#4
        (t4(5, 1.0), dur(1.8, bs), 65, 60), # F4
        (t4(5, 3.0), dur(1.8, bs), 63, 56), # Eb4
        (t4(6, 1.0), dur(1.8, bs), 62, 58), # D4
        (t4(6, 3.0), dur(1.8, bs), 61, 54), # C#4 (leading tone)
        (t4(7, 1.0), dur(4.5, bs), 67, 50), # G4 resting
    ]
    
    return {'gamba': gamba, 'harpsichord': harpsichord, 'flute': flute}, "09 - Lamento in G minor (Passus Duriusculus)", "Gm", (4, 4), 42.0

def compose_lamento_02():
    """
    Track 10: Lamento in C minor (Monteverdi Pianto)
    Instruments: Viola da Gamba + Theorbo
    7 bars in 4/4 @ 40 BPM = 42.0 seconds (+ 4.5s tail)
    """
    bs = 1.5
    theorbo = []
    theorbo += arpeggio([36, 43, 48, 51, 55], t4(1, 1.0), 54) # Cm
    theorbo += arpeggio([35, 43, 47, 50, 55], t4(2, 1.0), 52) # G/B
    theorbo += arpeggio([34, 41, 46, 50, 53], t4(3, 1.0), 52) # Bb
    theorbo += arpeggio([33, 41, 45, 48, 53], t4(4, 1.0), 50) # F/A
    theorbo += arpeggio([32, 39, 44, 48, 51], t4(5, 1.0), 54) # Ab
    theorbo += arpeggio([31, 38, 43, 47, 50], t4(6, 1.0), 56) # G7
    theorbo += arpeggio([24, 36, 43, 48, 52], t4(7, 1.0), 50, dur_beats=4.5) # C major
    
    gamba = [
        (t4(1, 2.0), dur(2.8, bs), 60, 60), # C3
        (t4(2, 1.0), dur(1.8, bs), 63, 64), # Eb3
        (t4(2, 3.0), dur(1.8, bs), 62, 58), # D3
        (t4(3, 1.0), dur(1.8, bs), 65, 62), # F3
        (t4(3, 3.0), dur(1.8, bs), 63, 58), # Eb3
        (t4(4, 1.0), dur(1.8, bs), 62, 60), # D3
        (t4(4, 3.0), dur(1.8, bs), 60, 56), # C3
        (t4(5, 1.0), dur(1.8, bs), 60, 62), # C3
        (t4(5, 3.0), dur(1.8, bs), 59, 58), # B2
        (t4(6, 1.0), dur(1.8, bs), 62, 62), # D3
        (t4(6, 3.0), dur(1.8, bs), 59, 56), # B2
        (t4(7, 1.0), dur(4.5, bs), 64, 50), # E3 (Picardy third)
    ]
    
    return {'theorbo': theorbo, 'gamba': gamba}, "10 - Lamento in C minor (Monteverdi Pianto)", "Cm", (4, 4), 42.0

# === STYLE 6: SICILIANA ===

def compose_siciliana_01():
    """
    Track 11: Siciliana in F major (Telemann Pastoral)
    Instruments: Flauto Dolce + Viola da Gamba + Harpsichord
    14 bars in 6/8 @ 40 BPM (dotted quarter = 1.5s, 1 bar = 3.0s) = 42.0 seconds (+ 4.5s tail)
    Gentle rocking dotted rhythm
    """
    # At 40 BPM dotted quarter, 1 bar of 6/8 = 3.0 seconds
    bar_sec = 3.0
    gamba = []
    harpsichord = []
    flute = []
    
    chords = [
        (41, [53, 57, 60, 65]), # 1: F
        (38, [50, 53, 57, 62]), # 2: Dm
        (34, [46, 50, 53, 58]), # 3: Bb
        (36, [48, 52, 55, 60]), # 4: C
        (41, [53, 57, 60, 65]), # 5: F
        (34, [46, 50, 53, 58]), # 6: Bb
        (36, [48, 52, 55, 60]), # 7: C7
        (38, [50, 53, 57, 62]), # 8: Dm
        (34, [46, 50, 53, 58]), # 9: Bb
        (36, [48, 52, 55, 60]), # 10: C7
        (41, [53, 57, 60, 65]), # 11: F
        (36, [48, 52, 55, 60]), # 12: C
        (41, [53, 57, 60, 65]), # 13: F
        (29, [41, 53, 57, 65]), # 14: F final
    ]
    
    for i, (bass_n, chord_ns) in enumerate(chords):
        t_bar = i * bar_sec
        # Gamba rocking bass
        gamba.append((t_bar, 1.4, bass_n, 54))
        gamba.append((t_bar + 1.5, 1.4, bass_n + 7, 50))
        # Harpsichord continuo
        harpsichord += arpeggio(chord_ns, t_bar + 0.2, base_vel=50, step_s=0.035, dur_beats=1.6)
        
    # Flute Siciliana dotted melody (dotted 8th + 16th + 8th pattern)
    # in 6/8: beat 1 is 0.0 - 1.5s, beat 2 is 1.5 - 3.0s
    flute_notes = [
        # Bar 1
        (0 * bar_sec + 0.0, 0.9, 65, 60), (0 * bar_sec + 0.9, 0.5, 67, 54), (0 * bar_sec + 1.5, 1.4, 69, 62),
        # Bar 2
        (1 * bar_sec + 0.0, 0.9, 69, 60), (1 * bar_sec + 0.9, 0.5, 70, 54), (1 * bar_sec + 1.5, 1.4, 72, 64),
        # Bar 3
        (2 * bar_sec + 0.0, 0.9, 74, 62), (2 * bar_sec + 0.9, 0.5, 72, 56), (2 * bar_sec + 1.5, 1.4, 70, 58),
        # Bar 4
        (3 * bar_sec + 0.0, 2.8, 67, 58),
        # Bar 5
        (4 * bar_sec + 0.0, 0.9, 69, 60), (4 * bar_sec + 0.9, 0.5, 70, 54), (4 * bar_sec + 1.5, 1.4, 72, 62),
        # Bar 6
        (5 * bar_sec + 0.0, 0.9, 74, 64), (5 * bar_sec + 0.9, 0.5, 76, 58), (5 * bar_sec + 1.5, 1.4, 77, 66),
        # Bar 7
        (6 * bar_sec + 0.0, 1.4, 76, 62), (6 * bar_sec + 1.5, 1.4, 74, 58),
        # Bar 8
        (7 * bar_sec + 0.0, 2.8, 72, 60),
        # Bar 9-14 (Gentle pastoral resolution)
        (8 * bar_sec + 0.0, 1.4, 70, 58), (8 * bar_sec + 1.5, 1.4, 69, 56),
        (9 * bar_sec + 0.0, 1.4, 67, 56), (9 * bar_sec + 1.5, 1.4, 65, 54),
        (10 * bar_sec + 0.0, 2.8, 69, 60),
        (11 * bar_sec + 0.0, 1.4, 67, 56), (11 * bar_sec + 1.5, 1.4, 64, 54),
        (12 * bar_sec + 0.0, 2.8, 65, 58),
        (13 * bar_sec + 0.0, 4.5, 65, 50),
    ]
    flute.extend(flute_notes)
    
    return {'gamba': gamba, 'harpsichord': harpsichord, 'flute': flute}, "11 - Siciliana in F major (Telemann Pastoral)", "F", (6, 8), 42.0

def compose_siciliana_02():
    """
    Track 12: Siciliana in A minor (Bachian Melancholy / Erbarme dich Spirit)
    Instruments: Flauto Dolce + Viola da Gamba + Theorbo
    14 bars in 6/8 @ 40 BPM = 42.0 seconds (+ 4.5s tail)
    """
    bar_sec = 3.0
    gamba = []
    theorbo = []
    flute = []
    
    chords = [
        (45, [52, 57, 60, 64]), # 1: Am
        (40, [47, 52, 56, 59]), # 2: E7
        (45, [52, 57, 60, 64]), # 3: Am
        (38, [50, 53, 57, 62]), # 4: Dm
        (35, [47, 50, 53, 57]), # 5: Bdim
        (40, [47, 52, 56, 59]), # 6: E7
        (45, [52, 57, 60, 64]), # 7: Am
        (41, [48, 53, 57, 60]), # 8: F
        (38, [50, 53, 57, 62]), # 9: Dm
        (35, [47, 50, 53, 57]), # 10: Bdim
        (40, [47, 52, 56, 59]), # 11: E7
        (45, [52, 57, 60, 64]), # 12: Am
        (40, [47, 52, 56, 59]), # 13: E7
        (33, [45, 52, 57, 61]), # 14: A major (Picardy)
    ]
    
    for i, (bass_n, chord_ns) in enumerate(chords):
        t_bar = i * bar_sec
        gamba.append((t_bar, 1.4, bass_n, 52))
        theorbo += arpeggio(chord_ns, t_bar + 0.15, base_vel=52, step_s=0.04, dur_beats=1.8)
        
    flute_notes = [
        (0 * bar_sec + 0.0, 0.9, 69, 62), (0 * bar_sec + 0.9, 0.5, 71, 56), (0 * bar_sec + 1.5, 1.4, 72, 64),
        (1 * bar_sec + 0.0, 0.9, 71, 60), (1 * bar_sec + 0.9, 0.5, 69, 54), (1 * bar_sec + 1.5, 1.4, 68, 58),
        (2 * bar_sec + 0.0, 2.8, 69, 62),
        (3 * bar_sec + 0.0, 0.9, 72, 64), (3 * bar_sec + 0.9, 0.5, 74, 58), (3 * bar_sec + 1.5, 1.4, 76, 66),
        (4 * bar_sec + 0.0, 1.4, 74, 60), (4 * bar_sec + 1.5, 1.4, 72, 58),
        (5 * bar_sec + 0.0, 2.8, 71, 60),
        (6 * bar_sec + 0.0, 2.8, 69, 62),
        (7 * bar_sec + 0.0, 1.4, 69, 58), (7 * bar_sec + 1.5, 1.4, 68, 56),
        (8 * bar_sec + 0.0, 1.4, 65, 56), (8 * bar_sec + 1.5, 1.4, 64, 54),
        (9 * bar_sec + 0.0, 1.4, 62, 54), (9 * bar_sec + 1.5, 1.4, 65, 56),
        (10 * bar_sec + 0.0, 2.8, 64, 58),
        (11 * bar_sec + 0.0, 2.8, 60, 56),
        (12 * bar_sec + 0.0, 1.4, 64, 56), (12 * bar_sec + 1.5, 1.4, 68, 58),
        (13 * bar_sec + 0.0, 4.5, 69, 50),
    ]
    flute.extend(flute_notes)
    
    return {'gamba': gamba, 'theorbo': theorbo, 'flute': flute}, "12 - Siciliana in A minor (Bachian Melancholy)", "Am", (6, 8), 42.0

# === STYLE 7: INVENTION & POLYPHONIC CANON ===

def compose_invention_01():
    """
    Track 13: Two-Part Invention in D minor (J.S. Bach Style)
    Instruments: Harpsichord (Upper & Lower Manuals)
    7 bars in 4/4 @ 40 BPM = 42.0 seconds (+ 4.5s tail)
    Subject introduced in Upper voice, imitated in Lower voice, expanding into strict 2-part counterpoint
    """
    bs = 1.5
    upper = []
    lower = []
    
    # Subject: D - E - F - G - A - F - D - C# (Bar 1)
    # Upper manual plays subject in Bar 1
    upper += [
        (t4(1, 1.0), dur(0.5, bs), 62, 64), # D4
        (t4(1, 1.5), dur(0.5, bs), 64, 58), # E4
        (t4(1, 2.0), dur(0.5, bs), 65, 62), # F4
        (t4(1, 2.5), dur(0.5, bs), 67, 60), # G4
        (t4(1, 3.0), dur(1.0, bs), 69, 65), # A4
        (t4(1, 4.0), dur(0.5, bs), 65, 60), # F4
        (t4(1, 4.5), dur(0.5, bs), 61, 56), # C#4
    ]
    
    # Lower manual imitates subject an octave lower in Bar 2!
    lower += [
        (t4(2, 1.0), dur(0.5, bs), 50, 64), # D3
        (t4(2, 1.5), dur(0.5, bs), 52, 58), # E3
        (t4(2, 2.0), dur(0.5, bs), 53, 62), # F3
        (t4(2, 2.5), dur(0.5, bs), 55, 60), # G3
        (t4(2, 3.0), dur(1.0, bs), 57, 65), # A3
        (t4(2, 4.0), dur(0.5, bs), 53, 60), # F3
        (t4(2, 4.5), dur(0.5, bs), 49, 56), # C#3
    ]
    
    # Meanwhile, Upper manual plays countersubject in Bar 2:
    upper += [
        (t4(2, 1.0), dur(1.0, bs), 62, 58),
        (t4(2, 2.0), dur(1.0, bs), 65, 60),
        (t4(2, 3.0), dur(1.0, bs), 64, 58),
        (t4(2, 4.0), dur(1.0, bs), 62, 56),
    ]
    
    # Bar 3: Modulation towards F major (parallel major)
    upper += [
        (t4(3, 1.0), dur(0.5, bs), 65, 62), (t4(3, 1.5), dur(0.5, bs), 67, 60),
        (t4(3, 2.0), dur(1.0, bs), 69, 64),
        (t4(3, 3.0), dur(1.0, bs), 72, 65), (t4(3, 4.0), dur(1.0, bs), 70, 60),
    ]
    lower += [
        (t4(3, 1.0), dur(1.0, bs), 53, 56), (t4(3, 2.0), dur(1.0, bs), 55, 58),
        (t4(3, 3.0), dur(1.0, bs), 57, 60), (t4(3, 4.0), dur(1.0, bs), 58, 62),
    ]
    
    # Bar 4: Dialogue in sequential tenths
    upper += [
        (t4(4, 1.0), dur(1.0, bs), 69, 62), (t4(4, 2.0), dur(1.0, bs), 67, 60),
        (t4(4, 3.0), dur(1.0, bs), 65, 58), (t4(4, 4.0), dur(1.0, bs), 64, 56),
    ]
    lower += [
        (t4(4, 1.0), dur(1.0, bs), 53, 58), (t4(4, 2.0), dur(1.0, bs), 52, 56),
        (t4(4, 3.0), dur(1.0, bs), 50, 54), (t4(4, 4.0), dur(1.0, bs), 49, 52),
    ]
    
    # Bar 5: Inverted subject entry
    lower += [
        (t4(5, 1.0), dur(0.5, bs), 50, 62), (t4(5, 1.5), dur(0.5, bs), 52, 58),
        (t4(5, 2.0), dur(0.5, bs), 53, 60), (t4(5, 2.5), dur(0.5, bs), 55, 58),
        (t4(5, 3.0), dur(1.0, bs), 57, 62), (t4(5, 4.0), dur(1.0, bs), 45, 56),
    ]
    upper += [
        (t4(5, 1.0), dur(1.0, bs), 62, 56), (t4(5, 2.0), dur(1.0, bs), 65, 60),
        (t4(5, 3.0), dur(1.0, bs), 69, 64), (t4(5, 4.0), dur(1.0, bs), 67, 60),
    ]
    
    # Bar 6: Dominant pedal and trill
    upper += [
        (t4(6, 1.0), dur(1.0, bs), 65, 58),
        (t4(6, 2.0), dur(1.0, bs), 64, 56),
        (t4(6, 3.0), dur(1.4, bs), 61, 62), # C# leading tone trill
        (t4(6, 4.5), dur(0.5, bs), 62, 58),
    ]
    lower += [
        (t4(6, 1.0), dur(1.0, bs), 46, 56), (t4(6, 2.0), dur(1.0, bs), 47, 56),
        (t4(6, 3.0), dur(2.0, bs), 45, 60), # A dominant pedal
    ]
    
    # Bar 7: Cadential resolution to D major (Picardy Third)
    upper += [
        (t4(7, 1.0), dur(4.5, bs), 66, 54), # F#4
        (t4(7, 1.0), dur(4.5, bs), 62, 52), # D4
    ]
    lower += [
        (t4(7, 1.0), dur(4.5, bs), 38, 54), # D2
        (t4(7, 1.0), dur(4.5, bs), 50, 50), # D3
    ]
    
    return {'harpsichord': upper + lower}, "13 - Two-Part Invention in D minor (J.S. Bach Style)", "Dm", (4, 4), 42.0

def compose_canon_02():
    """
    Track 14: Canonic Dialogue in C major (Flute & Gamba / Corelli Style)
    Instruments: Flauto Dolce (Dux) + Viola da Gamba (Comes) + Harpsichord Continuo
    7 bars in 4/4 @ 40 BPM = 42.0 seconds (+ 4.5s tail)
    Strict canon at the octave over a classic Romanesca ground
    """
    bs = 1.5
    flute = []
    gamba = []
    harpsichord = []
    
    # Ground Bass chords in Harpsichord: C - G - Am - Em - F - C - F - G - C
    harpsichord_chords = [
        (t4(1, 1.0), [48, 55, 60, 64]), # C
        (t4(2, 1.0), [47, 55, 59, 62]), # G/B
        (t4(3, 1.0), [45, 52, 57, 60]), # Am
        (t4(4, 1.0), [40, 47, 52, 55]), # Em
        (t4(5, 1.0), [41, 48, 53, 57]), # F
        (t4(6, 1.0), [43, 47, 50, 55]), # G7
        (t4(7, 1.0), [36, 48, 52, 60]), # C
    ]
    for start_t, chord_pitches in harpsichord_chords:
        harpsichord += arpeggio(chord_pitches, start_t, base_vel=48, step_s=0.04, dur_beats=3.5)
        
    # Flute starts subject in Bar 1 (Dux)
    flute_theme = [
        (t4(1, 1.0), dur(1.0, bs), 72, 62), # C5
        (t4(1, 2.0), dur(1.0, bs), 71, 58), # B4
        (t4(1, 3.0), dur(1.0, bs), 69, 58), # A4
        (t4(1, 4.0), dur(1.0, bs), 67, 56), # G4
        (t4(2, 1.0), dur(1.0, bs), 65, 58), # F4
        (t4(2, 2.0), dur(1.0, bs), 64, 56), # E4
        (t4(2, 3.0), dur(1.0, bs), 65, 58), # F4
        (t4(2, 4.0), dur(1.0, bs), 67, 60), # G4
        # Continued flute line
        (t4(3, 1.0), dur(1.0, bs), 69, 62), (t4(3, 2.0), dur(1.0, bs), 72, 64),
        (t4(3, 3.0), dur(1.0, bs), 71, 60), (t4(3, 4.0), dur(1.0, bs), 69, 58),
        (t4(4, 1.0), dur(1.0, bs), 67, 60), (t4(4, 2.0), dur(1.0, bs), 65, 58),
        (t4(4, 3.0), dur(1.0, bs), 64, 56), (t4(4, 4.0), dur(1.0, bs), 62, 54),
        (t4(5, 1.0), dur(1.8, bs), 65, 60), (t4(5, 3.0), dur(1.8, bs), 69, 62),
        (t4(6, 1.0), dur(1.8, bs), 71, 64), (t4(6, 3.0), dur(1.8, bs), 74, 62),
        (t4(7, 1.0), dur(4.5, bs), 72, 54),
    ]
    flute.extend(flute_theme)
    
    # Gamba imitates exactly at the octave lower starting at Bar 2 (Comes!)
    for start_t, dur_t, pitch, vel in flute_theme:
        # shifted by 1 bar (+ 4 beats = 6.0s) and 12 semitones lower
        gamba_start = start_t + dur(4.0, bs)
        if gamba_start <= t4(7, 3.0):
            gamba.append((gamba_start, dur_t, pitch - 12, max(46, vel - 4)))
    # Gamba resolution note in bar 7
    gamba.append((t4(7, 1.0), dur(4.5, bs), 48, 52))
    
    return {'flute': flute, 'gamba': gamba, 'harpsichord': harpsichord}, "14 - Canonic Dialogue in C major (Corelli Style)", "C", (4, 4), 42.0

# ---------------------------------------------------------------------------
# MAIN BATCH ORCHESTRATOR
# ---------------------------------------------------------------------------

COMPOSITIONS = [
    # 1. La Folia
    compose_folia_01,
    compose_folia_02,
    # 2. Passacaglia
    compose_passacaglia_01,
    compose_passacaglia_02,
    # 3. Chaconne
    compose_chaconne_01,
    compose_chaconne_02,
    # 4. Sarabande
    compose_sarabande_01,
    compose_sarabande_02,
    # 5. Lamento
    compose_lamento_01,
    compose_lamento_02,
    # 6. Siciliana
    compose_siciliana_01,
    compose_siciliana_02,
    # 7. Invention & Canon
    compose_invention_01,
    compose_canon_02,
]

def main():
    print("=" * 70)
    print("BAROQUE FACTORY PROTOTYPE: 14 TRACKS (7 STYLES x 2)")
    print(f"Target duration: 40-50s | Tempo: {BPM} BPM | Output: {OUTPUT_DIR}")
    print("=" * 70)
    
    for idx, comp_fn in enumerate(COMPOSITIONS, start=1):
        notes_by_inst, title, key_name, meter, target_dur = comp_fn()
        prefix = f"baroque_{idx:02d}"
        midi_path = os.path.join(OUTPUT_DIR, f"{prefix}.mid")
        wav_path = os.path.join(OUTPUT_DIR, f"{prefix}.wav")
        mp3_path = os.path.join(OUTPUT_DIR, f"{prefix}.mp3")
        
        print(f"\n[{idx:02d}/14] Rendering: {title} ({key_name}, {meter[0]}/{meter[1]})...")
        
        # 1. Export MIDI
        export_baroque_midi(notes_by_inst, title, key_name, meter, midi_path, bpm=BPM)
        print(f"   -> MIDI exported: {os.path.basename(midi_path)}")
        
        # 2. Synthesize High-Resolution 24-bit Audio
        audio_data = synthesize_baroque_audio(notes_by_inst, target_dur)
        sf.write(wav_path, audio_data, SR, subtype='PCM_24')
        actual_sec = len(audio_data) / SR
        print(f"   -> Audio synthesized: {actual_sec:.1f}s")
        
        # 3. Encode to MP3 320k with rich Baroque metadata tags
        style_name = title.split("-")[1].split("in")[0].strip() if "-" in title and "in" in title else "Baroque"
        cmd = [
            FFMPEG_PATH, "-y",
            "-i", wav_path,
            "-codec:a", "libmp3lame",
            "-b:a", "320k",
            "-metadata", f"title={title}",
            "-metadata", "artist=Baroque AI Ensemble",
            "-metadata", "album=Baroque Forms & Variations (40 BPM)",
            "-metadata", f"genre=Baroque ({style_name})",
            "-metadata", f"comment=Authentic algorithmic Baroque loop ({actual_sec:.1f}s)",
            mp3_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0:
            print(f"   -> MP3 320k encoded: {os.path.basename(mp3_path)}")
        else:
            print(f"   -> FFmpeg warning: {res.stderr.decode('utf-8', errors='replace')[:200]}")
            
        # Clean temporary wav to save disk space
        if os.path.exists(wav_path):
            os.remove(wav_path)
            
    print("\n" + "=" * 70)
    print(f"SUCCESS: All 14 Baroque tracks generated in {OUTPUT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
