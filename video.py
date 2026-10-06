# Python port of the C# VideoHardware, TileRenderer and SpriteRenderer classes
#
# The Pac-Man screen is 224x288 visible (256x288 rendered, the outer 16 pixel
# columns are masked) and is built from:
#   * 36 rows x 28 columns of 8x8 tiles (tile numbers at 0x4000, palettes at 0x4400)
#   * 8 hardware sprites of 16x16 (numbers/flags at 0x4FF0, coordinates at 0x5060)
# Each tile/sprite pixel is 2 bits, looked up through a 4 colour palette (palette
# PROM) which indexes the 32 entry colour PROM.
import re
import pygame
from core.graphics import Graphics
from core.outline_font import OutlineFont
from memory import Memory
from roms import RomData, MSPACMAN

RESOLUTION_WIDTH = 256
RESOLUTION_HEIGHT = 288
SCALE = 2
PAC_SCREEN_W = RESOLUTION_WIDTH * SCALE
PAC_SCREEN_H = RESOLUTION_HEIGHT * SCALE


# --- ROM decoding (pure functions, used by the tests too) --------------------

def decode_colors(color_rom):
    """32 colour PROM bytes -> list of (r, g, b). Resistor weighted 3/3/2 bit RGB."""
    colors = []
    for c in color_rom:
        r = (0x21 if c & 0x01 else 0) + (0x47 if c & 0x02 else 0) + (0x97 if c & 0x04 else 0)
        g = (0x21 if c & 0x08 else 0) + (0x47 if c & 0x10 else 0) + (0x97 if c & 0x20 else 0)
        b = (0x51 if c & 0x40 else 0) + (0xAE if c & 0x80 else 0)
        colors.append((r, g, b))
    return colors


def decode_palettes(palette_rom, colors):
    """256 palette PROM bytes -> 64 palettes of 4 (r, g, b) colours."""
    return [[colors[palette_rom[i + j] & 0x1F] for j in range(4)] for i in range(0, len(palette_rom), 4)]


def _strip_pixels(byte):
    """The 4 vertically stacked 2-bit pixels (top to bottom) stored in one graphics byte."""
    p1 = ((byte & 0x10) >> 3) | (byte & 0x01)
    p2 = ((byte & 0x20) >> 4) | ((byte & 0x02) >> 1)
    p3 = ((byte & 0x40) >> 5) | ((byte & 0x04) >> 2)
    p4 = ((byte & 0x80) >> 6) | ((byte & 0x08) >> 3)
    return p4, p3, p2, p1


def decode_tile(tile_rom, index):
    """Tile number -> 64 colour indices (row major, 8x8)."""
    pixels = [0] * 64
    start = index * 16
    x, y = 0, 0
    for i in range(start + 15, start - 1, -1):
        for dy, p in enumerate(_strip_pixels(tile_rom[i])):
            pixels[(y + dy) * 8 + x] = p
        if x == 7:
            x, y = 0, 4
        else:
            x += 1
    return pixels


_SPRITE_GROUP_ORDER = (5, 1, 6, 2, 7, 3, 4, 0)


def decode_sprite(sprite_rom, index):
    """Sprite number -> 256 colour indices (row major, 16x16)."""
    pixels = [0] * 256
    x, y = 0, 0
    for group in _SPRITE_GROUP_ORDER:
        start = index * 64 + group * 8
        for i in range(start + 7, start - 1, -1):
            for dy, p in enumerate(_strip_pixels(sprite_rom[i])):
                pixels[(y + dy) * 16 + x] = p
            if x == 15:
                x, y = 0, y + 4
            else:
                x += 1
    return pixels


def _build_tile_layout():
    """(video RAM offset, x, y) of every visible tile, in the order of the C# renderer."""
    cells = []
    # Playfield: offsets 0x040-0x3BF run top to bottom, right to left, from column 29
    x, y = 29 * 8, 2 * 8
    row = 1
    for i in range(0x040, 0x3C0):
        cells.append((i, x, y))
        if row == 32:
            x, y, row = x - 8, 2 * 8, 1
        else:
            y, row = y + 8, row + 1
    # Top two rows (scores) and bottom two rows (lives, fruit): right to left
    for first, last, y in ((0x3DF, 0x3C0, 0), (0x3FF, 0x3E0, 8), (0x01F, 0x000, 34 * 8), (0x03F, 0x020, 35 * 8)):
        for n, i in enumerate(range(first, last - 1, -1)):
            cells.append((i, n * 8, y))
    return cells


TILE_LAYOUT = _build_tile_layout()


class Video:
    def __init__(self):
        self.X = 20
        self.Y = 40
        self.gVideo = None
        self.videoOutlineFont = OutlineFont()
        self.videoMemory = None
        self.videoMemoryPtr = None
        self.videoIo = None
        self.title = "Pac-Man"
        self.status = ""

    def init(self, g: Graphics, m: Memory, io, rom_data: RomData) -> bool:
        self.gVideo = g
        self.init_hardware(m, io, rom_data)
        self.title = "Ms. Pac-Man" if rom_data.rom_set == MSPACMAN else "Pac-Man"
        if not self.videoOutlineFont.load("fonts/blitz.fon", 14):
            return False
        return True

    def init_hardware(self, m: Memory, io, rom_data: RomData):
        """Everything needed to render frames (no window/font needed: used by the tests)."""
        self.videoMemory = m
        self.videoMemoryPtr = m.get_memory_ptr()
        self.videoIo = io
        self.is_mspacman = rom_data.rom_set == MSPACMAN
        self.colors = decode_colors(rom_data.color)
        self.palettes = decode_palettes(rom_data.palette, self.colors)
        self.tile_pixels = [decode_tile(rom_data.tile, i) for i in range(len(rom_data.tile) // 16)]
        self.sprite_pixels = [decode_sprite(rom_data.sprite, i) for i in range(len(rom_data.sprite) // 64)]
        self._tile_cache = {}
        self._sprite_cache = {}
        self.background = pygame.Surface((RESOLUTION_WIDTH, RESOLUTION_HEIGHT))
        self.frame = pygame.Surface((RESOLUTION_WIDTH, RESOLUTION_HEIGHT))
        self._cell_state = [None] * len(TILE_LAYOUT)   # (tile, palette) currently drawn per cell

    # --- tile / sprite surfaces ---------------------------------------------

    def get_tile(self, tile, palette):
        key = (tile, palette)
        surface = self._tile_cache.get(key)
        if surface is None:
            pal = [bytes(c) for c in self.palettes[palette]]
            data = b"".join(pal[p] for p in self.tile_pixels[tile])
            surface = pygame.image.frombuffer(data, (8, 8), "RGB").copy()
            self._tile_cache[key] = surface
        return surface

    def get_sprite(self, sprite, palette, flip_x, flip_y):
        key = (sprite, palette, flip_x, flip_y)
        surface = self._sprite_cache.get(key)
        if surface is None:
            # Colour index 0 and palette 0 are transparent
            pal = [bytes(c) + (b"\x00" if i == 0 or palette == 0 else b"\xff")
                   for i, c in enumerate(self.palettes[palette])]
            data = b"".join(pal[p] for p in self.sprite_pixels[sprite])
            surface = pygame.image.frombuffer(data, (16, 16), "RGBA").copy()
            if flip_x or flip_y:
                surface = pygame.transform.flip(surface, flip_x, flip_y)
            self._sprite_cache[key] = surface
        return surface

    # --- frame rendering -------------------------------------------------------

    def _update_background(self):
        """Redraw only the tiles whose number or palette changed since last frame."""
        mem = self.videoMemoryPtr
        state = self._cell_state
        bg = self.background
        mspac = self.is_mspacman
        get_tile = self.get_tile
        for n, (offset, x, y) in enumerate(TILE_LAYOUT):
            tile = mem[0x4000 + offset]
            palette = mem[0x4400 + offset] & 0x7F
            if mspac and palette == 93 and 0x040 <= offset < 0x3C0:
                palette = 63    # Ms. Pac-Man blue maze fix (as in the C# version)
            if palette >= 64:
                palette = 0
            key = (tile, palette)
            if state[n] != key:
                state[n] = key
                bg.blit(get_tile(tile, palette), (x, y))

    def render_frame(self, sprite_coords=None, flip_screen=None) -> pygame.Surface:
        """Render tiles + sprites into self.frame (256x288) and return it."""
        io = self.videoIo
        if sprite_coords is None:
            sprite_coords = io.sprite_coords
        if flip_screen is None:
            flip_screen = io.flip_screen
        self._update_background()
        frame = self.frame
        if flip_screen:
            frame.blit(pygame.transform.rotate(self.background, 180), (0, 0))
        else:
            frame.blit(self.background, (0, 0))

        mem = self.videoMemoryPtr
        # Sprite 7 first, sprite 0 last (on top)
        for s in range(7, -1, -1):
            flags = mem[0x4FF0 + s * 2]
            palette = mem[0x4FF1 + s * 2]
            if palette >= 64:
                palette = 0
            if palette == 0:
                continue        # fully transparent
            sx = sprite_coords[s * 2]
            sy = sprite_coords[s * 2 + 1]
            surface = self.get_sprite(flags >> 2, palette, bool(flags & 0x02), bool(flags & 0x01))
            frame.blit(surface, (RESOLUTION_WIDTH - sx - 1, RESOLUTION_HEIGHT - 16 - sy))

        # Mask the off screen columns
        frame.fill((0, 0, 0), (0, 0, 16, RESOLUTION_HEIGHT))
        frame.fill((0, 0, 0), (RESOLUTION_WIDTH - 16, 0, 16, RESOLUTION_HEIGHT))
        return frame

    def invalidate(self):
        """Force a full redraw of the background (e.g. after loading state)."""
        self._cell_state = [None] * len(TILE_LAYOUT)

    def draw(self):
        g = self.gVideo
        g.clear(0, 0, 0)
        self.draw_outline_font(f"{self.title} emulator started. {self.status}", 0, 0, 255, 255, 255)
        self.draw_controls_panel()
        self.copy_screen()
        x, y, w, h = self.X, self.Y, PAC_SCREEN_W, PAC_SCREEN_H
        g.draw_line(x - 1, y - 1, x + w + 1, y - 1, 200, 200, 200)
        g.draw_line(x - 1, y + h, x + w, y + h, 200, 200, 200)
        g.draw_line(x - 1, y - 1, x - 1, y + h, 200, 200, 200)
        g.draw_line(x + w, y - 1, x + w, y + h, 200, 200, 200)

    def copy_screen(self):
        frame = self.render_frame()
        scaled = pygame.transform.scale(frame, (PAC_SCREEN_W, PAC_SCREEN_H))
        self.gVideo.get_backbuffer().blit(scaled, (self.X, self.Y))

    # Right-hand help panel (same approach as the Space Invaders emulator). Each
    # section is (title, credits_needed, rows); a row is a plain string (word-wrapped)
    # or an (action, key) pair (two-column table). The section is highlighted as
    # READY when no game is in progress and at least credits_needed credits exist.
    # Keep keys in sync with iohandler.py.
    HELP_SECTIONS = (
        ("1 PLAYER GAME", 1, (
            "1. Press 5 (or 6) to insert a coin.",
            "2. Press 1 to start.",
        )),
        ("2 PLAYER GAME", 2, (
            "1. Press 5 twice to insert 2 coins. CREDIT must show 2.",
            "2. Press 2 to start.",
            "Players take turns when a life is lost.",
        )),
        ("CONTROLS", None, (
            ("Move (player 1)", "ARROW keys"),
            ("Move (player 2)", "W A S D"),
            ("Service credit", "3"),
            ("Rack advance", "7"),
            ("Board test", "8 (toggle)"),
            ("Pause", "P"),
            ("Mute sound", "M"),
            ("Quit", "ESCAPE"),
        )),
    )

    TITLE_COLOR = (255, 255, 0)
    TEXT_COLOR = (200, 200, 200)
    KEY_COLOR = (255, 184, 81)
    READY_TITLE_COLOR = (255, 255, 255)
    READY_BAR_COLOR = (33, 33, 222)
    READY_SUFFIX = "  << READY"
    READY_BLINK_FRAMES = 20

    # Pac-Man / Ms. Pac-Man RAM locations used to drive the panel highlight
    RAM_GAME_STATE = 0x4E00   # 0 = init, 1 = attract, 2 = coin inserted, 3 = playing
    RAM_CREDITS = 0x4E6E      # credits, BCD (0xFF = free play)

    def game_state(self):
        """Return (credits, game_in_progress) read from the emulated RAM."""
        mem = self.videoMemoryPtr
        if mem is None:
            return 0, False
        bcd = mem[self.RAM_CREDITS]
        credits = 99 if bcd == 0xFF else (bcd >> 4) * 10 + (bcd & 0x0F)
        return credits, mem[self.RAM_GAME_STATE] == 3

    def draw_controls_panel(self):
        if getattr(self, "_panel_ops", None) is None:
            self._panel_ops = self._layout_help_panel()
        credits, in_game = self.game_state()
        frame = getattr(self, "_panel_frame", 0)
        self._panel_frame = frame + 1
        show_marker = (frame // self.READY_BLINK_FRAMES) % 2 == 0
        bar_height = self._line_height() + 2
        bar_width = self._panel_right - self._panel_x + 8
        for text, x, y, (r, g, b), needed in self._panel_ops:
            if needed is not None and not in_game and credits >= needed:
                br, bg, bb = self.READY_BAR_COLOR
                self.gVideo.fill_rect(x - 4, y - 1, bar_width, bar_height, br, bg, bb)
                r, g, b = self.READY_TITLE_COLOR
                if show_marker:
                    text += self.READY_SUFFIX
            self.draw_outline_font(text, x, y, r, g, b)

    def _layout_help_panel(self):
        """Compute (text, x, y, colour, credits_needed) draw operations for the help panel once."""
        font = getattr(self.videoOutlineFont, "font", None)
        width_of = (lambda s: font.size(s)[0]) if font else (lambda s: len(s) * 8)

        x = self.X + PAC_SCREEN_W + 20
        backbuffer = self.gVideo.get_backbuffer() if self.gVideo else None
        right = (backbuffer.get_width() if backbuffer else 860) - 10
        indent = 8
        line = self._line_height() + 4
        self._panel_x, self._panel_right = x, right

        labels = [row[0] for _, _, rows in self.HELP_SECTIONS for row in rows if isinstance(row, tuple)]
        key_x = x + indent + (max(width_of(a) for a in labels) if labels else 0) + 16

        ops = []
        y = self.Y
        for title, needed, rows in self.HELP_SECTIONS:
            ops.append((title, x, y, self.TITLE_COLOR, needed))
            y += line + 2
            for row in rows:
                if isinstance(row, tuple):
                    action, key = row
                    ops.append((action, x + indent, y, self.TEXT_COLOR, None))
                    ops.append((key, key_x, y, self.KEY_COLOR, None))
                    y += line
                else:
                    match = re.match(r"^(\d+\.\s+)(.*)$", row)
                    prefix, body = (match.group(1), match.group(2)) if match else ("", row)
                    text_x = x + indent + (width_of(prefix) if prefix else 0)
                    if prefix:
                        ops.append((prefix.rstrip(), x + indent, y, self.TEXT_COLOR, None))
                    for wrapped in self._wrap_text(body, right - text_x, width_of):
                        ops.append((wrapped, text_x, y, self.TEXT_COLOR, None))
                        y += line
            y += line
        return ops

    @staticmethod
    def _wrap_text(text, max_width, width_of):
        """Greedy word-wrap of text into lines no wider than max_width pixels."""
        lines, current = [], ""
        for word in text.split():
            candidate = word if not current else current + " " + word
            if width_of(candidate) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def _line_height(self):
        font = getattr(self.videoOutlineFont, "font", None)
        return font.get_linesize() if font else 18

    def draw_outline_font(self, text, x, y, r, g, b):
        self.videoOutlineFont.draw(text, x, y, r, g, b, self.gVideo)

    def free(self):
        self.videoOutlineFont.free()

    def get_video_outline_font(self):
        return self.videoOutlineFont
