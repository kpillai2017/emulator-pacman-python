"""
Pattern 6 of 19 - STATE
=======================
Book: "Design Patterns Revisited > State"
      https://gameprogrammingpatterns.com/state.html

  "Allow an object to alter its behavior when its internal state changes.
   The object will appear to change its class."

THE PROBLEM (book section "We've All Been There")
    A ghost behaves completely differently depending on what it is doing:
    waiting in the house, leaving it, scattering to its corner, chasing
    Pac-Man, running away while blue, or flying home as a pair of eyes. With
    booleans (is_blue, is_eaten, is_in_house...) and if-statements, the
    combinations quickly become impossible to keep correct.

FINITE STATE MACHINES (book section "Finite State Machines to the Rescue")
    A fixed set of states; the machine is in exactly one at a time; inputs
    cause transitions. The book first shows "Enums and Switches", then:

THE STATE PATTERN (book section "The State Pattern")
    * "A state interface": ``State`` with ``enter``, ``exit``, ``update``
      and ``handle``.
    * "Classes for each state": InHouse, LeavingHouse, Scatter, Chase,
      Frightened, Eaten, EnteringHouse.
    * "Delegate to the state": the owner's ``StateMachine`` forwards
      ``update``/``handle`` to the current state object.
    * "Instantiated states" (not "Static states"): each ghost gets fresh
      state objects because they hold per-ghost data such as timers.
    * "Enter and Exit Actions": e.g. entering Frightened sets the timer and
      the blue look; entering Eaten switches to "eyes" and the fast speed.

HIERARCHICAL STATE MACHINES (book section of the same name)
    Scatter and Chase share most behaviour: both react to a power pellet the
    same way and both follow the global scatter/chase timer. They inherit from
    a ``Roaming`` super-state that handles those. A subclass only says how
    to pick a target tile. The book does this with an ``OnGroundState`` base.

PUSHDOWN AUTOMATA (book section of the same name)
    ``PushdownAutomaton`` keeps a *stack* of states. Pausing the game
    *pushes* a Paused state over Playing; un-pausing *pops* it and Playing
    resumes exactly where it was. app/game_states.py uses it for the game flow
    (Attract -> Ready -> Playing -> Dying / LevelComplete -> GameOver).

CONCURRENT STATE MACHINES (book section of the same name)
    Each ghost has its own machine running at the same time as the game-flow
    machine. They are independent, which avoids a combinatorial explosion of
    "game-playing-and-ghost-blue" states.

THE GHOST INTERFACE THESE STATES EXPECT
    The ghost object itself is built from components in p13_component.py. The
    states only rely on these attributes (Python "duck typing"):
        x, y, direction, target, speed, look, on_rails, random_turns
        breed (p12), brain (its StateMachine), world, reverse(), chase_target()
    and on these from ``ghost.world``:
        ghost_mode ("scatter"/"chase"), fright_seconds, maze, speed_scale,
        pacman (for Elroy).
"""
from support.constants import TILE, FULL_SPEED, Direction, tile_of
from support.maze_layout import GHOST_DOOR, HOUSE_CENTRE_Y
from patterns.p03_observer import Event


# ---------------------------------------------------------------------------
# The generic machinery
# ---------------------------------------------------------------------------
class State:
    """The state interface. Every method receives the object that owns the machine."""
    name = "state"

    def enter(self, owner) -> None:
        pass

    def exit(self, owner) -> None:
        pass

    def update(self, owner, dt: float) -> None:
        pass

    def handle(self, owner, event, data) -> bool:
        """React to an input or event. Return True if it was handled."""
        return False

    def resume(self, owner) -> None:
        """Pushdown automata only: the state above this one was popped."""
        pass


class StateMachine:
    """Holds the current state and delegates to it."""

    def __init__(self, owner, initial: State = None):
        self.owner = owner
        self.state = None
        self.transitions = 0
        if initial is not None:
            self.change(initial)

    def change(self, new_state: State) -> None:
        if self.state is not None:
            self.state.exit(self.owner)          # exit action of the old state
        self.state = new_state
        self.transitions += 1
        new_state.enter(self.owner)              # enter action of the new state

    def update(self, dt: float) -> None:
        if self.state is not None:
            self.state.update(self.owner, dt)

    def handle(self, event, data=None) -> bool:
        return self.state is not None and self.state.handle(self.owner, event, data or {})


class PushdownAutomaton:
    """A stack of states: ``push`` to interrupt, ``pop`` to return."""

    def __init__(self, owner):
        self.owner = owner
        self.stack = []

    @property
    def state(self):
        return self.stack[-1] if self.stack else None

    def push(self, state: State) -> None:
        self.stack.append(state)
        state.enter(self.owner)

    def pop(self) -> None:
        self.stack.pop().exit(self.owner)
        if self.stack:
            self.stack[-1].resume(self.owner)

    def change(self, state: State) -> None:
        """Replace the top state (a plain FSM transition)."""
        if self.stack:
            self.stack.pop().exit(self.owner)
        self.push(state)

    def update(self, dt: float) -> None:
        if self.stack:
            self.stack[-1].update(self.owner, dt)   # only the top state runs

    def handle(self, event, data=None) -> bool:
        return bool(self.stack) and self.stack[-1].handle(self.owner, event, data or {})

    def names(self):
        return [s.name for s in self.stack]


# ---------------------------------------------------------------------------
# Ghost states
# ---------------------------------------------------------------------------
DOOR_X = GHOST_DOOR[0] * TILE          # pixel x of the gate's centre line
DOOR_Y = GHOST_DOOR[1] * TILE          # pixel y just outside the gate
HOUSE_Y = HOUSE_CENTRE_Y * TILE
DOOR_TILES = {(13, 11), (14, 11)}


def _move_towards(ghost, tx: float, ty: float, distance: float) -> bool:
    """Move straight towards a point, x first then y. True when arrived.

    Used inside the ghost house, where ghosts don't follow the maze grid.
    """
    if abs(ghost.x - tx) > 0.01:
        step = min(distance, abs(tx - ghost.x))
        ghost.direction = Direction.RIGHT if tx > ghost.x else Direction.LEFT
        ghost.x += step if tx > ghost.x else -step
        return False
    ghost.x = tx
    if abs(ghost.y - ty) > 0.01:
        step = min(distance, abs(ty - ghost.y))
        ghost.direction = Direction.DOWN if ty > ghost.y else Direction.UP
        ghost.y += step if ty > ghost.y else -step
        return False
    ghost.y = ty
    return True


def roaming_state_for(mode: str) -> State:
    """The state matching the global scatter/chase timer."""
    return Chase() if mode == "chase" else Scatter()


class GhostState(State):
    """Defaults shared by all ghost states."""
    edible = False       # can Pac-Man eat the ghost in this state?
    dangerous = False    # does touching the ghost kill Pac-Man?
    look = "normal"
    on_rails = True      # moved by the maze-following component?

    def enter(self, ghost) -> None:
        ghost.look = self.look
        ghost.on_rails = self.on_rails
        ghost.random_turns = False


class InHouse(GhostState):
    """Bob up and down inside the house until the breed's release time."""
    name = "in house"
    on_rails = False

    def __init__(self, delay: float = None):
        self.delay = delay

    def enter(self, ghost) -> None:
        super().enter(ghost)
        self.timer = ghost.breed.release_delay if self.delay is None else self.delay
        if ghost.direction not in (Direction.UP, Direction.DOWN):
            ghost.direction = Direction.UP

    def update(self, ghost, dt) -> None:
        self.timer -= dt
        speed = FULL_SPEED * 0.4 * dt
        ghost.y += ghost.direction.dy * speed
        if ghost.y < HOUSE_Y - TILE / 2:
            ghost.y, ghost.direction = HOUSE_Y - TILE / 2, Direction.DOWN
        elif ghost.y > HOUSE_Y + TILE / 2:
            ghost.y, ghost.direction = HOUSE_Y + TILE / 2, Direction.UP
        if self.timer <= 0:
            ghost.brain.change(LeavingHouse())

    def handle(self, ghost, event, data) -> bool:
        return event == Event.POWER_PELLET_EATEN    # ignored inside the house


class LeavingHouse(GhostState):
    """Line up with the gate, float up through it, then start roaming."""
    name = "leaving house"
    on_rails = False

    def update(self, ghost, dt) -> None:
        distance = FULL_SPEED * 0.5 * dt
        if abs(ghost.x - DOOR_X) > 0.01:
            _move_towards(ghost, DOOR_X, ghost.y, distance)
        elif _move_towards(ghost, DOOR_X, DOOR_Y, distance):
            ghost.direction = Direction.LEFT
            ghost.brain.change(roaming_state_for(ghost.world.ghost_mode))

    def handle(self, ghost, event, data) -> bool:
        return event == Event.POWER_PELLET_EATEN


class Roaming(GhostState):
    """Super-state of Scatter and Chase (a hierarchical state machine)."""
    dangerous = True
    mode = None

    def choose_target(self, ghost):
        raise NotImplementedError   # the only thing sub-states must provide

    def update(self, ghost, dt) -> None:
        world = ghost.world
        # Follow the global scatter/chase schedule. The arcade ghosts reverse
        # direction whenever the mode changes: a hint to the player.
        if world.ghost_mode != self.mode:
            ghost.reverse()
            ghost.brain.change(roaming_state_for(world.ghost_mode))
            return
        ghost.target = self.choose_target(ghost)
        ghost.speed = roaming_speed(ghost)

    def handle(self, ghost, event, data) -> bool:
        if event == Event.POWER_PELLET_EATEN:
            ghost.reverse()
            if ghost.world.fright_seconds > 0:
                ghost.brain.change(Frightened())
            return True
        return False


def roaming_speed(ghost) -> float:
    """Ghost speed from its breed (Type Object), the tunnel and Elroy mode."""
    breed, world = ghost.breed, ghost.world
    col, row = tile_of(ghost.x, ghost.y)
    if world.maze.tile(col, row).slows_ghosts:
        factor = breed.tunnel_speed
    elif breed.elroy_dots and world.maze.dots_left <= breed.elroy_dots:
        factor = breed.elroy_speed            # Blinky's "Cruise Elroy" speed-up
    else:
        factor = breed.speed
    return FULL_SPEED * factor * world.speed_scale


class Scatter(Roaming):
    """Head for the breed's home corner."""
    name = "scatter"
    mode = "scatter"

    def choose_target(self, ghost):
        return tuple(ghost.breed.scatter_corner)


class Chase(Roaming):
    """Target chosen by the breed's bytecode program (p10_bytecode.py)."""
    name = "chase"
    mode = "chase"

    def choose_target(self, ghost):
        return ghost.chase_target()


class Frightened(GhostState):
    """Blue, slow, wandering at random. Pac-Man can eat it."""
    name = "frightened"
    edible = True
    look = "frightened"
    FLASH_SECONDS = 2.0

    def enter(self, ghost) -> None:
        super().enter(ghost)
        self.timer = ghost.world.fright_seconds
        ghost.random_turns = True
        ghost.target = None

    def update(self, ghost, dt) -> None:
        self.timer -= dt
        if self.timer <= 0:
            ghost.brain.change(roaming_state_for(ghost.world.ghost_mode))
            return
        flashing = self.timer < self.FLASH_SECONDS and int(self.timer * 5) % 2 == 0
        ghost.look = "flash" if flashing else "frightened"
        col, row = tile_of(ghost.x, ghost.y)
        factor = ghost.breed.tunnel_speed if ghost.world.maze.tile(col, row).slows_ghosts \
            else ghost.breed.frightened_speed
        ghost.speed = FULL_SPEED * factor * ghost.world.speed_scale

    def handle(self, ghost, event, data) -> bool:
        if event == Event.POWER_PELLET_EATEN:   # another pellet: start again
            ghost.reverse()
            self.timer = ghost.world.fright_seconds
            return True
        return False


class Eaten(GhostState):
    """Just a pair of eyes racing back to the house."""
    name = "eaten"
    look = "eyes"

    def update(self, ghost, dt) -> None:
        ghost.target = (13, 11)
        ghost.speed = FULL_SPEED * ghost.breed.eaten_speed
        if tile_of(ghost.x, ghost.y) in DOOR_TILES:
            ghost.brain.change(EnteringHouse())

    def handle(self, ghost, event, data) -> bool:
        return event == Event.POWER_PELLET_EATEN   # eyes don't care


class EnteringHouse(GhostState):
    """Eyes drop through the gate; once inside, the ghost revives."""
    name = "entering house"
    look = "eyes"
    on_rails = False

    def update(self, ghost, dt) -> None:
        distance = FULL_SPEED * ghost.breed.eaten_speed * dt
        if abs(ghost.y - DOOR_Y) > 0.01 and abs(ghost.x - DOOR_X) > 0.01:
            _move_towards(ghost, ghost.x, DOOR_Y, distance)   # finish leaving the corridor
        elif _move_towards(ghost, DOOR_X, HOUSE_Y, distance):
            ghost.brain.change(LeavingHouse())
            ghost.look = "normal"

    def handle(self, ghost, event, data) -> bool:
        return event == Event.POWER_PELLET_EATEN
