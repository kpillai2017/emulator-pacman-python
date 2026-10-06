# Python port of the C# Emulator / PacManPCB main loop
#
# The Emulator ties the parts of the Pac-Man board together:
#   Cpu (cpu.py)        Z80 at 3.072 MHz
#   Memory (memory.py)  ROM/RAM map, Ms. Pac-Man aux board
#   Io (iohandler.py)   joysticks/buttons/DIP switches and the 0x5000 control registers
#   Video (video.py)    tiles + sprites -> the 224x288 portrait picture
#   SoundFX (soundfx.py) Namco WSG3 3-voice wavetable sound
# core.game.Game provides the pygame window, input and the 60 FPS loop that calls update().
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
        self.cycle_overshoot = 0    # T-states the last frame ran past its budget
        self.irq_pending = False    # VBLANK interrupt raised but not yet accepted by the CPU
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
        """Emulate one 1/60 s frame.

        Real hardware runs the CPU continuously and raises one interrupt per frame at
        vertical blank (VBLANK). Here a frame is: sample the inputs, run the CPU for a
        frame's worth of T-states, produce the frame's audio, then raise the VBLANK
        interrupt (the screen is drawn by update() right after).
        """
        io = self.emulIO
        cpu = self.emulCpu
        io.update()
        # Run exactly one frame of CPU time on average: an instruction can't be cut in
        # half, so whatever the previous frame overran by is taken off this one.
        budget = CYCLES_PER_FRAME - self.cycle_overshoot
        done = self._deliver_pending_interrupt(budget)
        if done < budget:
            done += cpu.run(budget - done)
        self.cycle_overshoot = done - budget
        self.emulSoundFX.update(io.sound_enabled)
        # VBLANK: if the game has enabled interrupts at 0x5000, the interrupt line is
        # raised and stays raised until the CPU accepts it (it may be inside a DI
        # section right now, in which case it is delivered early in the next frame).
        if io.interrupt_enabled:
            self.irq_pending = True
            self.cycle_overshoot += self._deliver_pending_interrupt(0)
        self.frames += 1

    def _deliver_pending_interrupt(self, budget):
        """Deliver the pending interrupt as soon as the CPU accepts it.

        While the CPU refuses it, keep running it for at most `budget` T-states and retry:
        one instruction at a time just after EI, in 64 T-state (~20 us) steps while
        interrupts are disabled (e.g. during the boot self-test, which runs with DI).
        Returns the T-states used.
        """
        io = self.emulIO
        cpu = self.emulCpu
        done = 0
        while self.irq_pending:
            if not io.interrupt_enabled:        # writing 0 to 0x5000 clears the line
                self.irq_pending = False
                break
            taken = cpu.interrupt(io.interrupt_vector)
            if taken:
                self.irq_pending = False
                done += taken
                break
            if done >= budget:
                break
            done += cpu.run(1 if cpu.iff1 else 64)
        return done

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
