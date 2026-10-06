"""
Pattern 1 of 19 - COMMAND
=========================
Book: "Design Patterns Revisited > Command"
      https://gameprogrammingpatterns.com/command.html

  "A command is a *reified method call*": a method call wrapped in an object.

THE PROBLEM
    The naive way to read input hard-wires keys to actions:

        if input.key_down(K_UP):  pacman.move_up()
        if input.key_down(K_P):   game.pause()

    Players can't rebind keys, and nothing *except* the keyboard can drive
    Pac-Man (no demo mode, no AI).

THE PATTERN
    1. Define a tiny base class with one method, ``execute``.
    2. Each action becomes a subclass (MoveCommand, PauseCommand, ...).
    3. The InputHandler keeps a *table* from key -> command object.
       Rebinding a key is just replacing a table entry
       (book section "Configuring Input").
    4. ``execute`` takes the *actor* to act on, so the same MoveCommand can
       steer Pac-Man, or anything else that can steer
       (book section "Directions for Actors").

WHERE IT IS USED IN THE GAME
    * PlayerInputComponent (p13_component.py) asks the InputHandler for a
      MoveCommand each update and executes it on Pac-Man.
    * DemoInputComponent (p13_component.py) is an AI that produces the *same*
      MoveCommand objects in the attract-mode demo. Pac-Man can't tell whether a
      human or the computer is playing: the book's point about commands as an
      interface between "controllers" and "actors".
    * Game-level keys (pause, mute, debug overlay, start, quit) are commands
      executed on the game object (app/game.py ``process_input``).

UNDO AND REDO (book section "Undo and Redo")
    Commands that remember enough to reverse themselves give you undo. Pac-Man
    has no natural undo, so this game doesn't use it, but see
    ``CommandHistory`` at the bottom of this file for the minimal shape of it
    (it is exercised by tests/test_patterns.py).

"CLASSY AND DYSFUNCTIONAL?"
    In Python a command could just be a function or a lambda (closures are the
    book's "functional" alternative). Classes are used here because they show
    the idea more explicitly and can carry ``undo`` and a readable ``name``.
"""
import pygame

from support.constants import Direction


# ---------------------------------------------------------------------------
# The command interface
# ---------------------------------------------------------------------------
class Command:
    """Base class: one method, ``execute(target)``."""
    name = "command"

    def execute(self, target) -> None:
        raise NotImplementedError

    def undo(self, target) -> None:
        """Optional: reverse ``execute``. Most commands here are not undoable."""
        raise NotImplementedError(f"{self.name} cannot be undone")

    def __repr__(self) -> str:
        return f"<{self.name}>"


# ---------------------------------------------------------------------------
# Actor commands: executed on whatever "actor" they are given.
# The only thing they need from the actor is a ``steer(direction)`` method.
# ---------------------------------------------------------------------------
class MoveCommand(Command):
    """Ask an actor to head in a direction (it turns as soon as the maze allows)."""

    def __init__(self, direction: Direction):
        self.direction = direction
        self.name = f"move {direction.name.lower()}"

    def execute(self, actor) -> None:
        actor.steer(self.direction)


# The four move commands carry no per-use state, so one shared instance of each
# is enough (a small taste of the next pattern, Flyweight).
MOVE_UP = MoveCommand(Direction.UP)
MOVE_DOWN = MoveCommand(Direction.DOWN)
MOVE_LEFT = MoveCommand(Direction.LEFT)
MOVE_RIGHT = MoveCommand(Direction.RIGHT)


# ---------------------------------------------------------------------------
# Game commands: executed on the game object.
# ---------------------------------------------------------------------------
class PauseCommand(Command):
    name = "pause"

    def execute(self, game) -> None:
        game.toggle_pause()


class MuteCommand(Command):
    name = "mute"

    def execute(self, game) -> None:
        game.toggle_mute()


class DebugOverlayCommand(Command):
    name = "debug overlay"

    def execute(self, game) -> None:
        game.toggle_debug()


class PanelCommand(Command):
    name = "toggle panel"

    def execute(self, game) -> None:
        game.toggle_panel()


class StartCommand(Command):
    name = "start"

    def execute(self, game) -> None:
        game.start_pressed()


class QuitCommand(Command):
    name = "quit"

    def execute(self, game) -> None:
        game.end()


# ---------------------------------------------------------------------------
# The input handler: a table from keys to commands.
# ---------------------------------------------------------------------------
class InputHandler:
    """Translates key presses into Command objects.

    ``core.input.Input`` (the engine) tells us *which keys* are down; this class
    decides *what they mean*. Nothing here knows about Pac-Man.
    """

    def __init__(self):
        # Held keys -> actor commands (both arrows and WASD work).
        self.move_bindings = {
            pygame.K_UP: MOVE_UP, pygame.K_w: MOVE_UP,
            pygame.K_DOWN: MOVE_DOWN, pygame.K_s: MOVE_DOWN,
            pygame.K_LEFT: MOVE_LEFT, pygame.K_a: MOVE_LEFT,
            pygame.K_RIGHT: MOVE_RIGHT, pygame.K_d: MOVE_RIGHT,
        }
        # Key *hits* (pressed this frame) -> game commands.
        self.game_bindings = {
            pygame.K_p: PauseCommand(),
            pygame.K_m: MuteCommand(),
            pygame.K_TAB: DebugOverlayCommand(),
            pygame.K_F1: PanelCommand(),
            pygame.K_RETURN: StartCommand(),
            pygame.K_SPACE: StartCommand(),
            pygame.K_ESCAPE: QuitCommand(),
        }
        self._last_move_key = None

    # "Configuring Input": rebinding is just a dictionary update.
    def bind_move(self, key: int, command: Command) -> None:
        self.move_bindings[key] = command

    def bind_game(self, key: int, command: Command) -> None:
        self.game_bindings[key] = command

    def handle_actor_input(self, core_input):
        """Return the MoveCommand for the held direction key, or None.

        If several direction keys are held, the most recently pressed one wins,
        which feels right when "rolling" from one arrow key to the next.
        """
        for key in self.move_bindings:
            if core_input.key_hit(key):
                self._last_move_key = key
        if self._last_move_key is not None and core_input.key_down(self._last_move_key):
            return self.move_bindings[self._last_move_key]
        for key, command in self.move_bindings.items():
            if core_input.key_down(key):
                return command
        return None

    def handle_game_input(self, core_input):
        """Return the list of game commands whose key was pressed this frame."""
        return [command for key, command in self.game_bindings.items()
                if core_input.key_hit(key)]


# ---------------------------------------------------------------------------
# Undo/redo, as in the book's "Undo and Redo" section (not used by the game).
# ---------------------------------------------------------------------------
class CommandHistory:
    """A list of executed commands plus a "current" index, exactly the book's design."""

    def __init__(self):
        self.done = []
        self.current = -1

    def execute(self, command: Command, target) -> None:
        command.execute(target)
        del self.done[self.current + 1:]   # a new command discards the redo tail
        self.done.append(command)
        self.current += 1

    def undo(self, target) -> None:
        if self.current >= 0:
            self.done[self.current].undo(target)
            self.current -= 1

    def redo(self, target) -> None:
        if self.current + 1 < len(self.done):
            self.current += 1
            self.done[self.current].execute(target)
