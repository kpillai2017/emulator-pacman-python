"""
Pattern 7 of 19 - DOUBLE BUFFER
===============================
Book: "Sequencing Patterns > Double Buffer"
      https://gameprogrammingpatterns.com/double-buffer.html

  "Cause a series of sequential operations to appear instantaneous or
   simultaneous."

THE PROBLEM (book section "How computer graphics work (briefly)")
    The video hardware reads the frame buffer continuously while we draw into
    it. If it reads a half-drawn frame, the player sees *tearing*: the maze
    from this frame with Pac-Man still where he was last frame, say.

THE PATTERN (book section "The Pattern")
    Keep TWO buffers:
      * the *current* buffer: finished, and the one being shown;
      * the *next* buffer: the one we draw the new frame into.
    When the next frame is complete, ``swap()``: the roles flip in one cheap
    step (we just flip an index, which is the book's "Swap pointers" option in
    "How are the buffers swapped?"). Nobody ever sees a half-finished frame.

    The book's theatre analogy ("Act 1, Scene 1"): two stages; the audience
    watches one while the crew sets up the next, then the spotlight switches.

WHERE IT IS USED IN THE GAME
    Every frame app/game.py draws into ``frame_buffer.next``. The game loop
    (p08_game_loop.py) then calls ``swap()`` and ``present()``, which copies
    the *current* buffer to the window.

    The engine's ``core.graphics.Graphics`` already calls its window surface
    the ``backbuffer``, and ``pygame.display.flip()`` is SDL's own hardware
    double buffer. So the window has *two* layers of double buffering here.
    The explicit one is kept for teaching, and it is genuinely useful: the
    whole frame is finished off-screen, so it can be scaled to the window
    size, saved as a screenshot or post-processed in one place.

NOT JUST FOR GRAPHICS (book sections "Artificial unintelligence" / "Buffered slaps")
    The book's second example double-buffers *game state* so that actors
    updated later in a frame don't see changes made earlier in the same frame.
    ``DoubleBufferedValue`` below is the minimal version of that idea.
    Our game doesn't need it: collisions are resolved after all actors have
    moved (see p19_spatial_partition.py).

KEEP IN MIND (book sections "The swap itself takes time" / "We have to have two buffers")
    Two full-screen surfaces cost twice the memory. The swap here is O(1);
    ``present`` is a blit (a copy), done once per rendered frame.
"""
import pygame


class FrameBuffer:
    """Two off-screen surfaces: draw into ``next``, show ``current``, then swap."""

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._buffers = [pygame.Surface((width, height)), pygame.Surface((width, height))]
        self._current = 0
        self.swaps = 0

    @property
    def current(self) -> pygame.Surface:
        """The finished frame (what the player sees)."""
        return self._buffers[self._current]

    @property
    def next(self) -> pygame.Surface:
        """The frame being drawn (nobody sees it until ``swap``)."""
        return self._buffers[1 - self._current]

    def swap(self) -> None:
        self._current = 1 - self._current
        self.swaps += 1

    def present(self, window: pygame.Surface) -> None:
        """Copy the current buffer to the window, scaling if the sizes differ."""
        if window.get_size() == (self.width, self.height):
            window.blit(self.current, (0, 0))
        else:
            pygame.transform.scale(self.current, window.get_size(), window)


class DoubleBufferedValue:
    """The book's "Buffered slaps" idea for any value: read old, write new, swap."""

    def __init__(self, value):
        self._current = value
        self._next = value

    def get(self):
        return self._current

    def set(self, value) -> None:
        self._next = value

    def swap(self) -> None:
        self._current = self._next
