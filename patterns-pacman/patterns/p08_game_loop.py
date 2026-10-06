"""
Pattern 8 of 19 - GAME LOOP
===========================
Book: "Sequencing Patterns > Game Loop"
      https://gameprogrammingpatterns.com/game-loop.html
      (source: https://github.com/munificent/game-programming-patterns/blob/master/book/game-loop.markdown)

  "Decouple the progression of game time from user input and processor speed."

THE PATTERN (book section "The Pattern")
    A game loop runs continuously. Each turn it processes user input
    *without blocking*, updates the game state and renders the game. It
    tracks the passage of time to control the rate of gameplay.

THE BOOK'S FOUR LOOPS (book section "Sample Code")
    1. "Run, run as fast as you can": no timing. Game speed depends on the
       machine.
    2. "Take a little nap": update, render, then sleep whatever is left of
       the 1/60 s. This is what the engine's ``core.game.Game.run`` does
       (look at its ``delay_time`` code). Simple, and fine for the emulator in
       the parent folder. But if a frame takes longer than 1/60 s the
       *game slows down*.
    3. "One small step, one giant step": a variable time step: pass the
       elapsed time into update. It adapts to any speed, but makes physics
       non-deterministic (floating point rounding differs with step size)
       and lets fast actors tunnel through walls on slow frames.
    4. "Play catch up": a FIXED update step with VARIABLE rendering:

           previous = now(); lag = 0
           while running:
               current = now(); lag += current - previous; previous = current
               process_input()
               while lag >= MS_PER_UPDATE:     # catch up in fixed steps
                   update()
                   lag -= MS_PER_UPDATE
               render(lag / MS_PER_UPDATE)    # see "Stuck in the middle"

       Gameplay is deterministic (every update simulates exactly 1/60 s),
       fast machines render more often and slow machines skip renders but not
       updates.

    "Stuck in the middle": after the catch-up loop, ``lag`` is how far we are
    *between* two updates (0..1 of a step). Rendering at ``alpha = lag /
    MS_PER_UPDATE`` lets each actor be drawn interpolated between its previous
    and current position, so motion is smooth even when the render rate isn't
    a multiple of 60 Hz. (Entity.lerp_position in p09_update_method.py.)

THIS FILE
    ``FixedTimestepGame`` subclasses the engine's ``core.game.Game`` and
    replaces ``run()`` with loop #4. The engine itself is unchanged: we reuse
    its window (Graphics), keyboard (Input) and audio initialisation.

DESIGN DECISIONS (book section "Design Decisions")
    * "Do you own the game loop, or does the platform?": we own it. pygame
      only gives us events.
    * "How do you manage power consumption?": once updates have caught up we
      cap *rendering* at MAX_RENDER_FPS with ``pygame.time.Clock.tick``, which
      sleeps instead of burning the CPU on frames nobody can see.
    * "How do you control gameplay speed?": fixed time step, so the
      simulation speed never depends on the machine.
    * The "spiral of death": if updates take longer than real time, ``lag``
      grows forever. We clamp the elapsed time to MAX_FRAME_MS, so on a hopelessly
      slow machine the game slows down rather than freezing.
"""
import pygame

from core.game import Game
from support.constants import UPDATES_PER_SECOND
from patterns.p07_double_buffer import FrameBuffer


class FixedTimestepGame(Game):
    """The book's "Play catch up" loop, built on the engine's Game class."""

    MS_PER_UPDATE = 1000.0 / UPDATES_PER_SECOND
    MAX_FRAME_MS = 250.0        # clamp against the spiral of death
    MAX_RENDER_FPS = 120        # power saving: don't render faster than this

    def __init__(self):
        super().__init__()
        self.frame_buffer = None
        self.lag = 0.0
        # Statistics for the patterns panel.
        self.total_updates = 0
        self.updates_last_frame = 0
        self.fps = 0.0                # rendered frames per second
        self.ups = 0.0                # updates per second (should be ~60)
        self._stat_frames = 0
        self._stat_updates = 0
        self._stat_ms = 0.0

    def init_frame_buffer(self, width: int, height: int) -> None:
        self.frame_buffer = FrameBuffer(width, height)

    # -- hooks for the game ------------------------------------------------------
    def process_input(self) -> None:
        """Once per loop turn: turn input into commands (p01)."""

    def fixed_update(self) -> None:
        """Advance the simulation by exactly MS_PER_UPDATE milliseconds."""

    def render(self, surface: pygame.Surface, alpha: float) -> None:
        """Draw the world ``alpha`` (0..1) of the way to the next update."""

    # -- the loop ----------------------------------------------------------------
    def tick(self, elapsed_ms: float) -> None:
        """One turn of the game loop, given the real time since the last turn.

        Split out of ``run`` so tests can drive the loop with fake time.
        """
        elapsed_ms = min(elapsed_ms, self.MAX_FRAME_MS)
        self.lag += elapsed_ms

        self.process_input()

        updates = 0
        while self.lag >= self.MS_PER_UPDATE:
            self.fixed_update()
            self.lag -= self.MS_PER_UPDATE
            updates += 1
        self.updates_last_frame = updates
        self.total_updates += updates

        # Render into the hidden buffer, then show it (Double Buffer, p07).
        self.render(self.frame_buffer.next, self.lag / self.MS_PER_UPDATE)
        self.frame_buffer.swap()
        self.frame_buffer.present(self.get_graphics().get_backbuffer())
        self.get_graphics().flip()

        self._measure(elapsed_ms, updates)

    def run(self) -> None:
        """Replaces core.game.Game.run ("Take a little nap") with "Play catch up"."""
        clock = pygame.time.Clock()
        previous = self.get_ticks()
        while not self.is_done:
            current = self.get_ticks()
            elapsed = current - previous
            previous = current

            self.get_input().update()              # engine: poll pygame events
            if self.get_input().get_event(pygame.QUIT):
                break
            self.tick(elapsed)
            clock.tick(self.MAX_RENDER_FPS)        # sleep a little: save power
        self.free()
        self.free_system()

    def _measure(self, elapsed_ms: float, updates: int) -> None:
        self._stat_frames += 1
        self._stat_updates += updates
        self._stat_ms += elapsed_ms
        if self._stat_ms >= 500:
            self.fps = self._stat_frames * 1000.0 / self._stat_ms
            self.ups = self._stat_updates * 1000.0 / self._stat_ms
            self._stat_frames = self._stat_updates = 0
            self._stat_ms = 0.0
