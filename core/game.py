
# Main Game class for managing the game loop, system initialization, and core services
import pygame
import pygame.gfxdraw
from dataclasses import dataclass
from core.graphics import Graphics
from core.input import Input
from core.audio import Audio

@dataclass
class Game:
    def __init__(self):
        # Core subsystems
        self.graphics = Graphics()
        self.input = Input()
        self.audio = Audio()
        self.is_done = False  # Game loop control
        self.fps = 30  # Target frames per second

    def get_ticks(self) -> int:
        """Return the number of milliseconds since pygame.init()."""
        return pygame.time.get_ticks()

    def set_fps(self, f: int) -> None:
        """Set the target frames per second."""
        self.fps = f

    def delay(self, ticks: int) -> None:
        """Delay the game for a given number of milliseconds"""
        if ticks > 0:
            pygame.time.delay(int(ticks))

    def init_system(self, title: str, width: int, height: int, fullscreen: bool) -> bool:
        """Initialize all core systems: graphics, audio, input."""
        pygame.mixer.pre_init(22050, -16, 2, 2048)
        pygame.init()

        if not self.graphics.init(width, height, fullscreen):
            return False

        pygame.display.set_caption(title)

        if not self.audio.init():
            return False

        self.input.init()
        return True

    def free_system(self) -> None:
        """Shut down all core systems."""
        self.input.kill()
        self.audio.kill()
        pygame.quit()

    def run(self) -> None:
        """Main game loop: handles input, updates, drawing, and frame timing."""
        while not self.is_done:
            frame_start = pygame.time.get_ticks()

            # Poll events first (like SDL_PollEvent in C++), then handle quit this frame
            self.input.update()
            if self.input.get_event(pygame.QUIT):
                self.is_done = True
                break

            self.update()
            self.draw(self.get_graphics())

            self.get_graphics().flip()

            # Frame timing and delay to maintain FPS
            frame_time = pygame.time.get_ticks() - frame_start
            delay_time = (1000 / self.fps) - frame_time
            delay_time > 0 and pygame.time.delay(int(delay_time))
            # print(f"Frame time: {frame_time} ms, Delay time: {delay_time} ms")

        self.free()
        self.free_system()

    def end(self) -> None:
        """Signal the game loop to end."""
        self.is_done = True

    def init(self) -> bool:
        """Default initialization for the game window."""
        return self.init_system("Game", 800, 600, False)

    def free(self) -> None:
        """Override to free game-specific resources."""
        pass

    def update(self) -> None:
        """Override to update game logic each frame."""
        pass

    def draw(self, g: Graphics) -> None:
        """Override to draw game content each frame."""
        g.clear(255, 255, 255)

    def get_graphics(self) -> Graphics:
        """Return the graphics system instance."""
        return self.graphics

    def get_input(self) -> Input:
        """Return the input system instance."""
        return self.input

    def get_audio(self) -> Audio:
        """Return the audio system instance."""
        return self.audio
