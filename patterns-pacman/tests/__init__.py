import os
import sys

# Headless: no window, no sound card needed.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

HERE = os.path.dirname(os.path.abspath(__file__))
GAME_DIR = os.path.dirname(HERE)
for path in (os.path.dirname(GAME_DIR), GAME_DIR):   # ../core and our packages
    if path not in sys.path:
        sys.path.insert(0, path)
