# Z80 conformance test: runs the ZEXDOC / ZEXALL instruction exercisers on cpu.Cpu.
# Port of pac-man-emulator/z80.tests/Tests/CPUIntegrationTest.cs
#
#   python -m tests.zex                 # all ZEXDOC tests (slow: a long time in Python)
#   python -m tests.zex 4 5 daa         # selected tests, by index or label
#   python -m tests.zex --all-flags     # ZEXALL (also checks undocumented X/Y flags)
#   python -m tests.zex --list
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cpu import Cpu  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

TESTS = ["adc16", "add16", "add16x", "add16y", "alu8i", "alu8r", "alu8rx", "alu8x", "bitx", "bitz80",
         "cpd1", "cpi1", "daa", "inca", "incb", "incbc", "incc", "incd", "incde", "ince", "inch",
         "inchl", "incix", "inciy", "incl", "incm", "incsp", "incx", "incxh", "incxl", "incyh", "incyl",
         "ld161", "ld162", "ld163", "ld164", "ld165", "ld166", "ld167", "ld168", "ld16im", "ld16ix",
         "ld8bd", "ld8im", "ld8imx", "ld8ix1", "ld8ix2", "ld8ix3", "ld8ixy", "ld8rr", "ld8rrx", "lda",
         "ldd1", "ldd2", "ldi1", "ldi2", "neg", "rld", "rot8080", "rotxy", "rotz80", "srz80", "srzx",
         "st8ix1", "st8ix2", "st8ix3", "stabd"]

TESTS_VECTOR = 0x100 + 58   # address of the exerciser's table of test pointers
BDOS_STUB = 0xFF00          # CALL 5 jumps here: OUT (0xFF),A ; RET


class RamMemory:
    """Flat 64 KB RAM, as seen by a CP/M program."""
    def __init__(self):
        self.memoryPtr = bytearray(0x10000)

    def get_memory_ptr(self):
        return self.memoryPtr

    def write(self, addr, value):
        self.memoryPtr[addr] = value


class CpmIo:
    """Emulates the two CP/M BDOS calls the exerciser uses (C=2 print char, C=9 print $-string)."""
    def __init__(self):
        self.cpu = None
        self.output = []

    def input_port(self, port):
        return 0xFF

    def output_port(self, port, value):
        if port != 0xFF:
            return
        cpu = self.cpu
        if cpu.C == 2:
            self._emit(chr(cpu.E))
        elif cpu.C == 9:
            addr = (cpu.D << 8) | cpu.E
            mem = cpu.mem
            chars = []
            while mem[addr] != ord("$"):
                chars.append(chr(mem[addr]))
                addr = (addr + 1) & 0xFFFF
            self._emit("".join(chars))

    def _emit(self, text):
        self.output.append(text)
        sys.stdout.write(text)
        sys.stdout.flush()


def run(program, test_index=None):
    mem = RamMemory()
    ram = mem.memoryPtr
    with open(os.path.join(DATA, program), "rb") as f:
        binary = f.read()
    ram[0x100:0x100 + len(binary)] = binary
    ram[0x0000] = 0x76                                        # JP 0 (program exit) -> HALT
    ram[0x0005:0x0008] = bytes([0xC3, BDOS_STUB & 0xFF, BDOS_STUB >> 8])  # JP stub; (6) = SP = 0xFF00
    ram[BDOS_STUB:BDOS_STUB + 3] = bytes([0xD3, 0xFF, 0xC9])  # OUT (0xFF),A ; RET

    if test_index is not None:
        # Run a single test: make it the first table entry, followed by the 0x0000 terminator
        entry = TESTS_VECTOR + test_index * 2
        ram[TESTS_VECTOR:TESTS_VECTOR + 2] = ram[entry:entry + 2]
        ram[TESTS_VECTOR + 2:TESTS_VECTOR + 4] = b"\x00\x00"

    io = CpmIo()
    cpu = Cpu()
    cpu.init(mem, io)
    io.cpu = cpu
    cpu.PC = 0x100

    total = 0
    start = time.time()
    while not cpu.halted:
        total += cpu.run(1_000_000)
    elapsed = time.time() - start
    text = "".join(io.output)
    return ("ERROR" not in text), total, elapsed


def main():
    parser = argparse.ArgumentParser(description="Run ZEXDOC / ZEXALL against cpu.Cpu")
    parser.add_argument("tests", nargs="*", help="test indices or labels (default: all, in one run)")
    parser.add_argument("--all-flags", action="store_true", help="use ZEXALL (undocumented flags too)")
    parser.add_argument("--list", action="store_true", help="list the test labels")
    args = parser.parse_args()
    if args.list:
        for i, name in enumerate(TESTS):
            print(f"{i:2d} {name}")
        return 0
    program = "zexall.com" if args.all_flags else "zexdoc.com"
    selected = [int(t) if t.isdigit() else TESTS.index(t) for t in args.tests] or [None]
    failures = 0
    for index in selected:
        ok, cycles, secs = run(program, index)
        failures += not ok
        print(f"  [{cycles / secs / 1e6:.2f} MHz effective, {secs:.1f}s]")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
