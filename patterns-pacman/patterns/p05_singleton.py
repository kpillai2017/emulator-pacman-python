"""
Pattern 5 of 19 - SINGLETON
===========================
Book: "Design Patterns Revisited > Singleton"
      https://gameprogrammingpatterns.com/singleton.html

  "Ensure a class has one instance, and provide a global point of access to it."

This is the one chapter where the book mostly argues *against* the pattern,
so this file is mostly discussion and a deliberately small example.

THE PATTERN (book section "The Singleton Pattern")
    Two promises in one:
      1. "Restricting a class to one instance": constructing it again hands
         back the same object.
      2. "Providing a global point of access": anyone, anywhere, can call
         ``Settings.instance()``.

WHY WE REGRET USING IT (book section "Why We Regret Using It")
    * "It's a global variable": any code can read and change it, so bugs
      can come from anywhere, and a function's real inputs are hidden.
    * "It solves two problems even when you just have one": often you only
      want *convenient access*, not "exactly one".
    * "Lazy initialization takes control away from you": it's created when
      first touched, which may be in the middle of gameplay.
    * Tests can't easily get a fresh one. Note the ``_reset_for_tests``
      hack below: that is the smell the book warns about.

WHAT WE DO INSTEAD (book section "What We Can Do Instead")
    * Most objects in this game are simply *passed in* to the code that
      needs them (the maze, the scoreboard, the event subject...).
    * Audio is reachable from anywhere through a *Service Locator* (pattern 15),
      which keeps global access but lets us swap the implementation (mute,
      logging) and fall back to a do-nothing "null" service.

WHERE IT IS USED IN THE GAME
    ``Settings`` is the one singleton: the debug flags you toggle with Tab and
    F1, plus command-line options. These really are global, rarely written,
    and harmless if read anywhere: the book's "What's Left for Singleton".

PYTHON NOTE
    In Python a *module* is already a singleton (it is imported once), so
    module-level variables are the idiomatic choice. The class version is
    shown because it maps directly onto the book.
"""


class Settings:
    """Global debug and display settings. Only one instance can exist."""

    _instance = None

    def __new__(cls):
        # Promise 1: "Restricting a class to one instance".
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._init_defaults()
            cls._instance = instance
        return cls._instance

    @classmethod
    def instance(cls) -> "Settings":
        # Promise 2: "Providing a global point of access" (created lazily).
        return cls()

    def _init_defaults(self) -> None:
        self.show_debug = False       # Tab: ghost targets, collision grid, tile changes
        self.show_panel = True        # F1: the patterns panel
        self.log_audio = False        # --log-audio: wrap audio in the logging decorator (p15)
        self.invincible = False       # --invincible: ghosts can't kill Pac-Man (for study)
        self.start_level = 1          # --level N

    @classmethod
    def _reset_for_tests(cls) -> None:
        """Tests need a fresh singleton: the book's "hard to test" complaint."""
        cls._instance = None
