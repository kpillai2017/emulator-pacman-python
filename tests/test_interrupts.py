"""Interrupt delivery: the Z80 EI delay and the held VBLANK interrupt line.

    python -m unittest tests.test_interrupts
"""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cpu import Cpu  # noqa: E402
from emulator import Emulator  # noqa: E402
from tests.test_smoke import write_rom_set  # noqa: E402


class FlatMemory:
    """64KB of RAM with the interface the Cpu expects."""
    def __init__(self, program):
        self.mem = bytearray(0x10000)
        self.mem[0:len(program)] = program

    def get_memory_ptr(self):
        return self.mem

    def write(self, address, value):
        self.mem[address] = value


class NoIo:
    def input_port(self, port):
        return 0xFF

    def output_port(self, port, value):
        pass


def make_cpu(program):
    cpu = Cpu()
    cpu.init(FlatMemory(program), NoIo())
    return cpu


class CpuInterruptTests(unittest.TestCase):
    def test_disabled_interrupts_are_refused(self):
        cpu = make_cpu(bytes([0xED, 0x56, 0x00]))      # IM 1 ; NOP
        cpu.run(1)
        self.assertEqual(cpu.interrupt(), 0)
        self.assertEqual(cpu.PC, 2)

    def test_interrupt_waits_one_instruction_after_ei(self):
        cpu = make_cpu(bytes([0xED, 0x56, 0xFB, 0x00, 0x00]))   # IM 1 ; EI ; NOP ; NOP
        cpu.run(1)                      # IM 1
        cpu.run(1)                      # EI
        self.assertEqual(cpu.interrupt(), 0, "accepted straight after EI")
        cpu.run(1)                      # the instruction after EI
        self.assertEqual(cpu.interrupt(), 13)
        self.assertEqual(cpu.PC, 0x0038)
        self.assertFalse(cpu.iff1)
        sp = cpu.SP
        self.assertEqual(cpu.mem[sp] | (cpu.mem[sp + 1] << 8), 4)   # return address after the NOP

    def test_ei_halt_wakes_on_interrupt(self):
        cpu = make_cpu(bytes([0xED, 0x56, 0xFB, 0x76]))         # IM 1 ; EI ; HALT
        cpu.run(3)                      # IM 1, EI, HALT (EI delay over)
        cpu.run(20)                     # still halted
        self.assertTrue(cpu.halted)
        self.assertEqual(cpu.interrupt(), 13)
        sp = cpu.SP
        self.assertEqual(cpu.mem[sp] | (cpu.mem[sp + 1] << 8), 4)   # resumes after the HALT


class HeldInterruptLineTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="tmp_rovo_")
        write_rom_set(self._tmp.name)
        self._cwd = os.getcwd()
        os.chdir(ROOT)
        self.emu = Emulator(self._tmp.name, skip_checksums=True)
        self.assertTrue(self.emu.init())

    def tearDown(self):
        self.emu.free()
        os.chdir(self._cwd)
        self._tmp.cleanup()

    def _refuse_interrupts(self):
        """Make the CPU refuse interrupts (as if inside a DI section) until the returned function is called."""
        cpu = self.emu.get_cpu()
        accept = cpu.interrupt
        cpu.interrupt = lambda data_bus=0: 0
        return lambda: setattr(cpu, "interrupt", accept)

    def test_vblank_during_di_is_delivered_later_not_lost(self):
        emu, cpu = self.emu, self.emu.get_cpu()
        mem = emu.get_memory().get_memory_ptr()
        for _ in range(5):
            emu.run_frame()
        count = mem[0x4C00]             # the handler counts accepted interrupts
        allow = self._refuse_interrupts()
        emu.run_frame()                 # last accepted interrupt's handler runs; VBLANK refused
        self.assertTrue(emu.irq_pending)
        self.assertEqual(mem[0x4C00], count + 1)
        allow()
        emu.run_frame()                 # the held interrupt is taken at once, then this VBLANK
        self.assertFalse(emu.irq_pending)
        self.assertEqual(mem[0x4C00], count + 2)
        self.assertEqual(cpu.PC, 0x1000)
        emu.run_frame()
        self.assertEqual(mem[0x4C00], count + 3)    # no interrupt was lost

    def test_disabling_interrupts_at_0x5000_clears_the_line(self):
        emu, cpu = self.emu, self.emu.get_cpu()
        emu.run_frame()
        allow = self._refuse_interrupts()
        emu.run_frame()
        self.assertTrue(emu.irq_pending)
        emu.get_memory().write(0x5000, 0)
        allow()
        emu.run_frame()
        self.assertFalse(emu.irq_pending)
        self.assertNotEqual(cpu.PC, 0x1000)

if __name__ == "__main__":
    unittest.main()
