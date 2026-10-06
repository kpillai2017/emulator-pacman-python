
# OutlineFont class for rendering text with a specified font and color
import pygame
from dataclasses import dataclass
from core.graphics import Graphics

@dataclass
class OutlineFont:
    def __init__(self):
        # Store the pygame font object
        self.font = 0
        pygame.init()

    def load(self, file_spec: str, size: int) -> bool:
        """Load a font from file with the given size"""
        self.font = pygame.font.Font(file_spec, size)
        if not self.font:
            return False
        return True

    def free(self) -> None:
        """Free the font resource."""
        if self.font is not None:
            pygame.font.quit()

    def draw(self, text: str, x: int, y: int, r: int, g: int, b: int, gfx: Graphics) -> None:
        """Draw text at (x, y) with the given color using the loaded font."""
        if not self.font:
            return False
        # Cache rendered text: the same strings are drawn every frame
        cache = self.__dict__.setdefault("_cache", {})
        key = (text, r, g, b)
        surface = cache.get(key)
        if surface is None:
            if len(cache) > 64:
                cache.clear()
            surface = self.font.render(text, True, (r, g, b))
            cache[key] = surface
        gfx.get_backbuffer().blit(surface, (x, y))
