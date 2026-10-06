
# RasterFont class for drawing text using a bitmap font image
from dataclasses import dataclass
from core.image import Image
from core.graphics import Graphics

@dataclass
class RasterFont:
    def __init__(self):
        # Bitmap font properties
        self.NUM_COLUMNS = 16
        self.START_CHAR = 32
        self.image = Image()
        self.char_size = 0

    def load(self, file_spec: str) -> bool:
        """Load the bitmap font image and set up character size"""
        if not self.image.load(file_spec):
            return False
        self.char_size = self.image.get_width() / self.NUM_COLUMNS
        self.image.set_frame_size(self.char_size, self.char_size)
        return True

    def draw(self, text: str, x: int, y: int, g: Graphics) -> None:
        """Draw a string using the bitmap font at (x, y)."""
        if not self.image.is_loaded():
            return
        for i in range(len(text)):
            self.image.draw(x + i * self.char_size, y, ord(text[i]) - self.START_CHAR, g)

    def free(self) -> None:
        """Free the font image resource."""
        self.image.free()
