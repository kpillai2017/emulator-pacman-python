# End-to-end test of the whole emulator (no real game ROMs needed).
#
# A tiny hand-assembled Z80 "homebrew" program is placed in the four code ROMs. It
# uses the Pac-Man hardware the same way the real game does: interrupt mode 2 with
# the vector set through OUT (0),A, LDIR to fill video RAM, the WSG sound registers
# and the interrupt enable latch. Its VBLANK interrupt handler counts frames and
# copies IN0 to RAM, so the test can check timing, interrupts and input.
#
#   python -m unittest tests.test_smoke
import os
import random
import sys
import tempfile
import time
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pygame  # noqa: E402
import roms  # noqa: E402
from emulator import Emulator, CYCLES_PER_FRAME  # noqa: E402
from memory import Memory  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

PROGRAM = bytes([
    0xF3,                    # DI
    0x31, 0xC0, 0x4F,        # LD SP,0x4FC0
    0xED, 0x5E,              # IM 2
    0x3E, 0x3F, 0xED, 0x47,  # LD A,0x3F ; LD I,A
    0x3E, 0xFC, 0xD3, 0x00,  # LD A,0xFC ; OUT (0),A    -> vector at 0x3FFC
    0x21, 0x00, 0x40, 0x11, 0x01, 0x40, 0x01, 0xFF, 0x03, 0x36, 0x40, 0xED, 0xB0,  # fill tiles with 0x40
    0x21, 0x00, 0x44, 0x11, 0x01, 0x44, 0x01, 0xFF, 0x03, 0x36, 0x01, 0xED, 0xB0,  # fill palettes with 1
    0x3E, 0x01, 0x32, 0x01, 0x50,  # LD (0x5001),A  sound enable
    0x3E, 0x0F, 0x32, 0x55, 0x50,  # LD (0x5055),A  voice 1 volume 15
    0x3E, 0x08, 0x32, 0x53, 0x50,  # LD (0x5053),A  voice 1 frequency
    0x3E, 0x01, 0x32, 0x00, 0x50,  # LD (0x5000),A  interrupt enable
    0xFB,                    # EI
    0x18, 0xFE,              # loop: JR loop
])
ISR = bytes([                # at 0x1000
    0xF5,                    # PUSH AF
    0x3A, 0x00, 0x4C, 0x3C, 0x32, 0x00, 0x4C,  # frame counter at 0x4C00
    0x3A, 0x00, 0x50, 0x32, 0x01, 0x4C,        # copy IN0 to 0x4C01
    0xF1, 0xFB, 0xED, 0x4D,  # POP AF ; EI ; RETI
])


def write_rom_set(directory, rom_set=roms.PACMAN):
    code = bytearray(0x4000)
    code[0:len(PROGRAM)] = PROGRAM
    code[0x1000:0x1000 + len(ISR)] = ISR
    code[0x3FFC:0x3FFE] = b"\x00\x10"
    rng = random.Random(7)
    contents = {
        roms.PAC_MAN_CODE_1: code[0x0000:0x1000], roms.PAC_MAN_CODE_2: code[0x1000:0x2000],
        roms.PAC_MAN_CODE_3: code[0x2000:0x3000], roms.PAC_MAN_CODE_4: code[0x3000:0x4000],
    }
    # Graphics/colour/sound PROMs are random: no copyrighted ROM data is needed.
    for rom in roms.ROM_SETS[rom_set]["files"]:
        data = contents.get(rom) or bytes(rng.randrange(256) for _ in range(rom.size))
        with open(os.path.join(directory, rom.file_name), "wb") as f:
            f.write(bytes(data))


class SmokeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="tmp_rovo_")
        write_rom_set(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(ROOT)      # fonts/ and dip-switches.json are relative to the project

    def tearDown(self):
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def test_checksums_enforced(self):
        with self.assertRaises(roms.RomError):
            roms.load_rom_set(roms.PACMAN, self._tmp.name, enforce_checksums=True)

    def test_runs_frames_with_interrupts_input_video_and_sound(self):
        emu = Emulator(self._tmp.name, skip_checksums=True)
        self.assertTrue(emu.init())
        try:
            mem = emu.get_memory().get_memory_ptr()
            frames = 120
            start = time.time()
            for frame in range(frames):
                if frame == 60:
                    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_5, mod=0, unicode="5"))
                emu.get_input().update()
                emu.update()
            elapsed = time.time() - start

            # One VBLANK interrupt per frame. The interrupt raised at the end of the last
            # frame has been accepted but its handler only runs during the next frame.
            self.assertEqual(mem[0x4C00], frames - 1)
            self.assertEqual(emu.get_cpu().PC, 0x1000)
            self.assertTrue(all(b == 0x40 for b in mem[0x4000:0x4400]))
            self.assertTrue(all(b == 0x01 for b in mem[0x4400:0x4800]))
            # Coin 1 (key 5) is IN0 bit 5, active low
            self.assertEqual(mem[0x4C01], 0xFF & ~0x20)
            self.assertTrue(emu.get_io().sound_enabled)
            self.assertNotEqual(set(emu.get_soundfx().generate_frame()), {0})
            self.assertEqual(emu.get_cpu().im, 2)
            self.assertLess(abs(emu.cycle_overshoot), 30)
            print(f"\n  {frames} frames in {elapsed:.2f}s = {frames / elapsed:.0f} FPS "
                  f"(CPU {CYCLES_PER_FRAME} T-states/frame, real time needs 60)")
        finally:
            emu.free()


class MsPacManAuxBoardTests(unittest.TestCase):
    def test_decryption_is_a_permutation(self):
        self.assertEqual(sorted(Memory._decrypt_data(i) for i in range(256)), list(range(256)))
        self.assertEqual(sorted(Memory._decrypt_address1(i) for i in range(0x1000)), list(range(0x1000)))
        self.assertEqual(sorted(Memory._decrypt_address2(i) for i in range(0x800)), list(range(0x800)))

    def test_aux_board_maps_in_on_write_to_5002(self):
        with tempfile.TemporaryDirectory(prefix="tmp_rovo_") as tmp:
            write_rom_set(tmp, roms.MSPACMAN)
            rom_data = roms.load_rom_set(roms.MSPACMAN, tmp, enforce_checksums=False)
        memory = Memory()
        memory.init(rom_data)
        written = []
        memory.io_write = lambda a, v: (written.append((a, v)), memory.enable_aux_board() if a == 0x5002 else None)
        mem = memory.get_memory_ptr()
        self.assertEqual(bytes(mem[0:0x4000]), rom_data.code)
        memory.write(0x5002, 1)
        aux = memory.aux_roms
        self.assertEqual(bytes(mem[0x3000:0x4000]), bytes(aux[0x4000:0x5000]))
        self.assertEqual(bytes(mem[0x8000:0x8800]), bytes(aux[0x6000:0x6800]))
        self.assertEqual(mem[0x9234], aux[0x5234])
        self.assertEqual(bytes(mem[0x0410:0x0418]), bytes(aux[0x6008:0x6010]))   # a patched area
        memory.write(0x1234, 0x99)              # ROM stays read-only
        self.assertNotEqual(mem[0x1234], 0x99)


if __name__ == "__main__":
    unittest.main()
