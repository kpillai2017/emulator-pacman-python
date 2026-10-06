import pygame
import pygame.gfxdraw
import os
from dataclasses import dataclass

# Image class for loading and drawing bitmap images, with optional frame support
@dataclass
class Image:
    def __init__(self):
        # Surface and dimension info
        self.surface = 0
        self.width = 0
        self.height = 0
        self.frame_width = 0
        self.frame_height = 0

    def load(self, file_spec: str, *args) -> bool:
        """Load an image from file, optionally with frame size for spritesheets"""
        i_list = []
        dir_name = os.path.dirname(file_spec)
        file_name = os.path.basename(file_spec)
        image_loaded = pygame.image.load(os.path.join(dir_name, file_name))
        self.surface = image_loaded.convert()

        if self.surface is not None:
            self.surface.set_colorkey((255, 0, 255))  # Set transparency color
            self.width = self.surface.get_width()
            self.height = self.surface.get_height()

            # Optionally set frame size for spritesheets
            for arg in args:
                i_list.append(arg)
            if len(i_list) == 2:
                self.frame_width = i_list[0]
                self.frame_height = i_list[1]
        else:
            print(f"Failed to load image: {file_name}")
            return False
        return True

    def draw(self, x: int, y: int, *args) -> None:
        """Draw the image at (x, y). Optionally support frames and graphics context."""
        if not self.surface:
            return
        i_list = []
        for arg in args:
            i_list.append(arg)
        # If one parameter, it's the Graphics() instance
        if len(i_list) == 1:
            i_list[0].get_backbuffer().blit(self.surface, (x, y))
        elif len(i_list) == 2:
            columns = self.surface.get_width() / self.frame_width

            src_rect_y = (i_list[0] // columns) * self.frame_height
            src_rect_x = (i_list[0] % columns) * self.frame_width
            src_rect_w = self.frame_width
            src_rect_h = self.frame_height

            i_list[1].get_backbuffer().blit(
                self.surface, (x, y),
                (src_rect_x, src_rect_y, src_rect_w, src_rect_h))

    def free(self) -> None:
        self.surface = 0

    def get_width(self) -> int:
        return self.width

    def get_height(self) -> int:
        return self.height

    def get_frame_width(self) -> int:
        return self.frame_width

    def get_frame_height(self) -> int:
        return self.frame_height

    def set_frame_size(self, w: int, h: int) -> None:
        self.frame_width = w
        self.frame_height = h

    def is_loaded(self) -> bool:
        return self.surface is not None
