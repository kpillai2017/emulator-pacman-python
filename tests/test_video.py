# Video hardware tests: render known video RAM dumps and compare them pixel for pixel
# with the reference images produced by the C# emulator.
# Port of pac-man-emulator/emulator.tests/Tests/Hardware/VideoHardwareTests.cs
#
#   python -m unittest tests.test_video
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402
from memory import Memory  # noqa: E402
from iohandler import Io  # noqa: E402
from video import Video, decode_colors  # noqa: E402
import roms  # noqa: E402
from roms import PACMAN  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
# The graphics ROMs are copyrighted, so they are not shipped with the tests: they are read
# from the same folder the emulator uses (override with PACMAN_ROM_DIR).
ROM_DIR = os.environ.get("PACMAN_ROM_DIR", os.path.join(os.path.dirname(HERE), "data"))


def _read(*parts):
    with open(os.path.join(HERE, *parts), "rb") as f:
        return f.read()


def _read_rom(rom):
    """The ROM's bytes from ROM_DIR, or None if it is missing or its CRC32 differs."""
    path = os.path.join(ROM_DIR, rom.file_name)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        data = f.read()
    return data if roms.crc32_hex(data) == rom.crc32.upper() else None


class TestRomData:
    """Stand-in for roms.RomData holding just the Pac-Man graphics ROMs."""
    rom_set = PACMAN
    color = _read_rom(roms.PAC_MAN_COLOR)
    palette = _read_rom(roms.PAC_MAN_PALETTE)
    tile = _read_rom(roms.PAC_MAN_TILE)
    sprite = _read_rom(roms.PAC_MAN_SPRITE)


HAVE_ROMS = None not in (TestRomData.color, TestRomData.palette, TestRomData.tile, TestRomData.sprite)
SKIP_REASON = (f"Pac-Man graphics ROMs ({roms.PAC_MAN_COLOR.file_name}, {roms.PAC_MAN_PALETTE.file_name}, "
               f"{roms.PAC_MAN_TILE.file_name}, {roms.PAC_MAN_SPRITE.file_name}) not found in {ROM_DIR}")


def make_video(vram_file):
    memory = Memory()
    memory.memoryPtr[0x4000:0x4800] = _read("data", vram_file)
    video = Video()
    video.init_hardware(memory, Io(), TestRomData())
    return video, memory


def surface_rgb(surface):
    return pygame.image.tostring(surface, "RGB")


def reference_rgb(bmp):
    return surface_rgb(pygame.image.load(os.path.join(HERE, "reference", bmp)))


@unittest.skipUnless(HAVE_ROMS, SKIP_REASON)
class VideoHardwareTests(unittest.TestCase):
    def test_colors_decode(self):
        colors = decode_colors(TestRomData.color)
        self.assertEqual(colors[0], (0, 0, 0))
        self.assertEqual(colors[1], (255, 0, 0))     # 0x07: all red resistors
        self.assertEqual(colors[15], (222, 222, 255))  # 0xF6

    def _check_screen(self, vram, bmp, flip, sprite=None, coords=None):
        video, memory = make_video(vram)
        sprite_coords = bytearray(16)
        if sprite is not None:
            memory.memoryPtr[0x4FF0] = sprite[0]
            memory.memoryPtr[0x4FF1] = sprite[1]
            sprite_coords[0:2] = bytes(coords)
        frame = video.render_frame(sprite_coords, flip)
        self.assertEqual(frame.get_size(), (256, 288))
        expected = reference_rgb(bmp)
        actual = surface_rgb(frame)
        if actual != expected:
            diff = sum(1 for i in range(0, len(actual), 3) if actual[i:i + 3] != expected[i:i + 3])
            self.fail(f"{bmp}: {diff} pixels differ")

    def test_boot_screen(self):
        self._check_screen("boot-screen.vram", "render-boot-screen.bmp", False)

    def test_attract_screen(self):
        self._check_screen("attract-screen.vram", "render-attract-screen.bmp", False)

    def test_maze(self):
        self._check_screen("maze-1.vram", "render-maze-1.bmp", False)

    def test_boot_screen_flipped(self):
        self._check_screen("boot-screen.vram", "render-boot-screen-flipped.bmp", True)

    def test_attract_screen_flipped(self):
        self._check_screen("attract-screen.vram", "render-attract-screen-flipped.bmp", True)

    def test_maze_flipped(self):
        self._check_screen("maze-1.vram", "render-maze-1-flipped.bmp", True)

    def test_maze_with_sprite(self):
        # Pac-Man facing left (sprite 46), no flip, palette 9, at x=50 y=20
        self._check_screen("maze-1.vram", "render-maze-1-with-sprites.bmp", False, ((46 << 2) | 0x00, 9), (50, 20))

    def test_maze_with_sprite_flipped(self):
        # Same sprite with flip X, flipped screen, at x=220 y=252
        self._check_screen("maze-1.vram", "render-maze-1-with-sprites-flipped.bmp", True,
                           ((46 << 2) | 0x02, 9), (220, 252))

    def test_incremental_redraw_matches_full_redraw(self):
        """Changing video RAM between frames must give the same image as a fresh render."""
        video, memory = make_video("maze-1.vram")
        video.render_frame(bytearray(16), False)
        memory.memoryPtr[0x4000:0x4800] = _read("data", "attract-screen.vram")
        frame = video.render_frame(bytearray(16), False)
        self.assertEqual(surface_rgb(frame), reference_rgb("render-attract-screen.bmp"))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(HAVE_ROMS, SKIP_REASON)
class PaletteMaskTests(unittest.TestCase):
    def test_only_low_five_palette_bits_are_used(self):
        """Bits 5-7 of a palette byte (e.g. Ms. Pac-Man's tunnel flag 0x40) don't change colours."""
        video, memory = make_video("maze-1.vram")
        expected = surface_rgb(video.render_frame(bytes(16), False))
        mem = memory.memoryPtr
        for a in range(0x4400, 0x4800):
            mem[a] |= 0xE0
        video.invalidate()
        self.assertEqual(surface_rgb(video.render_frame(bytes(16), False)), expected)
