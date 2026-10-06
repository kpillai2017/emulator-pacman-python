# WSG3 sound tests: the fast per-output-sample generator in soundfx.py must produce
# exactly what the C# AudioHardware.Tick() loop + Platform downsampler produce.
#
#   python -m unittest tests.test_sound
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from soundfx import SoundFX, TICKS_PER_FRAME  # noqa: E402


class CSharpReferenceWSG:
    """Literal port of AudioHardware.Tick() and Platform.QueueAudioSamples() mixing."""
    def __init__(self, sound_rom):
        self.rom = sound_rom
        self.acc = [0, 0, 0]

    def frame(self, regs, target_samples):
        f1 = sum((regs[0x10 + i] & 0x0F) << (4 * i) for i in range(5))
        f2 = sum((regs[0x16 + i] & 0x0F) << (4 * i) for i in range(4))
        f3 = sum((regs[0x1B + i] & 0x0F) << (4 * i) for i in range(4))
        source = []
        for _ in range(TICKS_PER_FRAME):
            self.acc[0] = (self.acc[0] + f1) & 0xFFFFF
            self.acc[1] = (self.acc[1] + f2) & 0xFFFF
            self.acc[2] = (self.acc[2] + f3) & 0xFFFF
            n1 = self.rom[(regs[0x05] & 7) * 32 + ((self.acc[0] & 0xF8000) >> 15)]
            n2 = self.rom[(regs[0x0A] & 7) * 32 + ((self.acc[1] & 0xF800) >> 11)]
            n3 = self.rom[(regs[0x0F] & 7) * 32 + ((self.acc[2] & 0xF800) >> 11)]
            s = (((n1 & 0x0F) - 8) * (regs[0x15] & 0x0F) + ((n2 & 0x0F) - 8) * (regs[0x1A] & 0x0F)
                 + ((n3 & 0x0F) - 8) * (regs[0x1F] & 0x0F))
            source.append(max(-128, min(127, s)))
        factor = TICKS_PER_FRAME / target_samples
        return [source[int(factor * i)] for i in range(target_samples)]


class SoundTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(1234)
        self.rom = bytes(rng.randrange(16) for _ in range(512))

    def _make(self, rate):
        sfx = SoundFX()
        sfx.init(self.rom)          # mixer not initialised: synthesis only
        sfx.output_rate = rate
        return sfx

    def test_matches_csharp_reference(self):
        rng = random.Random(42)
        sfx = self._make(24000)     # 400 samples per frame, as in the C# fixed frame size
        ref = CSharpReferenceWSG(self.rom)
        for frame in range(30):
            if frame % 5 == 0:      # reprogram the voices every few frames
                for offset in range(0x05, 0x20):
                    sfx.write_register(offset, rng.randrange(16))
                if frame == 10:     # a silent voice exercises the fast path
                    sfx.write_register(0x1A, 0)
            expected = ref.frame(sfx.regs, 400)
            self.assertEqual(sfx.generate_frame(), expected, f"frame {frame}")

    def test_silence_when_volume_zero(self):
        sfx = self._make(22050)
        for offset in range(0x10, 0x15):
            sfx.write_register(offset, 0x0F)
        self.assertEqual(set(sfx.generate_frame()), {0})

    def test_fractional_sample_rate_keeps_long_term_count(self):
        sfx = self._make(22050)     # 367.5 samples per frame
        total = sum(len(sfx.generate_frame()) for _ in range(60))
        self.assertEqual(total, 22050)


if __name__ == "__main__":
    unittest.main()
