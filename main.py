# Python port of the C# emulator.cli Program.cs
import argparse
from emulator import Emulator
from roms import ROM_SETS, PACMAN


def parse_args():
    parser = argparse.ArgumentParser(description="Pac-Man / Ms. Pac-Man arcade emulator (Python + pygame)")
    parser.add_argument("rom_path", nargs="?", help="directory containing the ROM files (default: data)")
    parser.add_argument("--rom-set", default=PACMAN, choices=sorted(ROM_SETS),
                        help="game to run: pacman or mspacman (default: pacman)")
    parser.add_argument("--dip-switches", default="dip-switches.json", help="DIP switch settings JSON file")
    parser.add_argument("--skip-checksums", action="store_true", help="allow ROMs with unexpected CRC32s")
    parser.add_argument("--writable-rom", action="store_true", help="allow writes to the ROM area (homebrew)")
    parser.add_argument("--debug", action="store_true", help="show the CPU registers on screen")
    parser.add_argument("--fullscreen", action="store_true", help="run full screen")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    emulator = Emulator(args.rom_path, args.rom_set, args.dip_switches, args.skip_checksums,
                        args.writable_rom, args.debug, args.fullscreen)
    if not emulator.init():
        emulator.free()
    else:
        emulator.run()
