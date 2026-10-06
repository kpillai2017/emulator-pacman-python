
# Graphics class for managing drawing operations and the main backbuffer
import pygame
import pygame.gfxdraw
from dataclasses import dataclass

@dataclass
class Graphics:
    def __init__(self):
        # The main drawing surface (screen)
        self.backbuffer = 0
        self.width = 0
        self.height = 0

    def init(self, a_width: int, a_height: int, a_fullscreen: bool) -> bool:
        """Initialise the graphics system and create the main window."""
        self.width = a_width
        self.height = a_height

        if a_fullscreen:
            self.backbuffer = pygame.display.set_mode(
                (self.width, self.height),
                pygame.SWSURFACE | pygame.SWFULLSCREEN, 32)
        else:
            self.backbuffer = pygame.display.set_mode(
                (self.width, self.height),
                pygame.SWSURFACE, 32)

        if self.backbuffer is None:
            print(f"Failed to initialise graphics!")
            return False
        return True


    def draw_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Draw a single pixel at (x, y) with the given color."""

        if self.backbuffer is None:
            return

        if self.backbuffer.mustlock():
            self.backbuffer.lock()
            if not self.backbuffer.get_locked():
                return

        if x >= self.backbuffer.get_width() or x < 0 or y >= self.backbuffer.get_height() or y < 0:
            return

        pygame.gfxdraw.pixel(self.backbuffer, x, y, (r, g, b))

        if self.backbuffer.mustlock():
            self.backbuffer.unlock()


    def draw_line(self, x1: int, y1: int, x2: int, y2: int, r: int, g: int, b: int) -> None:
        """Draw a line from (x1, y1) to (x2, y2) with the given color."""
        pygame.draw.line(self.backbuffer, (r, g, b), (x1, y1), (x2, y2))
        # Bresenham's line algorithm
        # steep = abs(y2 - y1) > abs(x2 - x1)
        # if steep:
        #     x1, y1 = y1, x1
        #     x2, y2 = y2, x2

        # if x1 > x2:
        #     x1, x2 = x2, x1
        #     y1, y2 = y2, y1

        # dx = x2 - x1
        # dy = abs(y2 - y1)

        # error = dx / 2.0
        # ystep = 1 if y1 < y2 else -1
        # y = int(y1)

        # maxX = int(x2)

        # for x in range(int(x1), maxX):
        #     if steep:
        #         self.draw_pixel(y, x, r, g, b)
        #     else:
        #         self.draw_pixel(x, y, r, g, b)

        #     error -= dy
        #     if error < 0:
        #         y += ystep
        #         error += dx

    def draw_pixel_column(self, x: int, y: int, height: int, r: int, g: int, b: int) -> None:
        """Draw a vertical column of pixels starting at (x, y) of given height and color."""
        for i in range(height):
            self.draw_pixel(x, y + i, r, g, b)

    def draw_rect(self, x: int, y: int, width: int, height: int, r: int, g: int, b: int) -> None:
        """Draw a rectangle outline."""
        pygame.draw.rect(self.backbuffer, (r, g, b), (x, y, width, height), 1)

    def fill_rect(self, x: int, y: int, width: int, height: int, r: int, g: int, b: int) -> None:
        """Draw a filled rectangle."""
        pygame.draw.rect(self.backbuffer, (r, g, b), (x, y, width, height))

    def clear(self, r: int, g: int, b: int) -> None:
        """Clear the screen to the given color."""
        if self.backbuffer is None:
            return
        self.fill_rect(0, 0, self.get_width(), self.get_height(), r, g, b)

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height

    def get_backbuffer(self) -> pygame.Surface:
        return self.backbuffer

    def flip(self) -> None:
        pygame.display.flip()
 

