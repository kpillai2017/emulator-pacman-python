"""
Pattern 11 of 19 - SUBCLASS SANDBOX
===================================
Book: "Behavioral Patterns > Subclass Sandbox"
      https://gameprogrammingpatterns.com/subclass-sandbox.html

  "Define behavior in a subclass using a set of operations provided by its
   base class."

THE PROBLEM (book section "Motivation")
    The book's example is superpowers: dozens of them, each written by a
    different programmer, each reaching into audio, particles, physics...
    The result is coupling everywhere. Our version: bonus fruit. Every fruit
    gives points, and each one has a different extra effect (freeze the
    ghosts, speed boost, extra life...).

THE PATTERN (book section "The Pattern")
    * The base class ``Bonus`` defines an abstract *sandbox method*,
      ``activate()``, which each fruit implements.
    * The base class also provides *provided operations*: ``_add_score``,
      ``_play_sound``, ``_spawn_particles``, ``_show_popup``,
      ``_freeze_ghosts``, ``_frighten_ghosts``, ``_boost_pacman`` and
      ``_add_life``. (A leading underscore is Python's "protected": meant for
      subclasses only.)
    * Subclasses ONLY use those operations. They never import audio, the
      particle system or the ghosts, so all the coupling is concentrated in
      one place: the base class.

WHERE IT IS USED IN THE GAME
    Eating a fruit calls ``fruit.activate()`` (app/game.py). Compare the
    subclasses at the bottom: each is a few lines of "what", and the base
    class owns the "how".

DESIGN DECISIONS (book section "Design Decisions")
    * "What operations should be provided?": just what the fruits need, kept
      small and high level.
    * "Should methods be provided directly, or through objects that contain
      them?": directly, because there are only a few.
    * "How does the base class get the state that it needs?": the book lists
      constructor, *two-stage initialization*, static state and a service
      locator. We use two-stage init: the fruit is cloned by a Spawner
      (Prototype, p04) and then ``init(context)`` hands it the game. (Sound goes
      through the context, which uses the Service Locator, p15.)

ALSO
    Each fruit is an ``Entity`` (p09): it updates itself (counts down and
    disappears) and a ``Prototype`` (p04): the level's Spawner clones it.
"""
from support import drawing
from patterns.p04_prototype import Prototype
from patterns.p09_update_method import Entity


class Bonus(Entity, Prototype):
    """Base class: the sandbox. Subclasses implement ``activate``."""
    kind = "bonus"
    points = 0
    lifetime = 9.5    # seconds on screen

    def __init__(self):
        Entity.__init__(self)
        self.timer = self.lifetime
        self._context = None

    def init(self, context) -> "Bonus":
        """Second stage of two-stage initialisation: give the sandbox its world."""
        self._context = context
        self.timer = self.lifetime
        return self

    # -- Entity (Update Method) ---------------------------------------------------
    def update(self, dt: float) -> None:
        self.timer -= dt
        if self.timer <= 0:
            self.alive = False       # the world sweeps it out (p09)

    def render(self, surface, alpha: float) -> None:
        drawing.fruit(surface, self.x, self.y, self.kind)

    # -- the sandbox method ------------------------------------------------------
    def activate(self) -> None:
        raise NotImplementedError

    # -- provided operations ------------------------------------------------------
    def _add_score(self, points: int) -> None:
        self._context.bonus_score(self, points)

    def _play_sound(self, name: str) -> None:
        self._context.play_sound(name)

    def _spawn_particles(self, count: int) -> None:
        colour = drawing.FRUIT_COLOURS.get(self.kind, (255, 255, 255))
        self._context.spawn_particles(self.x, self.y, count, colour)

    def _show_popup(self, text: str, colour=(255, 184, 255)) -> None:
        self._context.show_popup(self.x, self.y, text, colour)

    def _freeze_ghosts(self, seconds: float) -> None:
        self._context.freeze_ghosts(seconds)

    def _frighten_ghosts(self) -> None:
        self._context.frighten_ghosts()

    def _boost_pacman(self, seconds: float) -> None:
        self._context.boost_pacman(seconds)

    def _add_life(self) -> None:
        self._context.add_life()


# ---------------------------------------------------------------------------
# The subclasses: short, readable, and decoupled from every game system.
# ---------------------------------------------------------------------------
class Cherry(Bonus):
    kind, points = "cherry", 100

    def activate(self):
        self._add_score(self.points)
        self._spawn_particles(12)
        self._show_popup(str(self.points))


class Strawberry(Bonus):
    kind, points = "strawberry", 300

    def activate(self):
        self._add_score(self.points)
        self._freeze_ghosts(1.5)
        self._spawn_particles(16)
        self._show_popup(f"{self.points} FREEZE!")


class Orange(Bonus):
    kind, points = "orange", 500

    def activate(self):
        self._add_score(self.points)
        self._boost_pacman(5.0)
        self._spawn_particles(16)
        self._show_popup(f"{self.points} SPEED!")


class Apple(Bonus):
    kind, points = "apple", 700

    def activate(self):
        self._add_score(self.points)
        self._frighten_ghosts()
        self._spawn_particles(20)
        self._show_popup(f"{self.points} SCARE!")


class Melon(Bonus):
    kind, points = "melon", 1000

    def activate(self):
        self._add_score(self.points)
        self._freeze_ghosts(3.0)
        self._spawn_particles(24)
        self._show_popup(f"{self.points} FREEZE!")


class Galaxian(Bonus):
    kind, points = "galaxian", 2000

    def activate(self):
        self._add_score(self.points)
        self._boost_pacman(6.0)
        self._freeze_ghosts(1.0)
        self._spawn_particles(30)
        self._show_popup(f"{self.points} WARP!")


class Bell(Bonus):
    kind, points = "bell", 3000

    def activate(self):
        self._add_score(self.points)
        self._frighten_ghosts()
        self._play_sound("achievement")
        self._spawn_particles(30)
        self._show_popup(f"{self.points} DING!")


class Key(Bonus):
    kind, points = "key", 5000

    def activate(self):
        self._add_score(self.points)
        self._add_life()
        self._spawn_particles(40)
        self._show_popup(f"{self.points} 1UP!")


# The arcade's fruit order by level; the key repeats forever after level 13.
FRUIT_BY_LEVEL = [Cherry, Strawberry, Orange, Orange, Apple, Apple, Melon, Melon,
                  Galaxian, Galaxian, Bell, Bell, Key]


def fruit_prototype_for(level: int) -> Bonus:
    """One prototype instance per level, for the Spawner (p04) to clone."""
    cls = FRUIT_BY_LEVEL[min(level, len(FRUIT_BY_LEVEL)) - 1]
    return cls()
