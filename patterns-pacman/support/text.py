"""Text drawing that reuses the engine's ``core.outline_font.OutlineFont``.

OutlineFont draws onto ``graphics.get_backbuffer()``. We draw into our own
off-screen buffers (p07_double_buffer.py), so a tiny adapter pretends a plain
Surface is a ``Graphics`` object. This way ``core`` stays unchanged.
"""
from core.outline_font import OutlineFont


class _SurfaceAsGraphics:
    def __init__(self, surface):
        self.surface = surface

    def get_backbuffer(self):
        return self.surface


class Text:
    def __init__(self, size: int):
        self.font = OutlineFont()
        self.font.load(None, size)      # None = pygame's built-in font: no font file needed
        self.height = self.font.font.get_height()

    def width(self, text: str) -> int:
        return self.font.font.size(text)[0]

    def draw(self, surface, text: str, x, y, colour=(255, 255, 255)) -> None:
        r, g, b = colour
        self.font.draw(text, int(x), int(y), r, g, b, _SurfaceAsGraphics(surface))

    def draw_centred(self, surface, text: str, cx, y, colour=(255, 255, 255)) -> None:
        self.draw(surface, text, cx - self.width(text) / 2, y, colour)
