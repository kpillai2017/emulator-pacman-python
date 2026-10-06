# Python port of the C# Emulator / PacManPCB main loop
import pygame

from core.game import Game
from memory import Memory
from iohandler import Io
from cpu import Cpu
from soundfx import SoundFX
from video import Video
from dipswitches import DIPSwitches
from roms import load_rom_set, RomError, ROM_SETS, PACMAN

WINDOW_W = 860
WINDOW_H = 640
FPS = 60
CYCLES_PER_FRAME = Cpu.CLOCK_HZ // FPS     # 51,200 T-states between VBLANK interrupts


class Emulator(Game):
    def __init__(self, rom_path=None, rom_set=PACMAN, dip_switches="dip-switches.json",
                 skip_checksums=False, writable_rom=False, debug=False, fullscreen=False):
        super().__init__()
        self.rom_set = rom_set
        # Both sets live side by side in data/: their shared files have identical
        # contents and the set-specific tiles/sprites have distinct names.
        self.rom_path = rom_path or "data"
        self.dip_switches_path = dip_switches
        self.skip_checksums = skip_checksums
        self.writable_rom = writable_rom
        self.debug = debug
        self.fullscreen = fullscreen
        self.emulIO = Io()
        self.emulMemory = Memory()
        self.emulCpu = Cpu()
        self.emulSoundFX = SoundFX()
        self.emulVideo = Video()
        self.paused = False
        self.cycle_overshoot = 0
        self.frames = 0

    def init(self):
        try:
            dips = DIPSwitches.from_file(self.dip_switches_path)
            rom_data = load_rom_set(self.rom_set, self.rom_path, not self.skip_checksums)
        except (RomError, ValueError, OSError) as error:
            print(f"Error: {error}")
            return False
        title = ROM_SETS[self.rom_set]["title"]
        if not self.init_system(f"{title} Emulator", WINDOW_W, WINDOW_H, self.fullscreen):
            return False
        if not self.emulMemory.init(rom_data, self.writable_rom):
            return False
        if not self.emulCpu.init(self.get_memory(), self.get_io()):
            return False
        if not self.emulSoundFX.init(rom_data.sound):
            return False
        if not self.emulVideo.init(self.get_graphics(), self.get_memory(), self.get_io(), rom_data):
            return False
        self.emulIO.init(self.get_input(), self.get_soundfx(), self.get_memory(), dips)
        self.set_fps(FPS)
        self.get_graphics().clear(0, 0, 0)
        return True

    def run_frame(self):
        """Emulate one 1/60 s frame: CPU, sound, then the VBLANK interrupt."""
        io = self.emulIO
        io.update()
        target = CYCLES_PER_FRAME - self.cycle_overshoot
        self.cycle_overshoot = self.emulCpu.run(target) - target
        self.emulSoundFX.update(io.sound_enabled)
        if io.interrupt_enabled:
            self.emulCpu.interrupt(io.interrupt_vector)
        self.frames += 1

    def update(self):
        in_obj = self.get_input()
        if in_obj.key_down(pygame.K_ESCAPE):
            self.end()
        if in_obj.key_hit(pygame.K_p):
            self.paused = not self.paused
        if in_obj.key_hit(pygame.K_m):
            self.emulSoundFX.toggle_mute()
        if not self.paused:
            self.run_frame()
        status = []
        if self.paused:
            status.append("PAUSED")
        if self.emulSoundFX.muted:
            status.append("MUTED")
        if self.emulIO.board_test:
            status.append("BOARD TEST")
        self.emulVideo.status = " ".join(status)
        self.emulVideo.draw()
        if self.debug:
            self.emulVideo.draw_outline_font("-> " + self.emulCpu.get_debug_output(), 0, 20, 255, 255, 255)

    def draw(self, g):
        pass

    def get_soundfx(self):
        return self.emulSoundFX

    def get_memory(self):
        return self.emulMemory

    def get_video(self):
        return self.emulVideo

    def get_io(self):
        return self.emulIO

    def get_cpu(self):
        return self.emulCpu

    def free(self):
        self.emulVideo.free()
        self.emulCpu.free()
        self.emulSoundFX.free()
        self.emulMemory.free()
        self.free_system()
