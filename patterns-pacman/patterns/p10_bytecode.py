"""
Pattern 10 of 19 - BYTECODE
===========================
Book: "Behavioral Patterns > Bytecode"
      https://gameprogrammingpatterns.com/bytecode.html

  "Give behavior the flexibility of data by encoding it as instructions for a
   virtual machine."

THE PROBLEM (book sections "Spell fight!" / "Data > code")
    Each ghost has a *personality*: the rule it uses to pick its target tile
    while chasing. In the arcade:
      * Blinky targets Pac-Man's tile.
      * Pinky targets 4 tiles in front of Pac-Man (an ambush).
      * Inky takes the point 2 tiles ahead of Pac-Man and doubles the vector
        from Blinky to it: he works with Blinky.
      * Clyde chases like Blinky when far away, but when he gets within 8
        tiles he gets shy and heads back to his corner.
    Hard-coding these in Python means a designer can't tweak or invent a
    ghost without a programmer. We want behaviour to be *data*, but data
    that is safe to run (it can't crash the game or loop forever).

THE PATTERN (book section "The Pattern")
    An *instruction set* defines the low-level operations; a series of
    instructions is encoded as a *sequence of bytes*; a *virtual machine*
    executes them one at a time using a *stack* for intermediate values.
    The ghosts' programs live in data/breeds.json as readable assembly text.
    The tiny ``assemble`` function turns that into bytes when the game loads.

THE INSTRUCTION SET (book section "A magical instruction set")
    Queries ("A magical API": the VM can only see what we expose):
        PAC_X PAC_Y      Pac-Man's tile            -> push 1 value each
        PAC_DX PAC_DY    Pac-Man's heading (-1/0/1)
        SELF_X SELF_Y    this ghost's tile
        BLINKY_X BLINKY_Y  Blinky's tile (for Inky)
        CORNER_X CORNER_Y  this ghost's scatter corner
    Values and arithmetic ("A stack machine" / "Behavior = composition"):
        LIT n            push the literal byte n (0..255)
        ADD SUB MUL      pop b, pop a, push a op b
        DIST2            pop 4 values (x1 y1 x2 y2), push squared distance
        GREATER LESS     pop b, pop a, push 1 or 0
    Control flow:
        JUMP label       continue at label
        JUMP_IF_FALSE label   pop v; jump if v == 0
        HALT             stop
    Output:
        SET_TARGET       pop y, pop x: the ghost's target tile

    Example: Pinky (target = Pac-Man + 4 * heading)
        PAC_X  PAC_DX  LIT 4  MUL  ADD      ; x
        PAC_Y  PAC_DY  LIT 4  MUL  ADD      ; y
        SET_TARGET

WHERE IT IS USED IN THE GAME
    The Chase state (p06) asks ``ghost.chase_target()``, which runs the
    breed's bytecode on the VM below (p13_component.py: GhostBrain). Want a
    new ghost personality? Edit data/breeds.json, no Python needed.

KEEP IN MIND (book section "Keep in Mind")
    * "You'll need a front-end": nobody writes bytes by hand. ``assemble``
      is our (very small) front-end, with error messages that include the
      line number ("Spellcasting tools").
    * "You'll miss your debugger": ``disassemble`` turns bytes back into
      text so you can see what the VM is running (try it in a Python shell).
    * Safety: the VM limits the stack depth and the number of instructions
      per run, so bad data can't hang the game.

DESIGN DECISIONS (book section "Design Decisions")
    * Stack-based, not register-based ("How do instructions access the stack?").
    * Values are plain integers ("How are values represented?"): enough for
      tile maths.
    * The bytecode is produced by an assembler, not a GUI tool ("How is the
      bytecode generated?").
"""
from enum import IntEnum


class Op(IntEnum):
    HALT = 0
    LIT = 1
    PAC_X = 2
    PAC_Y = 3
    PAC_DX = 4
    PAC_DY = 5
    SELF_X = 6
    SELF_Y = 7
    BLINKY_X = 8
    BLINKY_Y = 9
    CORNER_X = 10
    CORNER_Y = 11
    ADD = 12
    SUB = 13
    MUL = 14
    DIST2 = 15
    GREATER = 16
    LESS = 17
    JUMP = 18
    JUMP_IF_FALSE = 19
    SET_TARGET = 20


# Instructions followed by a one-byte operand.
_HAS_OPERAND = {Op.LIT, Op.JUMP, Op.JUMP_IF_FALSE}


class BytecodeError(Exception):
    pass


# ---------------------------------------------------------------------------
# The front-end: assembly text -> bytes
# ---------------------------------------------------------------------------
def assemble(source) -> bytes:
    """Assemble text (a string or a list of lines) into bytecode.

    Syntax: one or more instructions per line, ``;`` starts a comment,
    ``name:`` defines a label usable by JUMP / JUMP_IF_FALSE.
    """
    lines = source.splitlines() if isinstance(source, str) else list(source)
    tokens = []                           # (line number, word)
    for number, line in enumerate(lines, 1):
        for word in line.split(";", 1)[0].split():
            tokens.append((number, word))

    # Pass 1: work out the address of every label.
    labels, address, i = {}, 0, 0
    while i < len(tokens):
        number, word = tokens[i]
        if word.endswith(":"):
            labels[word[:-1].lower()] = address
            i += 1
            continue
        op = _opcode(word, number)
        address += 2 if op in _HAS_OPERAND else 1
        i += 2 if op in _HAS_OPERAND else 1

    # Pass 2: emit bytes.
    code, i = bytearray(), 0
    while i < len(tokens):
        number, word = tokens[i]
        if word.endswith(":"):
            i += 1
            continue
        op = _opcode(word, number)
        code.append(op)
        if op in _HAS_OPERAND:
            if i + 1 >= len(tokens):
                raise BytecodeError(f"line {number}: {word} needs an operand")
            operand_line, operand = tokens[i + 1]
            if op == Op.LIT:
                value = _int(operand, operand_line)
            else:
                if operand.lower() not in labels:
                    raise BytecodeError(f"line {operand_line}: unknown label '{operand}'")
                value = labels[operand.lower()]
            if not 0 <= value <= 255:
                raise BytecodeError(f"line {operand_line}: operand {value} is not a byte")
            code.append(value)
            i += 2
        else:
            i += 1
    return bytes(code)


def _opcode(word: str, number: int) -> Op:
    try:
        return Op[word.upper()]
    except KeyError:
        raise BytecodeError(f"line {number}: unknown instruction '{word}'") from None


def _int(word: str, number: int) -> int:
    try:
        return int(word)
    except ValueError:
        raise BytecodeError(f"line {number}: '{word}' is not a number") from None


def disassemble(code: bytes):
    """Bytes -> readable lines (the debugger you'd otherwise miss)."""
    out, pc = [], 0
    while pc < len(code):
        op = Op(code[pc])
        if op in _HAS_OPERAND:
            out.append(f"{pc:3d}  {op.name} {code[pc + 1]}")
            pc += 2
        else:
            out.append(f"{pc:3d}  {op.name}")
            pc += 1
    return out


# ---------------------------------------------------------------------------
# The virtual machine
# ---------------------------------------------------------------------------
class VM:
    """A small stack machine. ``api`` is the window into the game world.

    ``api`` must provide: pacman_tile(), pacman_heading(), self_tile(),
    blinky_tile(), corner() (each returning an (x, y) pair) and
    set_target(x, y).
    """
    MAX_STACK = 32
    MAX_STEPS = 256

    def __init__(self):
        self.stack = []
        self.instructions_run = 0     # total, for the side panel

    def _push(self, value: int) -> None:
        if len(self.stack) >= self.MAX_STACK:
            raise BytecodeError("stack overflow")
        self.stack.append(int(value))

    def _pop(self) -> int:
        if not self.stack:
            raise BytecodeError("stack underflow")
        return self.stack.pop()

    def interpret(self, code: bytes, api) -> int:
        """Run ``code`` to the end (or HALT). Returns the instructions executed."""
        self.stack.clear()
        pc, steps = 0, 0
        push, pop = self._push, self._pop
        while pc < len(code):
            steps += 1
            if steps > self.MAX_STEPS:
                raise BytecodeError("program ran too long (infinite loop?)")
            op = code[pc]
            pc += 1
            if op == Op.HALT:
                break
            elif op == Op.LIT:
                push(code[pc])
                pc += 1
            elif op == Op.PAC_X:
                push(api.pacman_tile()[0])
            elif op == Op.PAC_Y:
                push(api.pacman_tile()[1])
            elif op == Op.PAC_DX:
                push(api.pacman_heading()[0])
            elif op == Op.PAC_DY:
                push(api.pacman_heading()[1])
            elif op == Op.SELF_X:
                push(api.self_tile()[0])
            elif op == Op.SELF_Y:
                push(api.self_tile()[1])
            elif op == Op.BLINKY_X:
                push(api.blinky_tile()[0])
            elif op == Op.BLINKY_Y:
                push(api.blinky_tile()[1])
            elif op == Op.CORNER_X:
                push(api.corner()[0])
            elif op == Op.CORNER_Y:
                push(api.corner()[1])
            elif op in (Op.ADD, Op.SUB, Op.MUL, Op.GREATER, Op.LESS):
                b, a = pop(), pop()
                if op == Op.ADD:
                    push(a + b)
                elif op == Op.SUB:
                    push(a - b)
                elif op == Op.MUL:
                    push(a * b)
                elif op == Op.GREATER:
                    push(1 if a > b else 0)
                else:
                    push(1 if a < b else 0)
            elif op == Op.DIST2:
                y2, x2, y1, x1 = pop(), pop(), pop(), pop()
                push((x1 - x2) ** 2 + (y1 - y2) ** 2)
            elif op == Op.JUMP:
                pc = code[pc]
            elif op == Op.JUMP_IF_FALSE:
                target = code[pc]
                pc = target if pop() == 0 else pc + 1
            elif op == Op.SET_TARGET:
                y, x = pop(), pop()
                api.set_target(x, y)
            else:
                raise BytecodeError(f"bad opcode {op} at {pc - 1}")
        self.instructions_run += steps
        return steps
