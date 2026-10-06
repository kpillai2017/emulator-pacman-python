"""Pattern-Man: Robert Nystrom's Game Programming Patterns, one by one, in a Pac-Man clone.

Run from anywhere:   python main.py            (see README.md for options)
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# Everything (the core engine, patterns, app, support) lives next to this file,
# so the game runs from any working directory.
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from patterns.p05_singleton import Settings  # noqa: E402
from app.game import PatternManGame          # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Pattern-Man: game programming patterns in Pac-Man")
    p.add_argument("--scale", type=int, default=1, help="window scale factor (default 1)")
    p.add_argument("--fullscreen", action="store_true", help="run full screen")
    p.add_argument("--level", type=int, default=1, help="level to start a new game on")
    p.add_argument("--invincible", action="store_true", help="ghosts can't catch Pac-Man")
    p.add_argument("--log-audio", action="store_true",
                   help="wrap audio in the LoggedAudio decorator (Service Locator, p15)")
    p.add_argument("--debug", action="store_true", help="start with the debug overlay on")
    p.add_argument("--seed", type=int, default=None, help="random seed (frightened ghosts)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    settings = Settings.instance()
    settings.start_level = max(1, args.level)
    settings.invincible = args.invincible
    settings.log_audio = args.log_audio
    settings.show_debug = args.debug

    game = PatternManGame(scale=max(1, args.scale), fullscreen=args.fullscreen, seed=args.seed)
    if not game.init():
        print("Failed to initialise the game", file=sys.stderr)
        return 1
    game.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
