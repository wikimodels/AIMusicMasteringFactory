"""
Data Models and Constants for Early Baroque Generator
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple

@dataclass
class NoteEvent:
    step: int
    note: str
    duration: str
    velocity: float
    _p: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'step': self.step,
            'note': self.note,
            'duration': self.duration,
            'velocity': round(max(0.60, min(0.98, self.velocity)), 2)
        }

@dataclass
class TrackConfig:
    index: int
    volume: int
    volume_title: str
    key_code: str
    key_name: str
    instrument: str
    form_code: str
    form_name: str
    steps: int
    meter: str
    bpm: int
    duration_sec: float
    texture_code: str
    texture_name: str
    texture_desc: str
    start_code: str
    start_desc: str
    cadence_code: str
    cadence_desc: str
    filename: str

@dataclass
class ChordDegrees:
    bass_pitch: int
    inner_pitches: List[int]
    soprano_pitches: List[int]
    suspended_pitch: int

# 8 Minor Keys (Strict minor only)
KEY_MODES: Dict[str, Dict[str, Any]] = {
    'Dm': {'root': 2, 'scale': [2, 4, 5, 7, 9, 10, 0], 'leading': 1, 'picardy': 6, 'name': 'D Minor'},
    'Am': {'root': 9, 'scale': [9, 11, 0, 2, 4, 5, 7], 'leading': 8, 'picardy': 1, 'name': 'A Minor'},
    'Gm': {'root': 7, 'scale': [7, 9, 10, 0, 2, 3, 5], 'leading': 6, 'picardy': 11, 'name': 'G Minor'},
    'Cm': {'root': 0, 'scale': [0, 2, 3, 5, 7, 8, 10], 'leading': 11, 'picardy': 4, 'name': 'C Minor'},
    'Em': {'root': 4, 'scale': [4, 6, 7, 9, 11, 0, 2], 'leading': 3, 'picardy': 8, 'name': 'E Minor'},
    'Fsm': {'root': 6, 'scale': [6, 8, 9, 11, 1, 2, 4], 'leading': 5, 'picardy': 10, 'name': 'F# Minor'},
    'Bm': {'root': 11, 'scale': [11, 1, 2, 4, 6, 7, 9], 'leading': 10, 'picardy': 3, 'name': 'B Minor'},
    'D_Dor': {'root': 2, 'scale': [2, 4, 5, 7, 9, 11, 0], 'leading': 1, 'picardy': 6, 'name': 'D Dorian Minor'},
}

NOTE_NAMES = ['C', 'C#', 'D', 'Eb', 'E', 'F', 'F#', 'G', 'Ab', 'A', 'Bb', 'B']

DEGREE_SCALE_INDEX = {
    'i': 0, 'i6': 0, 'I_picardy': 0, 'I_open5': 0,
    'ii_dim': 1, 'ii_dim6': 1, 'ii': 1,
    'III': 2, 'III6': 2,
    'iv': 3, 'iv6': 3,
    'v': 4, 'v6': 4,
    'V': 4, 'V6': 4, 'V7': 4,
    'VI': 5, 'VI6': 5,
    'VII': 6, 'VII6': 6
}

DURATION_BEATS = {
    '16n': 0.25,
    '8n': 0.50,
    '8n.': 0.75,
    '8t': 0.333,
    '4n': 1.00,
    '4n.': 1.50,
    '2n': 2.00,
    '1n': 4.00
}

FORM_PROGRESSIONS_CATALOG: Dict[str, Dict[str, List[str]]] = {
    'Pavane': {
        'Lachrimae': ['i', 'iv', 'V', 'i', 'VII', 'III', 'iv', 'V'],
        'Passamezzo_Antico': ['i', 'VII', 'i', 'V', 'III', 'VII', 'i', 'V'],
        'Ploravit': ['i', 'v', 'VI', 'III', 'iv', 'i6', 'V', 'i'],
        'Grand_Pavane': ['i', 'VII', 'III', 'VI', 'iv', 'ii_dim6', 'V', 'i']
    },
    'Ciaccona': {
        'Descending_Tetrachord': ['i', 'v6', 'iv6', 'V'],
        'Romanesca_Ground': ['III', 'VII', 'i', 'V', 'III', 'VII', 'i', 'V'],
        'Ciaccona_di_Paradiso': ['i', 'VII', 'VI', 'V', 'i', 'III', 'iv', 'V'],
        'Vitali_Passacaglia': ['i', 'iv6', 'V', 'i', 'VI', 'ii_dim6', 'V', 'i']
    },
    'Lamento': {
        'Passus_Duriusculus': ['i', 'V6', 'i6', 'iv6', 'VI', 'ii_dim6', 'V', 'i'],
        'Lamento_d_Arianna': ['i', 'iv', 'V', 'i', 'iv6', 'V', 'i', 'V'],
        'Lamento_Chromaticum': ['i', 'VII', 'VI', 'V', 'iv', 'i6', 'V', 'i']
    },
    'La_Folia': {
        'Folia_Antica': ['i', 'V', 'i', 'VII', 'III', 'VII', 'i', 'V'],
        'Folia_Seconda': ['III', 'VII', 'i', 'V', 'i', 'iv', 'V', 'i']
    },
    'Sarabande': {
        'Sarabande_Grave': ['i', 'V', 'i', 'iv', 'VI', 'ii_dim6', 'V', 'i'],
        'Sarabande_Nobiles': ['i', 'i', 'iv', 'VII', 'III', 'VI', 'V', 'i']
    },
    'Galliard': {
        'Cinque_Pas': ['i', 'VII', 'III', 'VII', 'VI', 'ii_dim6', 'V', 'i'],
        'Galliard_Hemiola': ['i', 'III', 'VII', 'i', 'iv', 'i6', 'V', 'i']
    },
    'Toccata': {
        'Elevazione': ['i', 'i', 'iv6', 'V', 'i', 'VI', 'V', 'i'],
        'Stylus_Phantasticus': ['i', 'iv', 'VII', 'III', 'VI', 'ii_dim', 'V', 'i']
    },
    'Siciliana': {
        'Siciliana_Pastorale': ['i', 'iv', 'ii_dim', 'V', 'III', 'iv', 'V', 'i'],
        'Barcarola': ['i', 'v', 'i', 'iv', 'i6', 'ii_dim6', 'V', 'i']
    },
    'Ricercar': {
        'Ricercar_Cromatico': ['i', 'v', 'i', 'iv', 'VI', 'ii_dim6', 'V', 'i'],
        'Ricercar_Antico': ['i', 'i', 'iv', 'V', 'VI', 'ii_dim6', 'V', 'i']
    },
    'Canzona': {
        'Canzona_Francese': ['i', 'iv', 'V', 'i', 'III', 'VII', 'V', 'i'],
        'Canzona_di_Galli': ['i', 'V', 'VI', 'III', 'iv', 'V', 'i', 'i']
    },
    'La_Monica': {
        'Monica_Tradizionale': ['i', 'VII', 'III', 'VII', 'i', 'iv', 'V', 'i'],
        'Monica_Variata': ['i', 'iv', 'VII', 'III', 'VI', 'V', 'i', 'i']
    },
    'Spagnoletta': {
        'Spagnoletta_Antica': ['i', 'iv', 'VII', 'III', 'VI', 'ii_dim', 'V', 'i'],
        'Spagnoletta_Saltata': ['i', 'VII', 'VI', 'V', 'III', 'iv', 'V', 'i']
    }
}

FORM_TEMPO_RANGES: Dict[str, Tuple[int, int]] = {
    'Lamento': (46, 50),
    'Sarabande': (50, 54),
    'Pavane': (52, 58),
    'Ricercar': (54, 60),
    'Siciliana': (52, 58),
    'Ciaccona': (60, 72),
    'Passacaglia': (58, 68),
    'La_Folia': (62, 72),
    'La_Monica': (64, 74),
    'Spagnoletta': (66, 76),
    'Toccata': (76, 92),
    'Canzona': (80, 94),
    'Galliard': (84, 100),
}

FORM_SCHEMATA: Dict[str, List[str]] = {
    f: list(v.values())[0] for f, v in FORM_PROGRESSIONS_CATALOG.items()
}
FORM_SCHEMATA['Passacaglia'] = FORM_PROGRESSIONS_CATALOG['Ciaccona']['Descending_Tetrachord']
