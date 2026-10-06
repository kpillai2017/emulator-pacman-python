# Python port of the C# Pac-Man memory map (PacManPCB.Read/Write + MsPacManAuxBoard)
#
#   0x0000-0x3FFF  code ROM (4 x 4KB)
#   0x4000-0x43FF  video RAM: tile numbers
#   0x4400-0x47FF  video RAM: tile palettes
#   0x4800-0x4FEF  RAM
#   0x4FF0-0x4FFF  sprite number / flip flags and palettes (8 sprites x 2 bytes)
#   0x5000-0x50FF  memory mapped I/O (reads: IN0, IN1, DIP switches; writes: see iohandler.py)
#   0x8000-0x9FFF  Ms. Pac-Man aux board ROM (once enabled)
#
# The CPU reads straight from memoryPtr for speed, so the I/O read ports are stored
# in it too (refreshed by Io.update() each frame). Writes always go through write(),
# which protects the ROM and routes 0x5000-0x50FF to the I/O registers.
#
# Ms. Pac-Man is a Pac-Man board plus a daughterboard plugged into the Z80 socket.
# Its ROMs are encrypted (address and data lines scrambled) and it patches small
# pieces of the Pac-Man code with jumps into its own code. As in the C# version the
# board is modelled simply: once the game writes 1 to 0x5002 (after the Pac-Man
# self-test) the decrypted and patched image replaces the code ROM area.
from roms import RomData, MS_PAC_MAN_AUX_U5, MS_PAC_MAN_AUX_U6, MS_PAC_MAN_AUX_U7, MSPACMAN


class Memory:
    def __init__(self):
        self.memoryPtr = bytearray(0x10000)  # 64KB address space
        self.writable_rom = False
        self.rom_data = None
        self.aux_roms = None
        self.aux_enabled = False
        self.io_write = lambda address, value: None   # set by Io.init()

    def init(self, rom_data: RomData, writable_rom: bool = False) -> bool:
        self.rom_data = rom_data
        self.writable_rom = writable_rom
        if rom_data.rom_set == MSPACMAN:
            self.aux_roms = self.build_aux_roms(rom_data)
        self.reset()
        return True

    def reset(self):
        mem = self.memoryPtr
        mem[:] = bytes(0x10000)
        code = self.rom_data.code
        mem[0:len(code)] = code
        self.aux_enabled = False

    def get_memory_ptr(self):
        return self.memoryPtr

    def write(self, address, value):
        if 0x4000 <= address < 0x5000:      # RAM (by far the most common case)
            self.memoryPtr[address] = value
        elif address < 0x4000:
            if self.writable_rom:           # homebrew ROMs may need this
                self.memoryPtr[address] = value
        elif address < 0x5100:
            self.io_write(address, value)
        # anything else is unmapped on the Pac-Man board: ignore

    def set_input_ports(self, in0, in1, dip):
        """Store the I/O read ports where the CPU will read them."""
        mem = self.memoryPtr
        mem[0x5000:0x5040] = bytes((in0,)) * 0x40
        mem[0x5040:0x5080] = bytes((in1,)) * 0x40
        mem[0x5080:0x50C0] = bytes((dip,)) * 0x40

    # --- Ms. Pac-Man auxiliary board -------------------------------------

    def enable_aux_board(self):
        """Writing 1 to 0x5002 on Ms. Pac-Man maps the decrypted, patched aux ROMs in."""
        if self.aux_roms is None or self.aux_enabled:
            return
        aux = self.aux_roms
        mem = self.memoryPtr
        mem[0x0000:0x4000] = aux[0x0000:0x4000]
        mem[0x8000:0x8800] = aux[0x6000:0x6800]
        mem[0x8800:0xA000] = bytes(aux[(a & 0xFFF) + 0x5000] for a in range(0x8800, 0xA000))
        self.aux_enabled = True

    @staticmethod
    def _decrypt_data(e):
        return ((e & 0xC0) >> 3) | ((e & 0x10) << 2) | ((e & 0x0E) >> 1) | ((e & 0x01) << 7) | (e & 0x20)

    @staticmethod
    def _decrypt_address1(e):
        return ((e & 0x807) | ((e & 0x400) >> 7) | ((e & 0x200) >> 2) | ((e & 0x080) << 3)
                | ((e & 0x040) << 2) | ((e & 0x138) << 1))

    @staticmethod
    def _decrypt_address2(e):
        return ((e & 0x807) | ((e & 0x040) << 4) | ((e & 0x100) >> 3) | ((e & 0x080) << 2)
                | ((e & 0x600) >> 2) | ((e & 0x028) << 1) | ((e & 0x010) >> 1))

    # (destination, source) of the 8-byte patches the aux board applies over the Pac-Man code
    _AUX_PATCHES = ((0x0410, 0x6008), (0x08E0, 0x61D8), (0x0A30, 0x6118), (0x0BD0, 0x60D8),
                    (0x0C20, 0x6120), (0x0E58, 0x6168), (0x0EA8, 0x6198), (0x1000, 0x6020),
                    (0x1008, 0x6010), (0x1288, 0x6098), (0x1348, 0x6048), (0x1688, 0x6088),
                    (0x16B0, 0x6188), (0x16D8, 0x60C8), (0x16F8, 0x61C8), (0x19A8, 0x60A8),
                    (0x19B8, 0x61A8), (0x2060, 0x6148), (0x2108, 0x6018), (0x21A0, 0x61A0),
                    (0x2298, 0x60A0), (0x23E0, 0x60E8), (0x2418, 0x6000), (0x2448, 0x6058),
                    (0x2470, 0x6140), (0x2488, 0x6080), (0x24B0, 0x6180), (0x24D8, 0x60C0),
                    (0x24F8, 0x61C0), (0x2748, 0x6050), (0x2780, 0x6090), (0x27B8, 0x6190),
                    (0x2800, 0x6028), (0x2B20, 0x6100), (0x2B30, 0x6110), (0x2BF0, 0x61D0),
                    (0x2CC0, 0x60D0), (0x2CD8, 0x60E0), (0x2CF0, 0x61E0), (0x2D60, 0x6160))

    @classmethod
    def build_aux_roms(cls, rom_data: RomData) -> bytearray:
        """Decrypt U5/U6/U7 and build the 26KB aux board image (port of MsPacManAuxBoard.LoadAuxROMs)."""
        u5, u6, u7 = rom_data.get(MS_PAC_MAN_AUX_U5), rom_data.get(MS_PAC_MAN_AUX_U6), rom_data.get(MS_PAC_MAN_AUX_U7)
        aux = bytearray((16 + 10) * 1024)
        for i in range(0x1000):
            a = cls._decrypt_address1(i)
            aux[a + 0x4000] = cls._decrypt_data(u7[i])
            aux[a + 0x5000] = cls._decrypt_data(u6[i])
        for i in range(0x0800):
            aux[cls._decrypt_address2(i) + 0x6000] = cls._decrypt_data(u5[i])
        aux[0x0000:0x3000] = rom_data.code[0x0000:0x3000]
        aux[0x3000:0x4000] = aux[0x4000:0x5000]
        for dst, src in cls._AUX_PATCHES:
            aux[dst:dst + 8] = aux[src:src + 8]
        return aux

    def free(self):
        self.memoryPtr = None
