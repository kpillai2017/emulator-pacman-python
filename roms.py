# Python port of the C# ROM definitions and loader (pac-man-emulator/emulator/ROMs)
import os
import zlib
from collections import namedtuple

ROMFile = namedtuple("ROMFile", "file_name size crc32 description")

PAC_MAN_CODE_1 = ROMFile("pacman.6e", 4096, "C1E6AB10", "Code 1 (4KB)")
PAC_MAN_CODE_2 = ROMFile("pacman.6f", 4096, "1A6FB2D4", "Code 2 (4KB)")
PAC_MAN_CODE_3 = ROMFile("pacman.6h", 4096, "BCDD1BEB", "Code 3 (4KB)")
PAC_MAN_CODE_4 = ROMFile("pacman.6j", 4096, "817D94E3", "Code 4 (4KB)")
PAC_MAN_COLOR = ROMFile("82s123.7f", 32, "2FC650BD", "Color (32B) (32 one-byte colors)")
PAC_MAN_PALETTE = ROMFile("82s126.4a", 256, "3EB3A8E4", "Palette (256B) (64 four-byte palettes)")
PAC_MAN_TILE = ROMFile("pacman.5e", 4096, "0C944964", "Tile (4KB) (256 8x8 pixel tile images)")
PAC_MAN_SPRITE = ROMFile("pacman.5f", 4096, "958FEDF9", "Sprite (4KB) (64 16x16 sprite images)")
PAC_MAN_SOUND_1 = ROMFile("82s126.1m", 256, "A9CC86BF", "Sound 1 (256B) (8 waveforms)")
PAC_MAN_SOUND_2 = ROMFile("82s126.3m", 256, "77245B66", "Sound 2 (256B) (8 waveforms)")
MS_PAC_MAN_TILE = ROMFile("5e", 4096, "5C281D01", "Tile (4KB) (256 8x8 pixel tile images)")
MS_PAC_MAN_SPRITE = ROMFile("5f", 4096, "615AF909", "Sprite (4KB) (64 16x16 sprite images)")
MS_PAC_MAN_AUX_U5 = ROMFile("u5", 2048, "F45FBBCD", "Aux Board ROM (2KB)")
MS_PAC_MAN_AUX_U6 = ROMFile("u6", 4096, "A90E7000", "Aux Board ROM (4KB)")
MS_PAC_MAN_AUX_U7 = ROMFile("u7", 4096, "C82CD714", "Aux Board ROM (4KB)")

PACMAN = "pacman"
MSPACMAN = "mspacman"

# Each ROM set lists its files plus which file plays each role, so the rest of the
# emulator never needs to know the per-set file names.
ROM_SETS = {
    PACMAN: {
        "title": "Pac-Man",
        "files": [PAC_MAN_CODE_1, PAC_MAN_CODE_2, PAC_MAN_CODE_3, PAC_MAN_CODE_4, PAC_MAN_COLOR,
                  PAC_MAN_PALETTE, PAC_MAN_TILE, PAC_MAN_SPRITE, PAC_MAN_SOUND_1, PAC_MAN_SOUND_2],
        "tile": PAC_MAN_TILE, "sprite": PAC_MAN_SPRITE,
    },
    MSPACMAN: {
        "title": "Ms. Pac-Man",
        "files": [PAC_MAN_CODE_1, PAC_MAN_CODE_2, PAC_MAN_CODE_3, PAC_MAN_CODE_4, PAC_MAN_COLOR,
                  PAC_MAN_PALETTE, MS_PAC_MAN_TILE, MS_PAC_MAN_SPRITE, PAC_MAN_SOUND_1, PAC_MAN_SOUND_2,
                  MS_PAC_MAN_AUX_U5, MS_PAC_MAN_AUX_U6, MS_PAC_MAN_AUX_U7],
        "tile": MS_PAC_MAN_TILE, "sprite": MS_PAC_MAN_SPRITE,
    },
}


class RomError(Exception):
    pass


class RomData:
    """The loaded ROM images of one ROM set, accessed by role (code, tile, ...)."""
    def __init__(self, rom_set, files):
        self.rom_set = rom_set
        self.files = files          # file name -> bytes

    def get(self, rom_file):
        return self.files[rom_file.file_name]

    @property
    def code(self):
        return b"".join(self.get(r) for r in (PAC_MAN_CODE_1, PAC_MAN_CODE_2, PAC_MAN_CODE_3, PAC_MAN_CODE_4))

    @property
    def color(self):
        return self.get(PAC_MAN_COLOR)

    @property
    def palette(self):
        return self.get(PAC_MAN_PALETTE)

    @property
    def tile(self):
        return self.get(ROM_SETS[self.rom_set]["tile"])

    @property
    def sprite(self):
        return self.get(ROM_SETS[self.rom_set]["sprite"])

    @property
    def sound(self):
        return self.get(PAC_MAN_SOUND_1) + self.get(PAC_MAN_SOUND_2)


def crc32_hex(data: bytes) -> str:
    return f"{zlib.crc32(data) & 0xFFFFFFFF:08X}"


def _missing_files(rom_set: str, directory: str) -> list:
    """The ROMFiles of rom_set that are not present in directory."""
    return [rom for rom in ROM_SETS[rom_set]["files"]
            if not os.path.isfile(os.path.join(directory, rom.file_name))]


def _other_set_hint(rom_set: str, directory: str):
    """Suggest another --rom-set when directory holds files unique to that set.

    Only files that are *not* shared with the requested set count as evidence, so
    the common code/PROM files never trigger a hint on their own.
    """
    wanted = {rom.file_name for rom in ROM_SETS[rom_set]["files"]}
    hints = []
    for other, info in ROM_SETS.items():
        if other == rom_set:
            continue
        unique = [rom.file_name for rom in info["files"] if rom.file_name not in wanted]
        found = [name for name in unique if os.path.isfile(os.path.join(directory, name))]
        if not found:
            continue
        if not _missing_files(other, directory):
            hints.append(f"The folder contains the complete {info['title']} ROM set: "
                         f"did you mean --rom-set {other}?")
        else:
            hints.append(f"The folder contains {info['title']} files ({', '.join(found)}): "
                         f"to run {info['title']} use --rom-set {other}.")
    return "\n".join(hints) or None


def load_rom_set(rom_set: str, directory: str, enforce_checksums: bool = True) -> RomData:
    """Load and verify every file of rom_set from directory (raises RomError)."""
    if rom_set not in ROM_SETS:
        raise RomError(f"Unknown ROM set '{rom_set}'. Expected one of: {', '.join(ROM_SETS)}")
    missing = _missing_files(rom_set, directory)
    if missing:
        rom = missing[0]
        message = (f"Could not locate the '{rom.description}' ROM file '{rom.file_name}' "
                   f"with CRC32 of '{rom.crc32}' at the location: {os.path.join(directory, rom.file_name)}")
        if len(missing) > 1:
            message += f"\nAll missing {ROM_SETS[rom_set]['title']} files: " + \
                       ", ".join(r.file_name for r in missing)
        hint = _other_set_hint(rom_set, directory)
        if hint:
            message += "\n" + hint
        raise RomError(message)
    files = {}
    for rom in ROM_SETS[rom_set]["files"]:
        path = os.path.join(directory, rom.file_name)
        with open(path, "rb") as f:
            data = f.read()
        if len(data) != rom.size:
            raise RomError(f"The file size for '{rom.description}' ROM file '{rom.file_name}' at {path} "
                           f"was {len(data)} bytes, but we are expecting {rom.size} bytes.")
        checksum = crc32_hex(data)
        if checksum != rom.crc32:
            message = (f"The CRC32 checksum for '{rom.description}' ROM file '{rom.file_name}' at {path} "
                       f"was calculated as '{checksum}', but we are expecting '{rom.crc32}'.")
            if enforce_checksums:
                raise RomError(message + " (use --skip-checksums to ignore)")
            print(f"[WARNING] {message}")
        files[rom.file_name] = data
    return RomData(rom_set, files)
