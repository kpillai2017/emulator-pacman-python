# Pac-Man Emulator (Python + pygame)

A Python emulator for the Pac-Man (and Ms. Pac-Man) arcade hardware: Zilog Z80 CPU, tile and
sprite video hardware, Namco WSG3 sound, DIP switches and controls.

It is a port of the C# [pac-man-emulator](../pac-man-emulator) and uses the same modular layout and
the same, unchanged `core/` framework as [emulator-spinvaders-python](../emulator-spinvaders-python).

---

## Game Instructions

**Starting a game:**

| Mode | Steps |
|---|---|
| 1 player | Press `5` (or `6`) to insert a coin, then press `1`. |
| 2 players | Press `5` twice (CREDIT shows `2`), then press `2`. |

The help panel on the right of the window shows these steps. When enough credits are inserted (and
no game is running) the matching section is highlighted with a blinking `<< READY` marker.

**Controls** (same keys as the C# version):

| Action | Key |
|---|---|
| Insert coin (chute 1 / 2) | `5` / `6` |
| 1 player start / 2 player start | `1` / `2` |
| Move (player 1) | Arrow keys |
| Move (player 2, cocktail mode) | `W` `A` `S` `D` |
| Service credit | `3` |
| Rack advance | `7` |
| Board test (toggle) | `8` |
| Pause | `P` |
| Mute sound | `M` |
| Quit | `Escape` |

---

## Setup Instructions

1. **Install Python 3.9+** (tested with Python 3.9 and 3.12).
2. **(Optional) Create a virtual environment**
   ```sh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Install dependencies** (just [pygame](https://www.pygame.org)):
   ```sh
   pip install -r requirements.txt
   ```
4. **Add the ROMs**: the ROMs are copyrighted and not included. Copy them all into `data/`.
   Both games share one folder: their common files are identical and their tiles/sprites have
   different names, so nothing clashes. The file names and CRC32s are listed in
   [`data/README.md`](data/README.md). `.gitignore` keeps them out of the repository.
5. **Run** (from this folder, so `fonts/` and `dip-switches.json` are found):
   ```sh
   python main.py --rom-set pacman         # Pac-Man (the default)
   python main.py --rom-set mspacman       # Ms. Pac-Man
   python main.py /path/to/roms --rom-set mspacman   # ROMs somewhere else
   ```

**Command line options** (as in the C# CLI):

| Option | Meaning |
|---|---|
| `rom_path` | Folder with the ROM files (default `data`) |
| `--rom-set pacman\|mspacman` | Game to run (default `pacman`) |
| `--dip-switches FILE` | DIP switch settings (default `dip-switches.json`) |
| `--skip-checksums` | Warn instead of failing on unexpected CRC32s (e.g. homebrew ROMs) |
| `--writable-rom` | Allow writes to the ROM area (some homebrew needs this) |
| `--debug` | Show the CPU registers on screen |
| `--fullscreen` | Run full screen |

**Game settings** (coins per game, lives, bonus life score, difficulty, ghost names, upright or
cocktail cabinet) are set in [`dip-switches.json`](dip-switches.json), the same file format as the
C# version (`//` comments allowed).

---

## Project Structure

Same structure as `emulator-spinvaders-python`. One module per hardware part, all driven by
`emulator.py`.

| File | Purpose |
|---|---|
| `main.py` | Entry point and command line options |
| `emulator.py` | `Emulator(Game)`: wires the parts together and runs one frame per tick |
| `cpu.py` | Zilog Z80 CPU (all documented and undocumented opcodes, IM 0/1/2, NMI) |
| `memory.py` | Pac-Man memory map, Ms. Pac-Man aux board decryption and patching |
| `iohandler.py` | Controls → input ports, memory mapped I/O latches, keyboard mapping |
| `video.py` | Colour/palette PROMs, tiles, sprites, screen flip, help panel |
| `soundfx.py` | Namco WSG3 3-voice waveform synthesis, streamed to the pygame mixer |
| `roms.py` | ROM set definitions, loading and CRC32 checks |
| `dipswitches.py` | DIP switch settings and JSON loader |
| `util.py` | Bit constants and hex helpers (same as Space Invaders) |
| `core/` | The shared game framework, **copied unchanged** from the Space Invaders emulator |
| `fonts/blitz.fon` | On-screen text font (same as Space Invaders) |
| `tests/` | CPU, video, sound and end-to-end tests (see below) |

Mapping from the C# project:

| C# | Python |
|---|---|
| `z80/` (CPU, opcodes, flags) | `cpu.py` |
| `Hardware/PacManPCB.cs` (memory map, main loop) | `memory.py`, `iohandler.py`, `emulator.py` |
| `Hardware/MsPacManAuxBoard.cs` | `memory.py` |
| `Hardware/VideoHardware.cs`, `Graphics/*Renderer.cs` | `video.py` |
| `Hardware/AudioHardware.cs`, audio part of `Platform.cs` | `soundfx.py` |
| `Hardware/Buttons.cs`, keyboard part of `Platform.cs` | `iohandler.py` |
| `Hardware/DIPSwitches.cs`, `DIPSwitchFlags/`, `dip-switches.json` | `dipswitches.py`, `dip-switches.json` |
| `ROMs/` | `roms.py` |
| `Platform/` (SDL window, audio, input) | `core/` (pygame) |

Not ported: the interactive console debugger, save states and reverse stepping (C# `--debug`
features), and the Xbox/UWP build.

---

## How the Emulator Works

1. **Initialisation**: loads and verifies the ROM set and DIP switches, opens an 860x640 window, and
   initialises the CPU, memory, sound and video.
2. **Main loop** (60 times a second, from `core.Game.run`):
   - `Io.update()` samples the keyboard into the active-low `IN0`/`IN1` ports.
   - The CPU runs 51,200 T-states (3.072 MHz / 60). Any overshoot is carried over to the next frame.
   - `SoundFX` generates 1/60 s of WSG3 audio and queues it on a mixer channel.
   - If the interrupt latch (`0x5000`) is set, the VBLANK interrupt line is raised. Like the real
     hardware it stays raised until the CPU accepts it, so an interrupt that arrives while
     interrupts are disabled (`DI`, or the instruction just after `EI`) is delayed, not lost.
     Writing `0` to `0x5000` clears it. The game uses interrupt mode 2 with the vector low byte
     set by `OUT (0),A`.
   - `Video` renders the screen and the help panel.
3. **CPU** (`cpu.py`): CPython is too slow for a classic `if/elif` interpreter at 3 MHz, so every opcode
   of every prefix (main, `CB`, `ED`, `DD`, `FD`, `DDCB`, `FDCB`) is generated at start-up from
   readable templates into a small specialised closure in a 256-entry dispatch table. Flags use
   precomputed lookup tables. On Python 3.12 this gives roughly 50-60 MHz effective, so the
   game uses only a small part of each frame.
4. **Memory** (`memory.py`): one 64 KB `bytearray` that the CPU reads directly. The input ports
   (`0x5000`-`0x50BF`) are refreshed into it once per frame. Writes go through `Memory.write()`:
   RAM is stored, ROM is protected, and `0x5000`-`0x50FF` is routed to `Io.write_register()`.
   On Ms. Pac-Man, writing `1` to `0x5002` maps in the decrypted aux board ROMs (`0x0000`-`0x3FFF` patched,
   `0x8000`-`0x9FFF` extra code).
5. **Video** (`video.py`): 28x36 tiles of 8x8 pixels plus 8 sprites of 16x16 pixels. Each pixel (0-3) is looked up in
   one of 32 four-colour palettes (the low 5 bits of the colour byte; bit 6 is the Ms. Pac-Man
   tunnel flag) to give a colour index 0-15, which the 32-entry colour PROM turns into RGB. Only tiles whose number or palette changed are redrawn
   into a background surface. Sprites are blitted on top, the 16 pixel side columns are masked, and
   the 256x288 frame is scaled 2x. Cocktail mode screen flipping is supported.
6. **Sound** (`soundfx.py`): 3 voices, each a 32-step 4-bit waveform from the sound PROMs with a 20-bit
   (voice 1) or 16-bit frequency accumulator and a 4-bit volume. Samples are generated directly at
   the mixer rate, using the same point sampling as the C# downsampler.

---

## Tests

```sh
python -m unittest discover -s tests -t .   # unit and end-to-end tests (a few seconds)
python -m tests.zex 4 daa neg               # selected Z80 exerciser tests (by index or label)
python -m tests.zex --list                  # list the 67 exerciser tests
python -m tests.zex                         # full ZEXDOC (documented flags): slow (about an hour)
python -m tests.zex --all-flags             # full ZEXALL (also undocumented X/Y flags)
```

- `tests/test_video.py`: renders the boot, attract and maze screens (normal and flipped, with and
  without a sprite) from the C# test VRAM dumps and compares them pixel for pixel with the C#
  reference images in `tests/reference/`. No ROM data is included in the repository, so these tests
  read the Pac-Man graphics ROMs from `data/` (or the folder in `PACMAN_ROM_DIR`) and are skipped
  when they are not there.
- `tests/test_sound.py`: compares the fast WSG3 generator sample for sample with a literal port of the
  C# `AudioHardware.Tick()` loop and downsampler.
- `tests/test_smoke.py`: runs the complete emulator headless on a small hand-assembled Z80 program
  that uses the Pac-Man hardware (IM 2 vector via `OUT`, `LDIR`, sound registers, interrupt latch,
  coin input). It also checks the Ms. Pac-Man aux board decryption and mapping.
- `tests/test_roms.py`: checks the missing-ROM error lists every missing file and, when the folder
  holds another game's files, suggests the matching `--rom-set`.
- `tests/test_interrupts.py`: checks that the CPU refuses interrupts while disabled and for one
  instruction after `EI`, that `EI` + `HALT` wakes up, and that a VBLANK raised during `DI` is
  delivered later (and cleared by writing `0` to `0x5000`).
- `tests/zex.py`: the ZEXDOC/ZEXALL Z80 instruction exercisers (port of the C# `CPUIntegrationTest`),
  with a CP/M BDOS stub for output.

`tests/data/` holds the VRAM dumps from the C# test project and the ZEXDOC/ZEXALL programs (no
game ROMs).

---

## Differences from the C# Version

The behaviour follows the C# version, with these deliberate fixes:

- **Interrupts**: the VBLANK interrupt is a held line (as in MAME) and `EI` enables interrupts only
  after the next instruction, as on a real Z80. The C# version drops a VBLANK that arrives while
  interrupts are disabled.
- **Palettes**: the palette number is masked to 5 bits (`& 0x1F`). This makes the Ms. Pac-Man
  "palette 93 → 63" special case unnecessary: 93 is the tunnel flag (`0x40`) plus palette 29.
- **Input ports**: every address in `0x5000`-`0x503F` reads `IN0` (the port is mirrored).
- **Aux board**: the decrypted Ms. Pac-Man ROM covers exactly `0x0000`-`0x3FFF`; the C# `<= 0x4000`
  off-by-one is not copied.
- **Z80 tests**: all 67 ZEX tests run (the C# suite skips `ld8rrx`). ZEXDOC and ZEXALL both pass.
- **DIP switches**: the lives comment in `dip-switches.json` is corrected.
- **`82s126.3m`**: loaded and CRC-checked to keep the ROM set complete, but not used (it is a
  timing PROM, not a waveform).

---

## License
This project is for educational purposes. Pac-Man and Ms. Pac-Man are © Bandai Namco. You must
legally own the original ROMs to use them with this emulator.
