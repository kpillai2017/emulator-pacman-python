"""
Pattern 17 of 19 - DIRTY FLAG
=============================
Book: "Optimization Patterns > Dirty Flag"
      https://gameprogrammingpatterns.com/dirty-flag.html

  "Avoid unnecessary work by deferring it until the result is needed."

THE IDEA (book section "The Pattern")
    Some *derived data* is expensive to compute from *primary data*. Keep a
    cached copy of the derived data and a flag that says "the primary data
    changed since the cache was built". When someone needs the derived data:
    if the flag is set, rebuild and clear the flag; otherwise reuse the cache.
    The book's example: world transforms in a scene graph (primary = local
    transforms; derived = world transforms).

WHERE IT IS USED IN THE GAME
    1. ``MazeRenderer``: primary data = the Maze's tiles (p02); derived data =
       a picture of the maze. Drawing 868 tiles every frame is wasteful when
       at most one dot changes per update. So:
         * a *coarse* flag ``maze.all_changed`` (new level): redraw all;
         * *fine-grained* flags ``maze.changed`` = the set of cells changed
           (book: "How fine-grained is your dirty tracking?"). Only those
           cells are redrawn into the cached surface.
       The panel shows how many tiles were redrawn: almost always 0.
       Power pellets blink, so they are deliberately NOT cached: data that
       changes every frame gains nothing from a dirty flag.
    2. ``CachedText``: the HUD score. Rendering text with a font is slow, so
       the surface is re-rendered only when the value changed. The Scoreboard
       (p03) bumps a ``version`` number on every change, which acts as the flag.

KEEP IN MIND (book section "Keep in Mind")
    * "You have to make sure to set the flag *every* time the state changes":
      that is why only ``Maze.eat`` and ``Maze.reset`` change the maze, and both
      set the flags.
    * "You have to keep the previous derived data in memory": the cached
      surface costs a screen-sized bitmap.
    * "When is the dirty flag cleaned?" (Design Decisions): when the result is
      needed, i.e. just before drawing.
"""
import pygame

from support.constants import (TILE, MAZE_W, MAZE_H, BLACK, WALL_BLUE, WHITE,
                               DOT_COLOUR, GATE_PINK)


class MazeRenderer:
    def __init__(self, maze):
        self.maze = maze
        self.cache = pygame.Surface((MAZE_W, MAZE_H))
        self.flash_cache = pygame.Surface((MAZE_W, MAZE_H))   # white walls (level clear)
        self.tiles_redrawn_last = 0
        self.tiles_redrawn_total = 0
        self.full_rebuilds = 0

    def _draw_tile(self, surface, col: int, row: int, wall_colour) -> None:
        maze = self.maze
        tile = maze.tile(col, row)
        x, y = col * TILE, row * TILE
        surface.fill(BLACK, (x, y, TILE, TILE))
        if tile.is_wall and tile.char == "-":
            surface.fill(GATE_PINK, (x, y + TILE // 2 - 2, TILE, 4))
        elif tile.is_wall:
            inset = 4
            # Draw a line along each side that faces an open cell, so blocks of
            # wall cells appear as outlined shapes like the arcade maze.
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                ncol, nrow = col + dx, row + dy
                if not (0 <= ncol < maze.cols):
                    continue
                if maze.tile(ncol, nrow).is_wall:
                    continue
                if dy == -1:
                    rect = (x, y + inset, TILE, 2)
                elif dy == 1:
                    rect = (x, y + TILE - inset - 2, TILE, 2)
                elif dx == -1:
                    rect = (x + inset, y, 2, TILE)
                else:
                    rect = (x + TILE - inset - 2, y, 2, TILE)
                surface.fill(wall_colour, rect)
        elif tile.is_dot and not tile.is_power:
            surface.fill(DOT_COLOUR, (x + TILE // 2 - 2, y + TILE // 2 - 2, 4, 4))
        # Power pellets are drawn every frame in render(): they blink.

    def _rebuild_all(self) -> None:
        for row in range(self.maze.rows):
            for col in range(self.maze.cols):
                self._draw_tile(self.cache, col, row, WALL_BLUE)
                self._draw_tile(self.flash_cache, col, row, WHITE)
        self.full_rebuilds += 1
        self.tiles_redrawn_last = self.maze.rows * self.maze.cols

    def clean(self) -> None:
        """Bring the cache up to date, but only the parts that are dirty."""
        maze = self.maze
        self.tiles_redrawn_last = 0
        if maze.all_changed:                     # coarse flag
            self._rebuild_all()
            maze.all_changed = False
            maze.changed.clear()
        elif maze.changed:                       # fine-grained flags
            for col, row in maze.changed:
                self._draw_tile(self.cache, col, row, WALL_BLUE)
                self._draw_tile(self.flash_cache, col, row, WHITE)
            self.tiles_redrawn_last = len(maze.changed)
            maze.changed.clear()
        self.tiles_redrawn_total += self.tiles_redrawn_last

    def render(self, surface, blink_on: bool, flash: bool = False) -> None:
        self.clean()
        surface.blit(self.flash_cache if flash else self.cache, (0, 0))
        if blink_on:
            for row in range(self.maze.rows):
                for col in (1, 26):              # the four pellets sit in these columns
                    if self.maze.tile(col, row).is_power:
                        pygame.draw.circle(surface, DOT_COLOUR,
                                           (col * TILE + TILE // 2, row * TILE + TILE // 2), 6)


class CachedText:
    """A text surface re-rendered only when its value changes."""

    def __init__(self, font: pygame.font.Font, colour):
        self.font = font
        self.colour = colour
        self._value = None
        self._surface = None
        self.dirty = True
        self.renders = 0

    def set(self, value) -> None:
        if value != self._value:                 # set the flag on every change
            self._value = value
            self.dirty = True

    def surface(self) -> pygame.Surface:
        if self.dirty:                           # clean it only when needed
            self._surface = self.font.render(str(self._value), True, self.colour)
            self.dirty = False
            self.renders += 1
        return self._surface
