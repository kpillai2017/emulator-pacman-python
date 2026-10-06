"""
Pattern 9 of 19 - UPDATE METHOD
===============================
Book: "Sequencing Patterns > Update Method"
      https://gameprogrammingpatterns.com/update-method.html

  "Simulate a collection of independent objects by telling each to process
   one frame of behavior at a time."

THE PROBLEM (book section "Motivation")
    Pac-Man, four ghosts and a fruit all need to "do their thing" at the same
    time. Writing one giant loop body that moves Pac-Man, then Blinky, then
    Pinky... doesn't scale, and each actor's behaviour gets smeared across it.

THE PATTERN (book section "The Pattern")
    * The game world keeps a collection of objects (``World.entities``).
    * Each object implements ``update(dt)``: "simulate one frame of yourself".
    * Each fixed step of the game loop (p08) calls ``world.update(dt)``, which
      calls ``update`` on every object.

WHERE IT IS USED IN THE GAME
    Pac-Man, the ghosts and the fruit are all Entities in one World. The game
    loop calls ``world.update(DT)`` sixty times a second.

KEEP IN MIND (book section "Keep in Mind")
    * "Splitting code into single frame slices makes it more complex" and
      "You have to store state to resume where you left off each frame":
      that is why ghosts need the State pattern (p06): the state object
      remembers what the ghost was doing between updates.
    * "Objects all simulate each frame but are not truly concurrent":
      Blinky moves before Pinky, so Pinky sees Blinky's *new* position. For
      Pac-Man that doesn't matter: collisions are checked after everybody has
      moved.
    * "Be careful modifying the object list while updating": objects added
      during an update go into ``_pending`` and join *after* the loop, so
      they don't update in the frame they were born. Removed objects are only
      marked dead (``alive = False``) and swept out after the loop, so
      the iteration never skips anybody.

SAMPLE CODE NOTES
    * "Subclassing entities?!": the book warns that deep entity hierarchies
      don't scale and points to the Component pattern. That is exactly where
      we go in p13_component.py: our Entity stays tiny.
    * "Passing time": with the fixed time step from p08, ``dt`` is always
      1/60 s. We still pass it in so the code reads naturally (speed * dt).
    * "How are dormant objects handled?" (Design Decisions): an entity
      with ``active = False`` stays in the list but isn't updated or drawn
      (the fruit, while it's off screen).

INTERPOLATION
    Each entity remembers its previous position. ``lerp_position(alpha)``
    gives the in-between position the game loop's "Stuck in the middle"
    rendering needs (see p08).
"""
from support.constants import TILE


class Entity:
    """Something in the world that updates itself every frame."""

    def __init__(self, x: float = 0.0, y: float = 0.0):
        self.x = x
        self.y = y
        self.prev_x = x
        self.prev_y = y
        self.alive = True     # False -> removed from the world after this update
        self.active = True    # False -> dormant: kept, but not updated or drawn
        self.world = None

    def place(self, x: float, y: float) -> None:
        """Teleport (no interpolation from the old position)."""
        self.x = self.prev_x = x
        self.y = self.prev_y = y

    def update(self, dt: float) -> None:
        """Simulate one fixed step. Subclasses override."""

    def render(self, surface, alpha: float) -> None:
        """Draw at the interpolated position. Subclasses override."""

    def lerp_position(self, alpha: float):
        """Position ``alpha`` of the way from the previous to the current update."""
        # Jumped through the tunnel? Then don't slide across the whole screen.
        if abs(self.x - self.prev_x) > TILE or abs(self.y - self.prev_y) > TILE:
            return self.x, self.y
        return (self.prev_x + (self.x - self.prev_x) * alpha,
                self.prev_y + (self.y - self.prev_y) * alpha)


class World:
    """The collection of entities and the update loop over them."""

    def __init__(self):
        self.entities = []
        self._pending = []
        self._updating = False
        self.updates = 0

    def add(self, entity: Entity) -> Entity:
        entity.world = self
        if self._updating:
            self._pending.append(entity)   # joins after this update
        else:
            self.entities.append(entity)
        return entity

    def remove(self, entity: Entity) -> None:
        entity.alive = False               # swept out after the update loop

    def update(self, dt: float) -> None:
        self._updating = True
        for entity in self.entities:
            # Remember the old position for interpolation, then simulate.
            entity.prev_x, entity.prev_y = entity.x, entity.y
            if entity.alive and entity.active:
                entity.update(dt)
        self._updating = False
        self.updates += 1
        if any(not e.alive for e in self.entities):
            self.entities = [e for e in self.entities if e.alive]
        if self._pending:
            self.entities.extend(self._pending)
            self._pending.clear()

    def render(self, surface, alpha: float) -> None:
        for entity in self.entities:
            if entity.alive and entity.active:
                entity.render(surface, alpha)
