
# Sound class for loading and playing sound effects
import pygame
import pygame.gfxdraw
from dataclasses import dataclass

@dataclass
class Sound:
    def __init__(self):
        # Store the loaded sound object
        self.sound = None
        # pygame.mixer.pre_init(22050, -16, 2, 1024)
        # pygame.init()
        # pygame.mixer.quit()
        # pygame.mixer.init(22050, -16, 2, 1024)

    def load(self, file_spec: str) -> bool:
        """Load a sound effect from file"""
        self.sound = pygame.mixer.Sound(file_spec)
        if not self.sound:
            print(f"Failed to load sound: {file_spec}")
            return False
        return True

    def free(self) -> None:
        """Free the loaded sound resource."""
        pygame.mixer.quit()
        self.sound = None

    def pause(self, channel=0) -> None:
        """Pause the music."""
        pygame.mixer.pause()

    def resume(self, channel=0) -> None:
        """Resume the music."""
        pygame.mixer.unpause()

    def halt(self, channel=0) -> None:
        """Stop the music."""
        pygame.mixer.stop()

    def play(self, loops=0) -> int:
        """Play the sound effect, optionally looping."""
        if self.sound is not None:
            return self.sound.play(loops)
        else:
            return -1

    def is_loaded(self) -> bool:
        """Return True if a sound is loaded."""
        return self.sound is not None
