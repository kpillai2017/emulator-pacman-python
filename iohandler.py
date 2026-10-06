# Python port of the Pac-Man I/O (C# Buttons + the I/O part of PacManPCB)
#
# Reads  (0x5000-0x50BF): IN0, IN1, DSW1 - stored into memory by update()
# Writes (0x5000-0x50FF): interrupt enable, sound enable, aux board, flip screen,
#                         lamps/coin counters, WSG3 sound registers, sprite coordinates,
#                         watchdog
# OUT (0),A sets the low byte of the interrupt mode 2 vector.
import pygame
from core.input import Input
from soundfx import SoundFX
from memory import Memory
from dipswitches import DIPSwitches
from util import BIT0, BIT1, BIT2, BIT3, BIT4, BIT5, BIT6, BIT7

# Keyboard mapping (same keys as the C# version). Keep in sync with the help panel in video.py.
KEY_P1_UP, KEY_P1_DOWN, KEY_P1_LEFT, KEY_P1_RIGHT = pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT
KEY_P2_UP, KEY_P2_DOWN, KEY_P2_LEFT, KEY_P2_RIGHT = pygame.K_w, pygame.K_s, pygame.K_a, pygame.K_d
KEY_P1_START, KEY_P2_START = pygame.K_1, pygame.K_2
KEY_COIN1, KEY_COIN2 = pygame.K_5, pygame.K_6
KEY_SERVICE_CREDIT = pygame.K_3
KEY_RACK_ADVANCE = pygame.K_7
KEY_BOARD_TEST = pygame.K_8     # toggle


class Io:
    def __init__(self):
        self.IoInput = None
        self.IoSoundFX = None
        self.IoMemory = None
        self.dips = DIPSwitches()
        self.IN0 = 0xFF
        self.IN1 = 0xFF
        self.board_test = False
        self.reset()

    def init(self, in_obj: Input, sfx: SoundFX, mem: Memory, dips: DIPSwitches):
        self.IoInput = in_obj
        self.IoSoundFX = sfx
        self.IoMemory = mem
        self.dips = dips
        mem.io_write = self.write_register
        self.reset()

    def reset(self):
        self.interrupt_enabled = False   # 0x5000
        self.sound_enabled = False       # 0x5001
        self.flip_screen = False         # 0x5003
        self.interrupt_vector = 0        # last value written with OUT (0),A
        self.sprite_coords = bytearray(16)  # 0x5060-0x506F: x, y for sprites 0-7

    def update(self):
        """Sample the keyboard into the (active low) input ports."""
        k = self.IoInput.key_down if self.IoInput else (lambda key: False)
        if self.IoInput and self.IoInput.key_hit(KEY_BOARD_TEST):
            self.board_test = not self.board_test
        in0 = 0xFF
        if k(KEY_P1_UP): in0 &= ~BIT0
        if k(KEY_P1_LEFT): in0 &= ~BIT1
        if k(KEY_P1_RIGHT): in0 &= ~BIT2
        if k(KEY_P1_DOWN): in0 &= ~BIT3
        if k(KEY_RACK_ADVANCE): in0 &= ~BIT4
        if k(KEY_COIN1): in0 &= ~BIT5
        if k(KEY_COIN2): in0 &= ~BIT6
        if k(KEY_SERVICE_CREDIT): in0 &= ~BIT7
        in1 = 0x7F | (BIT7 if self.dips.is_upright() else 0)   # bit 7: cabinet type
        if k(KEY_P2_UP): in1 &= ~BIT0
        if k(KEY_P2_LEFT): in1 &= ~BIT1
        if k(KEY_P2_RIGHT): in1 &= ~BIT2
        if k(KEY_P2_DOWN): in1 &= ~BIT3
        if self.board_test: in1 &= ~BIT4
        if k(KEY_P1_START): in1 &= ~BIT5
        if k(KEY_P2_START): in1 &= ~BIT6
        self.IN0, self.IN1 = in0 & 0xFF, in1 & 0xFF
        if self.IoMemory:
            self.IoMemory.set_input_ports(self.IN0, self.IN1, self.dips.get_byte())

    def write_register(self, address, value):
        """CPU write to the memory mapped I/O area 0x5000-0x50FF."""
        if 0x5040 <= address <= 0x505F:
            if self.IoSoundFX:
                self.IoSoundFX.write_register(address - 0x5040, value)
        elif 0x5060 <= address <= 0x506F:
            self.sprite_coords[address - 0x5060] = value
        elif address == 0x5000:
            self.interrupt_enabled = bool(value & BIT0)
        elif address == 0x5001:
            self.sound_enabled = bool(value & BIT0)
        elif address == 0x5002:
            if value & BIT0:
                self.IoMemory.enable_aux_board()   # no-op unless Ms. Pac-Man
        elif address == 0x5003:
            self.flip_screen = bool(value & BIT0)
        # 0x5004-0x5007 lamps / coin lockout / coin counter, 0x50C0 watchdog: nothing to emulate

    def output_port(self, port, value):
        if port == 0:
            self.interrupt_vector = value

    def input_port(self, port):
        return 0xFF
