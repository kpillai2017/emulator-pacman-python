"""Tiny square-wave synthesiser, so the game needs no sound files.

Each sound is a list of (frequency_hz, duration_s) notes; frequency 0 is silence.
The notes are rendered once into a pygame.mixer.Sound (raw 16-bit samples).
"""
import math
from array import array

import pygame

# name -> list of (frequency, seconds)
SOUND_DEFS = {
    "chomp": [(520, 0.035), (380, 0.035)],
    "power": [(220, 0.05), (330, 0.05), (440, 0.05), (330, 0.05)] * 2,
    "eat_ghost": [(900 - i * 40, 0.015) for i in range(12)] + [(1200, 0.06)],
    "eat_fruit": [(660, 0.05), (880, 0.05), (1320, 0.08)],
    "death": [(800 - i * 30, 0.04) for i in range(20)] + [(0, 0.05), (200, 0.08), (150, 0.12)],
    "start": [(494, 0.12), (988, 0.12), (740, 0.12), (622, 0.12),
              (988, 0.06), (740, 0.18), (622, 0.24), (0, 0.06),
              (523, 0.12), (1046, 0.12), (784, 0.12), (659, 0.12),
              (1046, 0.06), (784, 0.18), (659, 0.24)],
    "extra_life": [(1046, 0.08), (0, 0.04)] * 4,
    "achievement": [(784, 0.07), (988, 0.07), (1175, 0.07), (1568, 0.15)],
    "level_clear": [(523, 0.1), (659, 0.1), (784, 0.1), (1046, 0.25)],
}


def render(notes, volume: float = 0.25) -> pygame.mixer.Sound:
    """Render a note list into a Sound matching the mixer's sample format."""
    freq, size, channels = pygame.mixer.get_init()
    amplitude = int(32767 * volume) if abs(size) == 16 else int(127 * volume)
    samples = array("h")
    for hz, seconds in notes:
        count = int(freq * seconds)
        if hz <= 0:
            samples.extend([0] * (count * channels))
            continue
        period = freq / hz
        for i in range(count):
            # Square wave with a short linear fade-out to avoid clicks.
            value = amplitude if (i % period) < period / 2 else -amplitude
            fade = min(1.0, (count - i) / 64.0)
            value = int(value * fade)
            samples.extend([value] * channels)
    return pygame.mixer.Sound(buffer=samples.tobytes())


def render_all() -> dict:
    """Render every sound in SOUND_DEFS. Requires an initialised mixer."""
    return {name: render(notes) for name, notes in SOUND_DEFS.items()}


def duration(name: str) -> float:
    return math.fsum(seconds for _, seconds in SOUND_DEFS[name])
