"""
Pattern 2 of 19 - FLYWEIGHT
===========================
Book: "Design Patterns Revisited > Flyweight"
      https://gameprogrammingpatterns.com/flyweight.html

  "Use sharing to support large numbers of fine-grained objects efficiently."

THE PROBLEM
    The maze has 28 x 31 = 868 cells. If each cell were its own object holding
    "am I a wall? can ghosts walk here? how many points? what colour?", we'd
    have 868 objects that are mostly identical copies of six kinds of cell.

THE PATTERN
    Split an object's state in two:
      * *intrinsic* state: the same for every cell of a kind (is it a wall,
        its points value...). It lives in ONE shared ``Tile`` object per kind:
        the flyweight.
      * *extrinsic* state: what differs per cell. Here that is only "where
        it is", and the position is implied by the cell's index in the grid.
    The grid then stores *references* to the shared flyweights. This is the
    book's terrain example almost word for word (section "A Place To Put Down
    Roots": ``Terrain* tiles_[WIDTH][HEIGHT]``).

    Bonus from the book: because tiles are real objects, code asks
    ``maze.tile(c, r).pacman_can_enter`` instead of a ``switch`` on an enum.

    Eating a dot doesn't modify a Tile (that would change *every* dot!). The
    grid entry is pointed at the shared FLOOR flyweight instead.

WHERE IT IS USED IN THE GAME
    ``Maze`` is the playfield for everything that moves. The panel on the
    right shows "868 cells -> 6 Tile objects".

PERFORMANCE (book section "What About Performance?")
    In C++ the win is memory and cache use. In Python every list slot is
    already a reference, so the win is mostly *clarity*: there is exactly one
    place that says what a wall is.
"""
from support.constants import MAZE_COLS, MAZE_ROWS
from support.maze_layout import LAYOUT


class Tile:
    """A flyweight: intrinsic state shared by every maze cell of this kind."""
    # __slots__ keeps these objects small and makes them obviously "just data".
    __slots__ = ("name", "char", "pacman_can_enter", "ghost_can_enter",
                 "points", "is_power", "is_wall", "slows_ghosts")

    def __init__(self, name, char, pacman_can_enter, ghost_can_enter,
                 points=0, is_power=False, is_wall=False, slows_ghosts=False):
        self.name = name
        self.char = char
        self.pacman_can_enter = pacman_can_enter
        self.ghost_can_enter = ghost_can_enter
        self.points = points
        self.is_power = is_power
        self.is_wall = is_wall
        self.slows_ghosts = slows_ghosts

    @property
    def is_dot(self) -> bool:
        return self.points > 0

    def __repr__(self) -> str:
        return f"<Tile {self.name}>"


# The only six Tile objects that will ever exist.
WALL = Tile("wall", "#", False, False, is_wall=True)
FLOOR = Tile("floor", " ", True, True)
DOT = Tile("dot", ".", True, True, points=10)
POWER = Tile("power pellet", "o", True, True, points=50, is_power=True)
# The gate is closed to normal maze movement for everyone; ghosts pass through
# it with special "enter/leave the house" states (p06_state.py).
GATE = Tile("gate", "-", False, False, is_wall=True)
TUNNEL = Tile("tunnel", "t", True, True, slows_ghosts=True)

ALL_TILES = (WALL, FLOOR, DOT, POWER, GATE, TUNNEL)
_BY_CHAR = {t.char: t for t in ALL_TILES}


class Maze:
    """The grid: one *reference* per cell to a shared Tile flyweight."""

    def __init__(self, layout=LAYOUT):
        assert len(layout) == MAZE_ROWS and all(len(r) == MAZE_COLS for r in layout), \
            "maze layout must be 28 x 31"
        self.layout = layout
        self.cols = MAZE_COLS
        self.rows = MAZE_ROWS
        self.tiles = []
        self.total_dots = 0
        self.dots_left = 0
        # Which cells changed since the renderer last looked. The renderer in
        # p17_dirty_flag.py uses these as its dirty flags.
        self.changed = set()
        self.all_changed = True
        self.reset()

    def reset(self) -> None:
        """Rebuild the grid from the layout text (new level)."""
        self.tiles = [_BY_CHAR[ch] for row in self.layout for ch in row]
        self.total_dots = self.dots_left = sum(1 for t in self.tiles if t.is_dot)
        self.changed.clear()
        self.all_changed = True

    def tile(self, col: int, row: int) -> Tile:
        """The flyweight at (col, row). Columns wrap (tunnel); outside rows are walls."""
        if row < 0 or row >= self.rows:
            return WALL
        return self.tiles[row * self.cols + (col % self.cols)]

    def pacman_can_enter(self, col: int, row: int) -> bool:
        return self.tile(col, row).pacman_can_enter

    def ghost_can_enter(self, col: int, row: int) -> bool:
        return self.tile(col, row).ghost_can_enter

    def eat(self, col: int, row: int):
        """Remove a dot/pellet. Returns the Tile that was eaten, or None."""
        tile = self.tile(col, row)
        if not tile.is_dot:
            return None
        # Point the cell at another flyweight; never modify the shared Tile.
        self.tiles[row * self.cols + (col % self.cols)] = FLOOR
        self.dots_left -= 1
        self.changed.add((col % self.cols, row))
        return tile

    def distinct_tile_objects(self) -> int:
        """How many different objects the 868 cells refer to (shown on the panel)."""
        return len({id(t) for t in self.tiles})
