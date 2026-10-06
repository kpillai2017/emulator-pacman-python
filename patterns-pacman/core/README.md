# core: the small pygame engine

A thin wrapper around pygame: `Game` (the base class with a simple game loop), `Graphics`
(window and drawing), `Input` (keyboard and mouse state), `Audio` / `Music` / `Sound`, `Image`,
and two font classes.

It is an **unchanged copy** of the `core/` package from the
[emulator-pacman-python](https://github.com/kpillai2017/emulator-pacman-python) project, where it
also drives a Pac-Man arcade emulator. The only addition is an empty `__init__.py`, which makes it a
regular Python package. It is vendored here so that this repository is self-contained:
`git clone` plus `pip install -r requirements.txt` is all you need.

Pattern-Man uses it like this:

| Engine piece | Used by | For |
|---|---|---|
| `game.Game` | `patterns/p08_game_loop.py` | `FixedTimestepGame` subclasses it and replaces only `run()`: the book's "Play catch up" loop instead of the engine's "Take a little nap" loop. |
| `graphics.Graphics` | via `Game` | the window surface (`get_backbuffer`) and `flip` |
| `input.Input` | via `Game` → `patterns/p01_command.py` | which keys are down/hit; the Command pattern decides what they mean |
| `audio.Audio` | via `Game` | starting the mixer (sounds are played by `patterns/p14_event_queue.py`) |
| `outline_font.OutlineFont` | `support/text.py` | all on-screen text |

`image.py`, `raster_font.py`, `sound.py` and `music.py` are not used by the game. They are kept
so that the engine stays complete and identical to the original.

**Please don't edit these files.** Keeping the engine unchanged is part of the lesson: every
pattern is built *on top of* a simple engine, not by modifying it.
