import os
import sys

# Headless: no window, no sound card needed.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
if GAME_DIR not in sys.path:          # core, patterns, app and support live here
    sys.path.insert(0, GAME_DIR)
