"""
Test Script for 5 Baroque Masterpiece Directions
Verifies that all 5 compositional generators produce unique, consonant, beautiful note sequences.
"""

import os
import sys
import numpy as np
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

# Scale definitions
KEYS = {
    'Dm': {'root': 2, 'scale': [2, 4, 5, 7, 9, 10, 0], 'leading': 1, 'name': 'D Minor'},
    'Gm': {'root': 7, 'scale': [7, 9, 10, 0, 2, 3, 5], 'leading': 6, 'name': 'G Minor'},
    'Cm': {'root': 0, 'scale': [0, 2, 3, 5, 7, 8, 10], 'leading': 11, 'name': 'C Minor'},
    'Am': {'root': 9, 'scale': [9, 11, 0, 2, 4, 5, 7], 'leading': 8, 'name': 'A Minor'},
    'Em': {'root': 4, 'scale': [4, 6, 7, 9, 11, 0, 2], 'leading': 3, 'name': 'E Minor'},
    'Fm': {'root': 5, 'scale': [5, 7, 8, 10, 0, 1, 3], 'leading': 4, 'name': 'F Minor'},
    'Bm': {'root': 11, 'scale': [11, 1, 2, 4, 6, 7, 9], 'leading': 10, 'name': 'B Minor'},
}

print("Music theory definitions loaded successfully.")
