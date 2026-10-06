# Python port of the C# Zilog Z80 CPU (pac-man-emulator/z80)
#
# Speed matters: Pac-Man runs a 3.072 MHz Z80, roughly 350,000 instructions per
# emulated second, so a naive "if/elif" interpreter is far too slow in Python.
#
# Instead every opcode (all prefixes: main, CB, ED, DD, FD, DDCB, FDCB) is
# turned into a small, specialised Python function at start-up. The functions
# are generated from the readable templates below, compiled once with exec(),
# and stored in 256-entry dispatch tables. Each handler is a closure over the
# CPU instance, the memory bytearray and the memory write function, so running
# an instruction is just: table[mem[pc]]()  ->  returns T-states used.
#
# Registers are plain int attributes: A F B C D E H L (8-bit), IX IY SP PC
# (16-bit), the alternate set A_ F_ B_ C_ D_ E_ H_ L_, and I, R.
# F is kept as a real flags byte so PUSH/POP AF and the flag lookup tables work
# directly. Undocumented X/Y flags (bits 3 and 5) are emulated for most
# instructions; ZEXDOC (documented behaviour) is the conformance target.
from util import Util

# Flag bits in F
FLAG_S = 0x80   # Sign
FLAG_Z = 0x40   # Zero
FLAG_Y = 0x20   # Undocumented (copy of result bit 5)
FLAG_H = 0x10   # Half carry
FLAG_X = 0x08   # Undocumented (copy of result bit 3)
FLAG_P = 0x04   # Parity / overflow
FLAG_N = 0x02   # Subtract
FLAG_C = 0x01   # Carry


def _build_flag_tables():
    """Precompute per-value flag results so the hot paths are table lookups."""
    sz53 = [(v & 0xA8) | (FLAG_Z if v == 0 else 0) for v in range(256)]
    sz53p = [sz53[v] | (FLAG_P if bin(v).count("1") % 2 == 0 else 0) for v in range(256)]
    # Flags for INC r / DEC r given the *result* (carry is preserved separately)
    inc = [sz53[r] | (FLAG_H if (r & 0x0F) == 0 else 0) | (FLAG_P if r == 0x80 else 0) for r in range(256)]
    dec = [sz53[r] | FLAG_N | (FLAG_H if (r & 0x0F) == 0x0F else 0) | (FLAG_P if r == 0x7F else 0)
           for r in range(256)]
    signed = [v - 256 if v > 127 else v for v in range(256)]
    return sz53, sz53p, inc, dec, signed


SZ53, SZ53P, INCF, DECF, SIGNED = _build_flag_tables()

# ---------------------------------------------------------------------------
# Code generation helpers. "ctx" is the register that plays the role of HL:
# "HL" for unprefixed opcodes, "IX" after a DD prefix, "IY" after FD.
# ---------------------------------------------------------------------------
_R8 = ("B", "C", "D", "E", "H", "L", None, "A")
_CC = ("not (self.F & 0x40)", "(self.F & 0x40)",    # NZ, Z
       "not (self.F & 0x01)", "(self.F & 0x01)",    # NC, C
       "not (self.F & 0x04)", "(self.F & 0x04)",    # PO, PE
       "not (self.F & 0x80)", "(self.F & 0x80)")    # P,  M

FETCH8 = "pc = self.PC; n = mem[pc]; self.PC = (pc + 1) & 0xFFFF"
FETCH16 = "pc = self.PC; nn = mem[pc] | (mem[(pc + 1) & 0xFFFF] << 8); self.PC = (pc + 2) & 0xFFFF"
POP = "sp = self.SP; v = mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8); self.SP = (sp + 2) & 0xFFFF"


def _push(expr):
    return (f"v = {expr}; sp = (self.SP - 2) & 0xFFFF; self.SP = sp; "
            f"wr((sp + 1) & 0xFFFF, v >> 8); wr(sp, v & 0xFF)")


def _get8(r, ctx):
    """Expression reading 8-bit register r (0-7, not 6). IXH/IXL etc. when prefixed."""
    if ctx != "HL" and r == 4:
        return f"(self.{ctx} >> 8)"
    if ctx != "HL" and r == 5:
        return f"(self.{ctx} & 0xFF)"
    return "self." + _R8[r]


def _set8(r, ctx, v):
    """Statement writing expression v into 8-bit register r."""
    if ctx != "HL" and r == 4:
        return f"self.{ctx} = (self.{ctx} & 0xFF) | (({v}) << 8)"
    if ctx != "HL" and r == 5:
        return f"self.{ctx} = (self.{ctx} & 0xFF00) | ({v})"
    return f"self.{_R8[r]} = {v}"


def _addr(ctx):
    """Statement computing 'addr' for the (HL) / (IX+d) / (IY+d) operand."""
    if ctx == "HL":
        return "addr = (self.H << 8) | self.L"
    return f"pc = self.PC; addr = (self.{ctx} + SIGNED[mem[pc]]) & 0xFFFF; self.PC = (pc + 1) & 0xFFFF"


_RP = (("B", "C"), ("D", "E"), None, None)


def _get16(p, ctx, af=False):
    """Expression reading register pair p: BC DE HL(/IX/IY) SP (or AF when af=True)."""
    if p == 2:
        return "((self.H << 8) | self.L)" if ctx == "HL" else f"self.{ctx}"
    if p == 3:
        return "((self.A << 8) | self.F)" if af else "self.SP"
    hi, lo = _RP[p]
    return f"((self.{hi} << 8) | self.{lo})"


def _set16(p, ctx, v, af=False):
    """Statement writing the simple name v into register pair p."""
    if p == 2:
        return f"self.H = {v} >> 8; self.L = {v} & 0xFF" if ctx == "HL" else f"self.{ctx} = {v}"
    if p == 3:
        return f"self.A = {v} >> 8; self.F = {v} & 0xFF" if af else f"self.SP = {v}"
    hi, lo = _RP[p]
    return f"self.{hi} = {v} >> 8; self.{lo} = {v} & 0xFF"


_ADD_FLAGS = "self.F = SZ53[r & 0xFF] | (r >> 8) | ((a ^ v ^ r) & 0x10) | (((a ^ r) & (v ^ r) & 0x80) >> 5)"
_SUB_FLAGS = ("self.F = SZ53[r & 0xFF] | ((r >> 8) & 1) | 0x02 | ((a ^ v ^ r) & 0x10)"
              " | (((a ^ v) & (a ^ r) & 0x80) >> 5)")


def _alu(y):
    """Lines for ALU operation y (ADD ADC SUB SBC AND XOR OR CP) of A with local 'v'."""
    return (
        ["a = self.A; r = a + v", _ADD_FLAGS, "self.A = r & 0xFF"],
        ["a = self.A; r = a + v + (self.F & 1)", _ADD_FLAGS, "self.A = r & 0xFF"],
        ["a = self.A; r = a - v", _SUB_FLAGS, "self.A = r & 0xFF"],
        ["a = self.A; r = a - v - (self.F & 1)", _SUB_FLAGS, "self.A = r & 0xFF"],
        ["r = self.A & v; self.A = r; self.F = SZ53P[r] | 0x10"],
        ["r = self.A ^ v; self.A = r; self.F = SZ53P[r]"],
        ["r = self.A | v; self.A = r; self.F = SZ53P[r]"],
        # CP: X/Y flags come from the operand, not the result
        ["a = self.A; r = a - v",
         "self.F = (SZ53[r & 0xFF] & 0xD7) | (v & 0x28) | ((r >> 8) & 1) | 0x02 | ((a ^ v ^ r) & 0x10)"
         " | (((a ^ v) & (a ^ r) & 0x80) >> 5)"],
    )[y]


# CB-prefix rotate/shift operations on local 'v' -> result 'r', carry 'c'
_ROT = ("c = v >> 7; r = ((v << 1) | c) & 0xFF",            # RLC
        "c = v & 1; r = (v >> 1) | (c << 7)",               # RRC
        "c = v >> 7; r = ((v << 1) | (self.F & 1)) & 0xFF",  # RL
        "c = v & 1; r = (v >> 1) | ((self.F & 1) << 7)",     # RR
        "c = v >> 7; r = (v << 1) & 0xFF",                  # SLA
        "c = v & 1; r = (v >> 1) | (v & 0x80)",             # SRA
        "c = v >> 7; r = ((v << 1) | 1) & 0xFF",            # SLL (undocumented)
        "c = v & 1; r = v >> 1")                            # SRL


def _gen_main(op, ctx):
    """Body lines for unprefixed opcode op, with HL replaced by ctx (HL / IX / IY).
    Returns None for the prefix bytes (CB DD ED FD), which are wired up separately."""
    x, y, z, p, q = op >> 6, (op >> 3) & 7, op & 7, (op >> 4) & 3, (op >> 3) & 1
    ix = ctx != "HL"
    extra = 4 if ix else 0          # DD/FD prefix costs 4 more T-states
    HL = _get16(2, ctx)

    if x == 0:
        if z == 0:
            if y == 0:
                return ["return 4"]                                        # NOP
            if y == 1:
                return ["self.A, self.A_ = self.A_, self.A",                # EX AF,AF'
                        "self.F, self.F_ = self.F_, self.F", "return 4"]
            if y == 2:
                return ["b = (self.B - 1) & 0xFF; self.B = b; pc = self.PC",  # DJNZ e
                        "if b: self.PC = (pc + 1 + SIGNED[mem[pc]]) & 0xFFFF; return 13",
                        "self.PC = (pc + 1) & 0xFFFF", "return 8"]
            if y == 3:
                return ["pc = self.PC; self.PC = (pc + 1 + SIGNED[mem[pc]]) & 0xFFFF", "return 12"]  # JR e
            return ["pc = self.PC",                                          # JR cc,e
                    f"if {_CC[y - 4]}: self.PC = (pc + 1 + SIGNED[mem[pc]]) & 0xFFFF; return 12",
                    "self.PC = (pc + 1) & 0xFFFF", "return 7"]
        if z == 1:
            if q == 0:                                                       # LD rp,nn
                return [FETCH16, _set16(p, ctx, "nn"), f"return {10 + extra}"]
            return [f"hl = {HL}; v = {_get16(p, ctx)}; r = hl + v",          # ADD HL,rp
                    "self.F = (self.F & 0xC4) | ((r >> 8) & 0x28) | (((hl ^ v ^ r) >> 8) & 0x10) | (r >> 16)",
                    "r &= 0xFFFF", _set16(2, ctx, "r"), f"return {11 + extra}"]
        if z == 2:
            if p == 0:
                return ["wr((self.B << 8) | self.C, self.A)" if q == 0 else "self.A = mem[(self.B << 8) | self.C]",
                        "return 7"]
            if p == 1:
                return ["wr((self.D << 8) | self.E, self.A)" if q == 0 else "self.A = mem[(self.D << 8) | self.E]",
                        "return 7"]
            if p == 2:
                if q == 0:                                                   # LD (nn),HL
                    return [FETCH16, f"t = {HL}; wr(nn, t & 0xFF); wr((nn + 1) & 0xFFFF, t >> 8)",
                            f"return {16 + extra}"]
                return [FETCH16, "v = mem[nn] | (mem[(nn + 1) & 0xFFFF] << 8)",  # LD HL,(nn)
                        _set16(2, ctx, "v"), f"return {16 + extra}"]
            return [FETCH16, "wr(nn, self.A)" if q == 0 else "self.A = mem[nn]", "return 13"]
        if z == 3:                                                           # INC/DEC rp
            return [f"v = ({_get16(p, ctx)} {'+' if q == 0 else '-'} 1) & 0xFFFF", _set16(p, ctx, "v"),
                    f"return {6 + extra}"]
        if z in (4, 5):                                                      # INC/DEC r
            tbl = "INCF" if z == 4 else "DECF"
            sign = "+" if z == 4 else "-"
            if y == 6:
                return [_addr(ctx), f"r = (mem[addr] {sign} 1) & 0xFF; wr(addr, r)",
                        f"self.F = (self.F & 1) | {tbl}[r]", f"return {23 if ix else 11}"]
            return [f"r = ({_get8(y, ctx)} {sign} 1) & 0xFF", _set8(y, ctx, "r"),
                    f"self.F = (self.F & 1) | {tbl}[r]", f"return {4 + extra}"]
        if z == 6:                                                           # LD r,n
            if y == 6:
                return [_addr(ctx), FETCH8, "wr(addr, n)", f"return {19 if ix else 10}"]
            return [FETCH8, _set8(y, ctx, "n"), f"return {7 + extra}"]
        # z == 7: accumulator / flag operations
        return ({
            0: ["a = self.A; a = ((a << 1) | (a >> 7)) & 0xFF; self.A = a",            # RLCA
                "self.F = (self.F & 0xC4) | (a & 0x29)"],
            1: ["a = self.A; c = a & 1; a = (a >> 1) | (c << 7); self.A = a",          # RRCA
                "self.F = (self.F & 0xC4) | (a & 0x28) | c"],
            2: ["a = self.A; c = a >> 7; a = ((a << 1) | (self.F & 1)) & 0xFF; self.A = a",  # RLA
                "self.F = (self.F & 0xC4) | (a & 0x28) | c"],
            3: ["a = self.A; c = a & 1; a = (a >> 1) | ((self.F & 1) << 7); self.A = a",    # RRA
                "self.F = (self.F & 0xC4) | (a & 0x28) | c"],
            4: ["a = self.A; f = self.F; corr = 0; c = f & 1",                           # DAA
                "if (f & 0x10) or (a & 0x0F) > 9: corr = 0x06",
                "if c or a > 0x99: corr |= 0x60; c = 1",
                "if f & 0x02: r = (a - corr) & 0xFF; h = 0x10 if (f & 0x10) and (a & 0x0F) < 6 else 0",
                "else: r = (a + corr) & 0xFF; h = 0x10 if (a & 0x0F) > 9 else 0",
                "self.A = r; self.F = SZ53P[r] | h | (f & 0x02) | c"],
            5: ["a = self.A ^ 0xFF; self.A = a; self.F = (self.F & 0xC5) | 0x12 | (a & 0x28)"],  # CPL
            6: ["self.F = (self.F & 0xC4) | 0x01 | (self.A & 0x28)"],                     # SCF
            7: ["f = self.F; self.F = ((f & 0xC5) | ((f & 1) << 4) | (self.A & 0x28)) ^ 0x01"],  # CCF
        }[y] + ["return 4"])

    if x == 1:
        if y == 6 and z == 6:                                                # HALT
            return ["self.PC = (self.PC - 1) & 0xFFFF; self.halted = True", "return 4"]
        # With an (HL)/(IX+d) operand the other register is always the real H/L
        if y == 6:
            return [_addr(ctx), f"wr(addr, {_get8(z, 'HL')})", f"return {19 if ix else 7}"]
        if z == 6:
            return [_addr(ctx), _set8(y, "HL", "mem[addr]"), f"return {19 if ix else 7}"]
        return [_set8(y, ctx, _get8(z, ctx)), f"return {4 + extra}"]         # LD r,r'

    if x == 2:                                                               # ALU A,r
        if z == 6:
            return [_addr(ctx), "v = mem[addr]"] + _alu(y) + [f"return {19 if ix else 7}"]
        return [f"v = {_get8(z, ctx)}"] + _alu(y) + [f"return {4 + extra}"]

    # x == 3
    if z == 0:                                                               # RET cc
        return [f"if {_CC[y]}: {POP}; self.PC = v; return 11", "return 5"]
    if z == 1:
        if q == 0:                                                           # POP rp2
            return [POP, _set16(p, ctx, "v", af=True), f"return {10 + extra}"]
        if p == 0:
            return [POP, "self.PC = v", "return 10"]                          # RET
        if p == 1:
            return ["self.B, self.B_ = self.B_, self.B; self.C, self.C_ = self.C_, self.C",  # EXX
                    "self.D, self.D_ = self.D_, self.D; self.E, self.E_ = self.E_, self.E",
                    "self.H, self.H_ = self.H_, self.H; self.L, self.L_ = self.L_, self.L", "return 4"]
        if p == 2:
            return [f"self.PC = {HL}", f"return {4 + extra}"]                 # JP (HL)
        return [f"self.SP = {HL}", f"return {6 + extra}"]                     # LD SP,HL
    if z == 2:                                                               # JP cc,nn
        return [FETCH16, f"if {_CC[y]}: self.PC = nn", "return 10"]
    if z == 3:
        if y == 0:
            return [FETCH16, "self.PC = nn", "return 10"]                     # JP nn
        if y == 1:
            return None                                                      # CB prefix
        if y == 2:
            return [FETCH8, "pout(n, self.A)", "return 11"]                   # OUT (n),A
        if y == 3:
            return [FETCH8, "self.A = pin(n)", "return 11"]                   # IN A,(n)
        if y == 4:                                                           # EX (SP),HL
            return ["sp = self.SP; v = mem[sp] | (mem[(sp + 1) & 0xFFFF] << 8)",
                    f"t = {HL}; wr(sp, t & 0xFF); wr((sp + 1) & 0xFFFF, t >> 8)",
                    _set16(2, ctx, "v"), f"return {19 + extra}"]
        if y == 5:                                                           # EX DE,HL (never IX)
            return ["self.D, self.H = self.H, self.D; self.E, self.L = self.L, self.E", "return 4"]
        if y == 6:
            return ["self.iff1 = self.iff2 = False", "return 4"]              # DI
        return ["self.iff1 = self.iff2 = True", "return 4"]                   # EI
    if z == 4:                                                               # CALL cc,nn
        return [FETCH16, f"if {_CC[y]}: {_push('self.PC')}; self.PC = nn; return 17", "return 10"]
    if z == 5:
        if q == 0:                                                           # PUSH rp2
            return [_push(_get16(p, ctx, af=True)), f"return {11 + extra}"]
        if p == 0:
            return [FETCH16, _push("self.PC"), "self.PC = nn", "return 17"]   # CALL nn
        return None                                                          # DD / ED / FD prefixes
    if z == 6:                                                               # ALU A,n
        return [FETCH8, "v = n"] + _alu(y) + ["return 7"]
    return [_push("self.PC"), f"self.PC = {y * 8}", "return 11"]              # RST


def _gen_cb(op, indexed):
    """Body lines for CB-prefixed op. indexed=True builds the DDCB/FDCB form, whose
    handler receives the already computed (IX+d)/(IY+d) address as parameter 'addr'."""
    x, y, z = op >> 6, (op >> 3) & 7, op & 7
    mem_op = indexed or z == 6
    lines = []
    if mem_op:
        if not indexed:
            lines.append(_addr("HL"))
        lines.append("v = mem[addr]")
    else:
        lines.append(f"v = self.{_R8[z]}")

    if x == 1:                                                               # BIT y,r
        mask = 1 << y
        # X/Y come from the operand for registers, from the address high byte for memory
        xy = "((addr >> 8) & 0x28)" if mem_op else "(v & 0x28)"
        lines.append(f"b = v & {mask}; f = (self.F & 0x01) | 0x10 | {xy}")
        lines.append("if not b: f |= 0x44")
        if y == 7:
            lines.append("if b: f |= 0x80")
        lines.append("self.F = f")
        lines.append(f"return {20 if indexed else (12 if mem_op else 8)}")
        return lines

    if x == 0:                                                               # rotate / shift
        lines += [_ROT[y], "self.F = SZ53P[r] | c"]
    elif x == 2:                                                             # RES y,r
        lines.append(f"r = v & {0xFF ^ (1 << y)}")
    else:                                                                    # SET y,r
        lines.append(f"r = v | {1 << y}")

    if mem_op:
        lines.append("wr(addr, r)")
        if indexed and z != 6:
            lines.append(f"self.{_R8[z]} = r")      # undocumented: result also copied to a register
    else:
        lines.append(f"self.{_R8[z]} = r")
    lines.append(f"return {23 if indexed else (15 if mem_op else 8)}")
    return lines


_BLOCK_STEP = {"I": "+", "D": "-"}


def _gen_ed(op):
    """Body lines for ED-prefixed op (cycle counts include the ED prefix)."""
    x, y, z, p, q = op >> 6, (op >> 3) & 7, op & 7, (op >> 4) & 3, (op >> 3) & 1
    if x == 1:
        if z == 0:                                                           # IN r,(C)
            lines = ["v = pin(self.C)"]
            if y != 6:
                lines.append(f"self.{_R8[y]} = v")
            return lines + ["self.F = (self.F & 1) | SZ53P[v]", "return 12"]
        if z == 1:                                                           # OUT (C),r
            return [f"pout(self.C, {'0' if y == 6 else 'self.' + _R8[y]})", "return 12"]
        if z == 2:
            hl = _get16(2, "HL")
            if q == 0:                                                       # SBC HL,rp
                return [f"hl = {hl}; v = {_get16(p, 'HL')}; r = hl - v - (self.F & 1)",
                        "self.F = ((r >> 8) & 0xA8) | (0x40 if (r & 0xFFFF) == 0 else 0)"
                        " | (((hl ^ v ^ r) >> 8) & 0x10) | ((((hl ^ v) & (hl ^ r)) >> 13) & 0x04)"
                        " | 0x02 | ((r >> 16) & 1)",
                        "r &= 0xFFFF", _set16(2, "HL", "r"), "return 15"]
            return [f"hl = {hl}; v = {_get16(p, 'HL')}; r = hl + v + (self.F & 1)",    # ADC HL,rp
                    "self.F = ((r >> 8) & 0xA8) | (0x40 if (r & 0xFFFF) == 0 else 0)"
                    " | (((hl ^ v ^ r) >> 8) & 0x10) | ((((hl ^ r) & (v ^ r)) >> 13) & 0x04)"
                    " | ((r >> 16) & 1)",
                    "r &= 0xFFFF", _set16(2, "HL", "r"), "return 15"]
        if z == 3:
            if q == 0:                                                       # LD (nn),rp
                return [FETCH16, f"v = {_get16(p, 'HL')}; wr(nn, v & 0xFF); wr((nn + 1) & 0xFFFF, v >> 8)",
                        "return 20"]
            return [FETCH16, "v = mem[nn] | (mem[(nn + 1) & 0xFFFF] << 8)", _set16(p, "HL", "v"),
                    "return 20"]                                             # LD rp,(nn)
        if z == 4:                                                           # NEG
            return ["v = self.A; a = 0; r = -v", _SUB_FLAGS, "self.A = r & 0xFF", "return 8"]
        if z == 5:                                                           # RETN / RETI
            return ["self.iff1 = self.iff2", POP, "self.PC = v", "return 14"]
        if z == 6:                                                           # IM 0/1/2
            return [f"self.im = {(0, 0, 1, 2)[y & 3]}", "return 8"]
        return ({
            0: ["self.I = self.A", "return 9"],                                       # LD I,A
            1: ["self.R = self.A & 0x7F; self.R7 = self.A & 0x80", "return 9"],       # LD R,A
            2: ["a = self.I; self.A = a",                                             # LD A,I
                "self.F = (self.F & 1) | SZ53[a] | (0x04 if self.iff2 else 0)", "return 9"],
            3: ["a = (self.R & 0x7F) | self.R7; self.A = a",                         # LD A,R
                "self.F = (self.F & 1) | SZ53[a] | (0x04 if self.iff2 else 0)", "return 9"],
            4: [_addr("HL"), "m = mem[addr]; a = self.A",                            # RRD
                "wr(addr, ((a << 4) | (m >> 4)) & 0xFF); a = (a & 0xF0) | (m & 0x0F)",
                "self.A = a; self.F = (self.F & 1) | SZ53P[a]", "return 18"],
            5: [_addr("HL"), "m = mem[addr]; a = self.A",                            # RLD
                "wr(addr, ((m << 4) | (a & 0x0F)) & 0xFF); a = (a & 0xF0) | (m >> 4)",
                "self.A = a; self.F = (self.F & 1) | SZ53P[a]", "return 18"],
        }).get(y, ["return 8"])

    if x == 2 and y >= 4 and z <= 3:                                         # block instructions
        s = "+" if (y & 1) == 0 else "-"            # LDI/CPI/INI/OUTI vs the D variants
        repeat = y >= 6                             # ...R variants loop by re-executing
        hl_load = "hl = (self.H << 8) | self.L"
        hl_store = f"hl = (hl {s} 1) & 0xFFFF; self.H = hl >> 8; self.L = hl & 0xFF"
        bc_dec = "bc = (((self.B << 8) | self.C) - 1) & 0xFFFF; self.B = bc >> 8; self.C = bc & 0xFF"
        again = "self.PC = (self.PC - 2) & 0xFFFF; return 21"
        if z == 0:                                                           # LDI / LDD / LDIR / LDDR
            lines = [hl_load, "de = (self.D << 8) | self.E", "v = mem[hl]; wr(de, v)", hl_store,
                     f"de = (de {s} 1) & 0xFFFF; self.D = de >> 8; self.E = de & 0xFF", bc_dec,
                     "n = v + self.A",
                     "self.F = (self.F & 0xC1) | (0x04 if bc else 0) | (n & 0x08) | ((n << 4) & 0x20)"]
            cond = "bc"
        elif z == 1:                                                         # CPI / CPD / CPIR / CPDR
            lines = [hl_load, "v = mem[hl]; a = self.A; r = (a - v) & 0xFF; h = (a ^ v ^ r) & 0x10",
                     hl_store, bc_dec, "n = r - (h >> 4)",
                     "self.F = (self.F & 0x01) | 0x02 | h | (SZ53[r] & 0xC0) | (0x04 if bc else 0)"
                     " | (n & 0x08) | ((n << 4) & 0x20)"]
            cond = "bc and r"
        elif z == 2:                                                         # INI / IND / INIR / INDR
            lines = [hl_load, "v = pin(self.C); wr(hl, v)", hl_store,
                     "b = (self.B - 1) & 0xFF; self.B = b", "self.F = (self.F & 0x01) | SZ53[b] | 0x02"]
            cond = "b"
        else:                                                                # OUTI / OUTD / OTIR / OTDR
            lines = [hl_load, "v = mem[hl]; b = (self.B - 1) & 0xFF; self.B = b; pout(self.C, v)",
                     hl_store, "self.F = (self.F & 0x01) | SZ53[b] | 0x02"]
            cond = "b"
        if repeat:
            lines.append(f"if {cond}: {again}")
        return lines + ["return 16"]

    return ["return 8"]                                                      # undefined ED xx = NOP


def _build_factory_source():
    """Assemble the source of _factory(), which creates every opcode handler as a
    closure and returns the dispatch tables (MAIN, CB, ED, DD, FD, XCB)."""
    out = ["def _factory(self, mem, wr, pin, pout, SZ53, SZ53P, INCF, DECF, SIGNED):"]

    def emit(name, body, params=""):
        out.append(f"    def {name}({params}):")
        out.extend("        " + line for line in body)

    names = {"MAIN": [], "CB": [], "ED": [], "DD": [], "FD": [], "XCB": []}
    for op in range(256):
        body = _gen_main(op, "HL")
        if body is None:
            prefix = {0xCB: "CB", 0xDD: "DD", 0xED: "ED", 0xFD: "FD"}[op]
            body = ["pc = self.PC; self.PC = (pc + 1) & 0xFFFF; self.R += 1",
                    f"return {prefix}[mem[pc]]()"]
        emit(f"m_{op:02x}", body)
        names["MAIN"].append(f"m_{op:02x}")

        emit(f"cb_{op:02x}", _gen_cb(op, False))
        names["CB"].append(f"cb_{op:02x}")
        emit(f"xcb_{op:02x}", _gen_cb(op, True), "addr")
        names["XCB"].append(f"xcb_{op:02x}")
        emit(f"ed_{op:02x}", _gen_ed(op))
        names["ED"].append(f"ed_{op:02x}")

        for ctx, tbl in (("IX", "DD"), ("IY", "FD")):
            name = f"{tbl.lower()}_{op:02x}"
            if op == 0xCB:                       # DD CB d op / FD CB d op
                body = [f"pc = self.PC; addr = (self.{ctx} + SIGNED[mem[pc]]) & 0xFFFF",
                        "op = mem[(pc + 1) & 0xFFFF]; self.PC = (pc + 2) & 0xFFFF",
                        "return XCB[op](addr)"]
            elif op in (0xDD, 0xED, 0xFD):       # prefix followed by prefix: first acts as a NOP
                body = ["self.PC = (self.PC - 1) & 0xFFFF; self.R -= 1", "return 4"]
            else:
                body = _gen_main(op, ctx)
                if body == _gen_main(op, "HL"):  # opcode doesn't use HL: same as unprefixed + 4
                    body = [f"return m_{op:02x}() + 4"]
            emit(name, body)
            names[tbl].append(name)

    for tbl, lst in names.items():
        out.append(f"    {tbl} = [{', '.join(lst)}]")
    out.append("    return MAIN, CB, ED, DD, FD, XCB")
    return "\n".join(out) + "\n"


_ns = {}
exec(compile(_build_factory_source(), "<z80-generated>", "exec"), _ns)
_FACTORY = _ns["_factory"]
del _ns


class Cpu:
    CLOCK_HZ = 3072000      # Pac-Man Z80 clock (18.432 MHz / 6)

    def __init__(self):
        self.cpuUtil = Util()
        self.cpuMemory = None
        self.cpuIo = None
        self.mem = None
        self._main = None
        self.halted = False
        self.reset()

    def init(self, m, io) -> bool:
        """Attach memory (get_memory_ptr() / write()) and I/O (input_port() / output_port())."""
        self.cpuMemory = m
        self.cpuIo = io
        self.mem = m.get_memory_ptr()
        (self._main, self._cb, self._ed,
         self._dd, self._fd, self._xcb) = _FACTORY(self, self.mem, m.write, io.input_port, io.output_port,
                                                   SZ53, SZ53P, INCF, DECF, SIGNED)
        self.reset()
        return True

    def reset(self):
        """Power-on / reset state."""
        self.A = self.F = 0xFF
        self.B = self.C = self.D = self.E = self.H = self.L = 0
        self.A_ = self.F_ = self.B_ = self.C_ = self.D_ = self.E_ = self.H_ = self.L_ = 0
        self.IX = self.IY = 0xFFFF
        self.SP = 0xFFFF
        self.PC = 0
        self.I = 0
        self.R = 0          # low 7 bits of the refresh register (masked when read)
        self.R7 = 0         # bit 7 of R, only changed by LD R,A
        self.iff1 = False   # interrupts enabled
        self.iff2 = False   # copy of iff1 saved during an NMI
        self.im = 0         # interrupt mode 0 / 1 / 2
        self.halted = False

    def run(self, cycles: int) -> int:
        """Execute instructions until at least `cycles` T-states have elapsed.
        Returns the number of T-states actually executed (may overshoot slightly)."""
        mem = self.mem
        table = self._main
        done = 0
        while done < cycles:
            pc = self.PC
            self.PC = (pc + 1) & 0xFFFF
            self.R += 1
            done += table[mem[pc]]()
        self.R &= 0x7F
        return done

    def step(self) -> int:
        """Execute a single instruction and return the T-states it took."""
        return self.run(1)

    def _push_pc(self):
        sp = (self.SP - 2) & 0xFFFF
        self.SP = sp
        self.cpuMemory.write((sp + 1) & 0xFFFF, self.PC >> 8)
        self.cpuMemory.write(sp, self.PC & 0xFF)

    def _leave_halt(self):
        if self.halted:
            self.halted = False
            self.PC = (self.PC + 1) & 0xFFFF   # HALT re-executes itself, so step past it

    def interrupt(self, data_bus: int = 0) -> int:
        """Signal a maskable interrupt; data_bus is the byte the hardware places on the bus.
        Returns T-states used (0 if interrupts are disabled)."""
        if not self.iff1:
            return 0
        self._leave_halt()
        self.iff1 = self.iff2 = False
        self.R = (self.R + 1) & 0x7F
        self._push_pc()
        if self.im == 2:
            # Vector table address: I register (high byte) + data bus (low byte)
            addr = (self.I << 8) | (data_bus & 0xFF)
            self.PC = self.mem[addr] | (self.mem[(addr + 1) & 0xFFFF] << 8)
            return 19
        if self.im == 1:
            self.PC = 0x0038
            return 13
        # Mode 0: the data bus holds an instruction; only RST n is supported (as in the C# CPU)
        self.PC = data_bus & 0x38 if (data_bus & 0xC7) == 0xC7 else 0x0038
        return 13

    def nmi(self) -> int:
        """Signal a non-maskable interrupt (CALL 0x0066)."""
        self._leave_halt()
        self.iff2 = self.iff1
        self.iff1 = False
        self.R = (self.R + 1) & 0x7F
        self._push_pc()
        self.PC = 0x0066
        return 11

    def get_debug_output(self) -> str:
        u = self.cpuUtil
        return (f"PC={u.hword(self.PC)} SP={u.hword(self.SP)} AF={u.hbyte(self.A)}{u.hbyte(self.F)} "
                f"BC={u.hbyte(self.B)}{u.hbyte(self.C)} DE={u.hbyte(self.D)}{u.hbyte(self.E)} "
                f"HL={u.hbyte(self.H)}{u.hbyte(self.L)} IX={u.hword(self.IX)} IY={u.hword(self.IY)} "
                f"I={u.hbyte(self.I)} IM={self.im} IFF={int(self.iff1)}")

    def free(self):
        self._main = self._cb = self._ed = self._dd = self._fd = self._xcb = None
        self.mem = None
