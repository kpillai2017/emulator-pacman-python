# Python port of the C# AudioHardware class (Namco WSG3 waveform sound generator)
#
# Unlike Space Invaders there are no sampled sounds: the WSG3 has 3 voices, each
# playing one of 8 32-sample 4-bit waveforms (sound PROMs) at a programmable
# frequency and volume. The chip is clocked at 96 kHz (3.072 MHz / 32).
#
# Registers (offset from 0x5040, 4 bits each):
#   0x00-0x04 voice 1 accumulator   0x05 voice 1 waveform
#   0x06-0x09 voice 2 accumulator   0x0A voice 2 waveform
#   0x0B-0x0E voice 3 accumulator   0x0F voice 3 waveform
#   0x10-0x14 voice 1 frequency (20 bit)   0x15 voice 1 volume
#   0x16-0x19 voice 2 frequency (16 bit)   0x1A voice 2 volume
#   0x1B-0x1E voice 3 frequency (16 bit)   0x1F voice 3 volume
#
# Each emulated frame produces 1/60 s of audio. Samples are generated directly at
# the mixer's output rate by point sampling the 96 kHz stream (exactly what the
# C# version does after ticking 1600 times), then streamed to a pygame mixer
# Channel with play()/queue().
from array import array
import pygame

WSG_CLOCK = 96000
TICKS_PER_FRAME = WSG_CLOCK // 60     # 1600
OUTPUT_GAIN = 160                     # 8-bit mixed sample -> 16-bit output
MIN_CHUNK_FRAMES = 3                  # queue at least ~50 ms at a time (avoids gaps)
MAX_PENDING_FRAMES = 8                # drop audio rather than let latency grow

# (waveform reg, first frequency reg, frequency nibbles, volume reg, sample index shift)
VOICES = ((0x05, 0x10, 5, 0x15, 15), (0x0A, 0x16, 4, 0x1A, 11), (0x0F, 0x1B, 4, 0x1F, 11))


class SoundFX:
    def __init__(self):
        self.regs = bytearray(0x20)
        self.accumulators = [0, 0, 0]
        self.waveforms = [[0] * 32 for _ in range(8)]
        self.output_rate = 22050
        self.output_channels = 2
        self.channel = None
        self.muted = False
        self._pending = array("h")
        self._frame_samples = 0
        self._sample_debt = 0
        self._tick_tables = {}

    def init(self, sound_rom: bytes) -> bool:
        """sound_rom: the two 256 byte sound PROMs (82s126.1m + 82s126.3m)."""
        # Only waveforms 0-7 are addressable (3 bit waveform register)
        self.waveforms = [[(b & 0x0F) - 8 for b in sound_rom[w * 32:(w + 1) * 32]] for w in range(8)]
        mixer = pygame.mixer.get_init()
        if mixer:
            self.output_rate, _, self.output_channels = mixer
            self.channel = pygame.mixer.Channel(0)
        self._frame_samples = self.output_rate / 60
        self.reset()
        return True

    def reset(self):
        self.regs[:] = bytes(0x20)
        self.accumulators = [0, 0, 0]
        self._pending = array("h")
        self._sample_debt = 0

    def write_register(self, offset, value):
        self.regs[offset & 0x1F] = value & 0x0F

    def _ticks(self, n):
        """WSG tick count elapsed at each of n output samples spread over one frame."""
        table = self._tick_tables.get(n)
        if table is None:
            # Same sampling phase as the C# downsampler: source sample floor(k * factor)
            table = [(k * TICKS_PER_FRAME) // n + 1 for k in range(n)]
            self._tick_tables[n] = table
        return table

    def generate_frame(self):
        """Run the WSG for one frame (1600 ticks); return mixed signed 8-bit samples at output_rate."""
        self._sample_debt += self.output_rate
        n = self._sample_debt // 60
        self._sample_debt -= n * 60
        ticks = self._ticks(n)
        regs = self.regs
        mixed = None
        for v, (wave_reg, freq_reg, nibbles, vol_reg, shift) in enumerate(VOICES):
            freq = 0
            for i in range(nibbles):
                freq |= regs[freq_reg + i] << (4 * i)
            mask = (1 << (4 * nibbles)) - 1
            acc = self.accumulators[v]
            self.accumulators[v] = (acc + freq * TICKS_PER_FRAME) & mask
            volume = regs[vol_reg]
            if volume == 0 or freq == 0:
                continue        # silent voice: skip the per-sample work
            table = [s * volume for s in self.waveforms[regs[wave_reg] & 0x07]]
            samples = [table[((acc + freq * t) >> shift) & 0x1F] for t in ticks]
            mixed = samples if mixed is None else [a + b for a, b in zip(mixed, samples)]
        if mixed is None:
            return [0] * n
        return [127 if s > 127 else (-128 if s < -128 else s) for s in mixed]

    def update(self, sound_enabled: bool):
        """Produce this frame's audio and stream it to the mixer."""
        samples = self.generate_frame()
        if self.channel is None:
            return
        if not sound_enabled or self.muted:
            samples = [0] * len(samples)
        out = array("h", [s * OUTPUT_GAIN for s in samples])
        if self.output_channels == 2:
            stereo = array("h", bytes(len(out) * 4))
            stereo[0::2] = out
            stereo[1::2] = out
            out = stereo
        pending = self._pending
        pending.extend(out)
        frame_len = int(self._frame_samples) * self.output_channels
        if len(pending) > frame_len * MAX_PENDING_FRAMES:
            del pending[:len(pending) - frame_len * MIN_CHUNK_FRAMES]
        busy = self.channel.get_busy()
        if busy and (self.channel.get_queue() is not None or len(pending) < frame_len * MIN_CHUNK_FRAMES):
            return
        sound = pygame.mixer.Sound(buffer=pending.tobytes())
        if busy:
            self.channel.queue(sound)
        else:
            self.channel.play(sound)
        self._pending = array("h")

    def toggle_mute(self):
        self.muted = not self.muted

    def free(self):
        if self.channel is not None:
            self.channel.stop()
        self.channel = None
