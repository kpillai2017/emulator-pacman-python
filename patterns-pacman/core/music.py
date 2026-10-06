
# Music class for loading and controlling background music playback
import pygame
import pygame.gfxdraw
from dataclasses import dataclass

@dataclass
class Music:
    def __init__(self):
        # Track if music is loaded
        self.music = None

    def load(self, file_spec: str) -> bool:
        """Load a music file for playback."""
        pygame.mixer.music.load(file_spec)
        self.music = True
        # If loading fails, self.music would remain None.
        return True

    def free(self) -> None:
        """Free the loaded music resource."""
        if self.music is not None:
            music = None

    def play(self, loops: int) -> None:
        """Play the loaded music, optionally looping."""
        if self.music:
            pygame.mixer.music.play(loops)

    def is_loaded(self) -> None:
        """Return True if music is loaded."""
        return self.music

    def music_playing(self) -> bool:
        """Return True if music is currently playing."""
        return pygame.mixer.music.get_busy()
