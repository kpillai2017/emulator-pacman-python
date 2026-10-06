
# Audio system for handling music playback and control using pygame
import pygame
import pygame.gfxdraw
from dataclasses import dataclass
from core.music import Music

@dataclass
class Audio:
    def __init__(self):
        # Track if music is currently playing
        self.is_music_playing = False
        self.music = Music()

    def init(self) -> bool:
        """Initialise the audio system."""
        pygame.mixer.pre_init(22050, -16, 2, 2048)
        pygame.init()
        pygame.mixer.quit()
        pygame.mixer.init(22050, -16, 2, 2048)
        return True

    def kill(self) -> None:
        """Shut down the audio system."""
        pygame.mixer.quit()

    def music_play(self, loops=0) -> None:
        """Play music with optional looping."""
        self.music.play(loops)
        self.is_music_playing = True

    def music_playing(self) -> bool:
        """Return True if music is currently playing."""
        return self.music.music_playing()

    def music_paused(self) -> bool:
        """Return True if music is paused."""
        return not self.is_music_playing

    def pause_music(self) -> None:
        """Pause the currently playing music."""
        pygame.mixer.music.pause()
        self.is_music_playing = False

    def resume_music(self) -> None:
        """Resume paused music."""
        pygame.mixer.music.unpause()
        self.is_music_playing = True

    def stop_music(self) -> None:
        """Stop the music playback."""
        pygame.mixer.music.stop()
        self.is_music_playing = False

    def stop_channel(self, channel: pygame.mixer.Channel) -> None:
        """Stop a specific audio channel."""
        channel.stop()
