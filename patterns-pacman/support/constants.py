"""Screen geometry, colours, directions and gameplay tuning numbers."""
from enum import Enum

# --- Geometry -------------------------------------------------------------------
TILE = 16                      # pixels per maze tile
MAZE_COLS = 28
MAZE_ROWS = 31
HUD_TOP = 32                   # score line above the maze
HUD_BOTTOM = 32                # lives / fruit line below the maze
MAZE_W = MAZE_COLS * TILE      # 448
MAZE_H = MAZE_ROWS * TILE      # 496
PANEL_W = 352                  # the "patterns at work" panel on the right
SCREEN_W = MAZE_W + PANEL_W    # 800
SCREEN_H = HUD_TOP + MAZE_H + HUD_BOTTOM  # 560

# --- Timing ---------------------------------------------------------------------
UPDATES_PER_SECOND = 60        # fixed simulation rate (see p08_game_loop.py)
DT = 1.0 / UPDATES_PER_SECOND  # seconds simulated by one update

# --- Speeds ---------------------------------------------------------------------
# The arcade's "100%" speed is about 9.5 tiles per second. Actors move at a
# fraction of it; those fractions live in data/breeds.json for the ghosts.
FULL_SPEED = 9.5 * TILE        # pixels per second
PACMAN_SPEED = 0.80
PACMAN_FRIGHT_SPEED = 0.90     # Pac-Man runs a little faster while ghosts are blue

# --- Colours (r, g, b) ----------------------------------------------------------
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
WALL_BLUE = (33, 33, 222)
WALL_FILL = (0, 0, 40)
DOT_COLOUR = (255, 184, 151)
PACMAN_YELLOW = (255, 255, 0)
FRIGHT_BLUE = (33, 33, 255)
GATE_PINK = (255, 184, 222)
PANEL_BG = (16, 16, 32)
PANEL_TEXT = (200, 200, 220)
PANEL_TITLE = (255, 220, 90)
PANEL_DIM = (110, 110, 140)


class Direction(Enum):
    """The four maze directions plus NONE. The value is the (dx, dy) step."""
    NONE = (0, 0)
    UP = (0, -1)
    LEFT = (-1, 0)
    DOWN = (0, 1)
    RIGHT = (1, 0)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]

    @property
    def opposite(self) -> "Direction":
        return _OPPOSITE[self]


_OPPOSITE = {
    Direction.NONE: Direction.NONE,
    Direction.UP: Direction.DOWN,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
    Direction.RIGHT: Direction.LEFT,
}

# The arcade breaks ties between equally good ghost moves in this order.
MOVES = (Direction.UP, Direction.LEFT, Direction.DOWN, Direction.RIGHT)


def tile_centre(col: int, row: int):
    """Pixel position (maze coordinates) of the centre of a tile."""
    return col * TILE + TILE / 2, row * TILE + TILE / 2


def tile_of(x: float, y: float):
    """The tile that contains maze pixel (x, y). Columns wrap (the tunnel)."""
    return int(x // TILE) % MAZE_COLS, int(y // TILE)
