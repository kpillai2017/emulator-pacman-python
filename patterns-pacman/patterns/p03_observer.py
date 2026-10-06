"""
Pattern 3 of 19 - OBSERVER
==========================
Book: "Design Patterns Revisited > Observer"
      https://gameprogrammingpatterns.com/observer.html

  "Define a one-to-many dependency between objects so that when one object
   changes state, all its dependents are notified and updated automatically."

THE PROBLEM (book section "Achievement Unlocked")
    When Pac-Man eats a power pellet, lots of unrelated things care: the
    score goes up, a sound plays, all four ghosts turn blue, an achievement may
    unlock. If the eating code called each of them directly, the gameplay code
    would be tangled up with scoring, audio and achievements.

THE PATTERN (book section "How it Works")
    * A ``Subject`` keeps a list of ``Observer`` objects.
    * When something interesting happens, the subject calls ``notify``, which
      calls ``on_notify(entity, event, data)`` on every observer.
    * The subject doesn't know or care what the observers do.

WHERE IT IS USED IN THE GAME
    The game's rules (app/game.py) own one Subject and announce events:
    DOT_EATEN, POWER_PELLET_EATEN, GHOST_EATEN, FRUIT_EATEN, PACMAN_DIED,
    LEVEL_CLEARED... The observers are:
      * ``Scoreboard`` (below): adds points, awards an extra life at 10,000.
      * ``Achievements`` (below): the book's own example.
      * every ghost's brain (p13_component.py): a power pellet makes it
        frightened. The pellet code doesn't even know ghosts exist!
      * ``AudioObserver`` (p15_service_locator.py): plays sounds.
    In attract mode the game *removes* the achievement and audio observers,
    so the demo is silent and can't unlock anything (see app/game_states.py).
    That is the "Destroying subjects and observers" bookkeeping in practice.

KEEP IN MIND (book sections "It's Too Slow" / "It's too *fast*?")
    Notification is a plain, synchronous method call: cheap, but the subject
    waits until every observer returns. Observers must not do slow work in
    ``on_notify``. When you want "send it now, handle it later", you need an
    Event Queue, which is pattern 14.

    The book's "Linked observers" / "A pool of list nodes" sections avoid
    dynamic allocation in C++. In Python a list is the natural choice. We
    iterate over a *copy* of the list so that an observer may unsubscribe
    while being notified.
"""
from enum import Enum, auto


class Event(Enum):
    DOT_EATEN = auto()
    POWER_PELLET_EATEN = auto()
    GHOST_EATEN = auto()
    FRUIT_EATEN = auto()
    PACMAN_DIED = auto()
    LEVEL_CLEARED = auto()
    LEVEL_STARTED = auto()
    GAME_STARTED = auto()
    EXTRA_LIFE = auto()
    ACHIEVEMENT_UNLOCKED = auto()


class Observer:
    """Anything that wants to hear about events implements ``on_notify``."""

    def on_notify(self, entity, event: Event, data: dict) -> None:
        raise NotImplementedError


class Subject:
    """Keeps a list of observers and notifies them."""

    def __init__(self):
        self._observers = []
        self.notifications = 0   # for the side panel

    def add_observer(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def has_observer(self, observer: Observer) -> bool:
        return observer in self._observers

    @property
    def observer_count(self) -> int:
        return len(self._observers)

    def notify(self, entity, event: Event, data: dict = None) -> None:
        self.notifications += 1
        data = data or {}
        for observer in list(self._observers):   # copy: observers may unsubscribe
            observer.on_notify(entity, event, data)


# ---------------------------------------------------------------------------
# Observer #1: the scoreboard
# ---------------------------------------------------------------------------
EXTRA_LIFE_SCORE = 10000


class Scoreboard(Observer):
    """Turns events into points. It never looks at Pac-Man or the maze."""

    def __init__(self, subject: Subject):
        self.subject = subject   # to announce EXTRA_LIFE (an observer can be a subject too)
        self.score = 0
        self.high_score = 0
        self.lives = 3
        self.level = 1
        self.extra_life_awarded = False
        self.version = 0         # bumps on every change: the HUD's dirty flag (p17)

    def new_game(self) -> None:
        self.score = 0
        self.lives = 3
        self.level = 1
        self.extra_life_awarded = False
        self.version += 1

    def on_notify(self, entity, event, data) -> None:
        points = data.get("points", 0)
        if points:
            self.score += points
            self.high_score = max(self.high_score, self.score)
            self.version += 1
        if event == Event.PACMAN_DIED:
            self.lives -= 1
            self.version += 1
        elif event == Event.EXTRA_LIFE:
            self.lives += 1
            self.version += 1
        elif event == Event.LEVEL_STARTED:
            self.level = data.get("level", self.level)
            self.version += 1
        if not self.extra_life_awarded and self.score >= EXTRA_LIFE_SCORE:
            self.extra_life_awarded = True
            self.subject.notify(self, Event.EXTRA_LIFE, {})


# ---------------------------------------------------------------------------
# Observer #2: achievements, the book's motivating example.
# ---------------------------------------------------------------------------
class Achievements(Observer):
    """Unlocks badges by listening to gameplay events."""

    DEFINITIONS = {
        "first_bite": "First Bite: eat a ghost",
        "ghost_buster": "Ghost Buster: 4 ghosts, 1 pellet",
        "fruit_salad": "Fruit Salad: eat 2 fruits",
        "clean_sweep": "Clean Sweep: clear a level",
        "hungry": "Hungry: 500 dots in one game",
    }

    def __init__(self, subject: Subject):
        self.subject = subject
        self.unlocked = []          # keys, in unlock order
        self._ghost_combo = 0
        self._fruits = 0
        self._dots = 0

    def on_notify(self, entity, event, data) -> None:
        if event == Event.GAME_STARTED:
            self._fruits = self._dots = 0
        elif event == Event.POWER_PELLET_EATEN:
            self._ghost_combo = 0
            self._count_dot()
        elif event == Event.DOT_EATEN:
            self._count_dot()
        elif event == Event.GHOST_EATEN:
            self._ghost_combo += 1
            self._unlock("first_bite")
            if self._ghost_combo == 4:
                self._unlock("ghost_buster")
        elif event == Event.FRUIT_EATEN:
            self._fruits += 1
            if self._fruits >= 2:
                self._unlock("fruit_salad")
        elif event == Event.LEVEL_CLEARED:
            self._unlock("clean_sweep")

    def _count_dot(self):
        self._dots += 1
        if self._dots >= 500:
            self._unlock("hungry")

    def _unlock(self, key: str) -> None:
        if key in self.unlocked:
            return
        self.unlocked.append(key)
        # Announcing the unlock is itself an event: the popup and the jingle
        # are other observers' business.
        self.subject.notify(self, Event.ACHIEVEMENT_UNLOCKED,
                            {"key": key, "text": self.DEFINITIONS[key]})
