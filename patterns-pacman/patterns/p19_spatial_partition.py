"""
Pattern 19 of 19 - SPATIAL PARTITION
====================================
Book: "Optimization Patterns > Spatial Partition"
      https://gameprogrammingpatterns.com/spatial-partition.html

  "Efficiently locate objects by storing them in a data structure organized
   by their positions."

THE PROBLEM (book section "Units on the field of battle")
    To find which actors touch, the naive way tests every pair: n * (n - 1) / 2
    distance checks. That is quadratic: fine for 6 actors, hopeless for 600.

THE PATTERN (book section "Drawing battle lines")
    Divide space into a grid of cells ("A sheet of graph paper"). Each cell
    keeps the units inside it. Two units can only touch if they are in the
    same or *neighbouring* cells, so we only test those pairs.

SAMPLE CODE, AS IN THE BOOK
    * "A grid of linked units": each cell holds the head of a *doubly linked
      list* of units, and each Unit has ``prev`` / ``next``. Adding, removing
      and moving between cells is O(1), with no list allocation.
    * "Entering the field of battle": ``add`` puts a unit at the front of its
      cell's list.
    * "A clash of swords": ``handle_collisions`` walks each cell and tests the
      units in it against each other.
    * "Charging forward": ``move`` re-files a unit when it crosses into a
      different cell.
    * "At arm's length": units near a cell edge can touch units in the next
      cell, so we also test against neighbouring cells. To avoid testing each
      pair twice we only look at *half* of the neighbours (left, up-left, up,
      up-right), exactly as the book does.

WHERE IT IS USED IN THE GAME
    After every update, app/game.py moves Pac-Man, the ghosts and the fruit
    in the grid and asks it for touching pairs: Pac-Man meets a ghost (eat or
    die) or the fruit (bonus). The panel compares the number of distance checks
    made with the brute-force n*(n-1)/2. With so few actors the saving is
    small, and the book says so too: "When to Use It": when you have *many*
    objects. Press Tab to see the grid drawn over the maze.

DESIGN DECISIONS (book section "Design Decisions")
    * "Is the partition hierarchical or flat?": flat (a fixed grid). Simple,
      and memory use is constant.
    * "Does the partitioning depend on the set of objects?": no, the cells are
      fixed, so moving objects is cheap.
    * "Are objects only stored in the partition?": no. The World (p09) still
      owns the entities; the grid only refers to them.
"""


class Unit:
    """An object's presence in the grid: a node in its cell's linked list."""
    __slots__ = ("owner", "x", "y", "cell", "prev", "next")

    def __init__(self, owner, x: float, y: float):
        self.owner = owner
        self.x = x
        self.y = y
        self.cell = None
        self.prev = None
        self.next = None


class Grid:
    def __init__(self, width: float, height: float, cell_size: float):
        self.cell_size = cell_size
        self.cols = int(width // cell_size) + 1
        self.rows = int(height // cell_size) + 1
        # cells[col][row] is the head of a linked list of units (or None).
        self.cells = [[None] * self.rows for _ in range(self.cols)]
        self.count = 0
        self.checks_last = 0       # distance checks made by the last collision pass

    def _cell_of(self, x: float, y: float):
        col = min(max(int(x // self.cell_size), 0), self.cols - 1)
        row = min(max(int(y // self.cell_size), 0), self.rows - 1)
        return col, row

    def add(self, unit: Unit) -> None:
        """Entering the field of battle: push onto the front of the cell's list."""
        col, row = self._cell_of(unit.x, unit.y)
        unit.cell = (col, row)
        unit.prev = None
        unit.next = self.cells[col][row]
        if unit.next is not None:
            unit.next.prev = unit
        self.cells[col][row] = unit
        self.count += 1

    def remove(self, unit: Unit) -> None:
        col, row = unit.cell
        if unit.prev is not None:
            unit.prev.next = unit.next
        else:
            self.cells[col][row] = unit.next
        if unit.next is not None:
            unit.next.prev = unit.prev
        unit.prev = unit.next = None
        unit.cell = None
        self.count -= 1

    def move(self, unit: Unit, x: float, y: float) -> None:
        """Charging forward: re-file the unit only if it changed cell."""
        unit.x, unit.y = x, y
        if self._cell_of(x, y) != unit.cell:
            self.remove(unit)
            self.add(unit)

    def handle_collisions(self, radius: float, on_touch) -> None:
        """Call ``on_touch(a, b)`` for every pair of owners closer than ``radius``.

        ``radius`` must not exceed ``cell_size`` (we only look one cell away).
        """
        assert radius <= self.cell_size
        self.checks_last = 0
        r2 = radius * radius
        for col in range(self.cols):
            for row in range(self.rows):
                unit = self.cells[col][row]
                while unit is not None:
                    # Same cell: units after this one.
                    self._handle_unit(unit, unit.next, r2, on_touch)
                    # At arm's length: half of the neighbouring cells.
                    if col > 0:
                        self._handle_unit(unit, self.cells[col - 1][row], r2, on_touch)
                        if row > 0:
                            self._handle_unit(unit, self.cells[col - 1][row - 1], r2, on_touch)
                        if row < self.rows - 1:
                            self._handle_unit(unit, self.cells[col - 1][row + 1], r2, on_touch)
                    if row > 0:
                        self._handle_unit(unit, self.cells[col][row - 1], r2, on_touch)
                    unit = unit.next

    def _handle_unit(self, unit: Unit, other: Unit, r2: float, on_touch) -> None:
        while other is not None:
            self.checks_last += 1
            dx, dy = unit.x - other.x, unit.y - other.y
            if dx * dx + dy * dy < r2:
                on_touch(unit.owner, other.owner)
            other = other.next

    def brute_force_checks(self) -> int:
        return self.count * (self.count - 1) // 2
