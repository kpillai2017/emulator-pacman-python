"""
Pattern 13 of 19 - COMPONENT
============================
Book: "Decoupling Patterns > Component"
      https://gameprogrammingpatterns.com/component.html

  "Allow a single entity to span multiple domains without coupling the
   domains to each other."

THE PROBLEM (book sections "The Gordian knot" / "A monolithic class")
    A Pac-Man actor touches several *domains*: input (keyboard or AI),
    physics (moving through the maze), and graphics (drawing a chomping mouth
    or a wobbling ghost). One big ``Pacman`` class mixing them all means a
    graphics programmer has to wade through input code, and nothing can be
    reused for the ghosts.

THE PATTERN (book section "Cutting the knot")
    * ``GameObject`` is a thin *container* holding shared state (position,
      direction, speed) and a few components.
    * Each *component* owns one domain:
        input    - decides where to go     (PlayerInput, DemoInput, GhostBrain)
        physics  - moves through the maze  (PacmanMover, GhostMover)
        graphics - draws it                (PacmanGraphics, GhostGraphics)
    * ``GameObject.update`` just calls ``input.update`` then
      ``physics.update``, and ``render`` calls ``graphics.render``. This is the
      book's final ``GameObject`` with ``InputComponent``, ``PhysicsComponent``
      and ``GraphicsComponent``, almost line for line.

ROBO-BJORN (book section "Robo-Bjørn")
    The book swaps a player-input component for a demo-AI component to get an
    attract mode for free. We do the same: in attract mode Pac-Man gets a
    ``DemoInputComponent`` that plays by itself. Both components emit the same
    MoveCommands (Command, p01), so the physics and graphics never notice.

NO PAC-MAN AT ALL? (book section "No Bjørn at all?")
    Ghosts are *also* GameObjects, just with different components:
    ``GhostBrain`` (input), ``GhostMover`` (physics), ``GhostGraphics``.
    Nobody wrote a Ghost class: ``make_ghost(breed)`` assembles one.

HOW COMPONENTS COMMUNICATE (book section "How do components communicate with each other?")
    The book lists three ways, and all three appear here:
      1. *By modifying the container's state*: input sets
         ``obj.desired_direction`` / ``obj.target``, physics reads them and
         updates ``obj.x/y``, and graphics reads those. This is the main channel.
      2. *By referring directly to each other*: ``make_ghost`` gives the
         container direct handles to its brain (``obj.brain``,
         ``obj.chase_target``) because the State pattern (p06) needs them.
      3. *By sending messages*: ``obj.send(message)`` forwards to every
         component's ``receive`` (used for "reset" when a life starts).

THE OTHER PATTERNS MEETING HERE
    * GhostBrain owns a StateMachine (State, p06), reads its Breed (Type Object,
      p12), runs the breed's bytecode on the VM (Bytecode, p10) and is an
      Observer (p03) of power pellets.
    * GameObject is an Entity (Update Method, p09).
"""
import math
import random
from collections import deque

from support import drawing
from support.constants import (TILE, MAZE_W, MOVES, Direction, FULL_SPEED,
                               tile_of, tile_centre)
from support.maze_layout import GHOST_DOOR, HOUSE_CENTRE_Y
from patterns.p01_command import MoveCommand
from patterns.p03_observer import Observer
from patterns.p06_state import StateMachine, InHouse, roaming_state_for
from patterns.p09_update_method import Entity

EPS = 1e-6


# ---------------------------------------------------------------------------
# Component base classes, one per domain
# ---------------------------------------------------------------------------
class Component:
    def update(self, obj, dt: float) -> None:
        pass

    def receive(self, obj, message: str, data: dict) -> None:
        """Messaging between components (optional)."""


class InputComponent(Component):
    """Decides where the object wants to go."""


class PhysicsComponent(Component):
    """Moves the object."""


class GraphicsComponent(Component):
    def render(self, obj, surface, alpha: float) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# The container
# ---------------------------------------------------------------------------
class GameObject(Entity):
    """A bag of shared state plus input, physics and graphics components."""

    def __init__(self, name: str, input_component: InputComponent,
                 physics: PhysicsComponent, graphics: GraphicsComponent):
        super().__init__()
        self.name = name
        self.input = input_component
        self.physics = physics
        self.graphics = graphics
        # Shared state: the components talk through these attributes.
        self.direction = Direction.NONE          # where it is moving
        self.desired_direction = Direction.NONE  # where input wants to go
        self.facing = Direction.LEFT             # last real direction (for drawing)
        self.speed = 0.0                         # pixels per second
        self.distance_travelled = 0.0            # drives animations
        self.target = None                       # ghosts: target tile
        self.look = "normal"                     # ghosts: how to draw
        self.on_rails = True                     # moved by the maze mover?
        self.random_turns = False                # frightened ghosts wander
        self.dying = 0.0                         # Pac-Man death animation 0..1

    @property
    def components(self):
        return (self.input, self.physics, self.graphics)

    # The Command pattern's actor interface (p01): MoveCommand calls this.
    def steer(self, direction: Direction) -> None:
        self.desired_direction = direction

    def reverse(self) -> None:
        self.direction = self.direction.opposite

    @property
    def tile(self):
        return tile_of(self.x, self.y)

    def send(self, message: str, **data) -> None:
        for component in self.components:
            component.receive(self, message, data)

    # Entity (Update Method, p09): delegate to the components.
    def update(self, dt: float) -> None:
        self.input.update(self, dt)
        self.physics.update(self, dt)

    def render(self, surface, alpha: float) -> None:
        self.graphics.render(self, surface, alpha)


# ---------------------------------------------------------------------------
# Physics: moving along the maze grid
# ---------------------------------------------------------------------------
class MazeMover(PhysicsComponent):
    """Moves an object from tile centre to tile centre.

    Turning decisions are only taken exactly at a tile centre, which keeps
    actors perfectly on the corridors. Subclasses provide ``decide``.
    """

    def __init__(self, maze):
        self.maze = maze

    def decide(self, obj, col: int, row: int) -> Direction:
        raise NotImplementedError

    def update(self, obj, dt: float) -> None:
        if obj.on_rails:
            self.advance(obj, obj.speed * dt)

    def advance(self, obj, distance: float) -> None:
        for _ in range(8):                      # a few sub-steps at most
            if distance <= EPS:
                break
            col, row = tile_of(obj.x, obj.y)
            cx, cy = tile_centre(col, row)
            d = obj.direction
            # Signed distance to this tile's centre along the direction of travel.
            ahead = (cx - obj.x) * d.dx + (cy - obj.y) * d.dy
            if d == Direction.NONE or abs(ahead) <= EPS:
                obj.x, obj.y = cx, cy           # exactly on the centre: decide
                d = self.decide(obj, col, row)
                obj.direction = d
                if d == Direction.NONE:
                    break
                obj.facing = d
                step = min(distance, TILE)
            elif ahead > 0:
                step = min(distance, ahead)     # run up to the centre
            else:
                step = min(distance, TILE + ahead)  # past the centre: on to the next one
            obj.x += d.dx * step
            obj.y += d.dy * step
            obj.distance_travelled += step
            distance -= step
            obj.x %= MAZE_W                     # the tunnel wraps around


class PacmanMover(MazeMover):
    def update(self, obj, dt: float) -> None:
        obj.speed = obj.world.pacman_speed()
        # Pac-Man may reverse at any moment, not just at tile centres.
        if obj.desired_direction != Direction.NONE and obj.desired_direction == obj.direction.opposite:
            obj.direction = obj.desired_direction
            obj.facing = obj.direction
        super().update(obj, dt)

    def decide(self, obj, col, row) -> Direction:
        wanted = obj.desired_direction
        if wanted != Direction.NONE and self.maze.pacman_can_enter(col + wanted.dx, row + wanted.dy):
            return wanted
        d = obj.direction
        if d != Direction.NONE and self.maze.pacman_can_enter(col + d.dx, row + d.dy):
            return d
        return Direction.NONE                   # stop against the wall


class GhostMover(MazeMover):
    def __init__(self, maze, rng: random.Random):
        super().__init__(maze)
        self.rng = rng

    def decide(self, obj, col, row) -> Direction:
        # Ghosts never reverse by choice; they pick the open exit that brings
        # them closest to their target tile (ties: up, left, down, right).
        options = [d for d in MOVES
                   if d != obj.direction.opposite
                   and self.maze.ghost_can_enter(col + d.dx, row + d.dy)]
        if not options:
            return obj.direction.opposite       # dead end
        if obj.random_turns or obj.target is None:
            return self.rng.choice(options)
        tx, ty = obj.target
        return min(options, key=lambda d: (col + d.dx - tx) ** 2 + (row + d.dy - ty) ** 2)


# ---------------------------------------------------------------------------
# Input: three interchangeable "brains"
# ---------------------------------------------------------------------------
class PlayerInputComponent(InputComponent):
    """Keyboard -> InputHandler (p01) -> MoveCommand -> obj.steer()."""

    def __init__(self, handler, core_input):
        self.handler = handler
        self.core_input = core_input

    def update(self, obj, dt: float) -> None:
        command = self.handler.handle_actor_input(self.core_input)
        if command is not None:
            command.execute(obj)


class DemoInputComponent(InputComponent):
    """Robo-Pac-Man for attract mode: heads for the nearest dot, avoiding ghosts.

    It emits exactly the same MoveCommands as the keyboard does.
    """
    DANGER_RADIUS = 2

    def __init__(self):
        self._last_tile = None
        self.commands = {d: MoveCommand(d) for d in MOVES}

    def update(self, obj, dt: float) -> None:
        tile = obj.tile
        if tile == self._last_tile and obj.direction != Direction.NONE:
            return                              # think once per tile
        self._last_tile = tile
        direction = self._plan(obj, tile)
        if direction != Direction.NONE:
            self.commands[direction].execute(obj)

    def receive(self, obj, message, data) -> None:
        if message == "reset":
            self._last_tile = None

    def _plan(self, obj, start) -> Direction:
        world, maze = obj.world, obj.world.maze
        danger = set()
        for ghost in world.ghosts:
            if ghost.brain.state.dangerous:
                gx, gy = ghost.tile
                for dx in range(-self.DANGER_RADIUS, self.DANGER_RADIUS + 1):
                    for dy in range(-self.DANGER_RADIUS, self.DANGER_RADIUS + 1):
                        danger.add(((gx + dx) % maze.cols, gy + dy))
        edible = {g.tile for g in world.ghosts if g.brain.state.edible}
        # Breadth-first search for the closest dot (or blue ghost), not through danger.
        first_step = {start: Direction.NONE}
        queue = deque([start])
        while queue:
            col, row = queue.popleft()
            if (col, row) != start and (maze.tile(col, row).is_dot or (col, row) in edible):
                return first_step[(col, row)]
            for d in MOVES:
                nxt = ((col + d.dx) % maze.cols, row + d.dy)
                if nxt in first_step or nxt in danger or not maze.pacman_can_enter(*nxt):
                    continue
                first_step[nxt] = d if (col, row) == start else first_step[(col, row)]
                queue.append(nxt)
        # Boxed in: just run away from the nearest dangerous ghost.
        options = [d for d in MOVES if maze.pacman_can_enter(start[0] + d.dx, start[1] + d.dy)]
        threats = [g.tile for g in world.ghosts if g.brain.state.dangerous]
        if not options or not threats:
            return Direction.NONE

        def safety(d):
            nx, ny = start[0] + d.dx, start[1] + d.dy
            return min((nx - tx) ** 2 + (ny - ty) ** 2 for tx, ty in threats)
        return max(options, key=safety)


class GhostBrain(InputComponent, Observer):
    """A ghost's mind: state machine + breed + bytecode personality.

    It is also the VM's "magical API" (p10): the bytecode can only see the
    world through the query methods at the bottom of this class.
    """

    def __init__(self, breed, vm):
        self.breed = breed          # Type Object (p12)
        self.vm = vm                # Bytecode VM (p10), shared by all ghosts
        self.machine = None
        self.owner = None
        self._result = None

    def attach(self, obj) -> None:
        self.owner = obj
        self.machine = StateMachine(obj)   # State (p06); started by reset()

    def update(self, obj, dt: float) -> None:
        if obj.world.ghosts_frozen():
            obj.speed = 0.0
            return
        self.machine.update(dt)

    def receive(self, obj, message, data) -> None:
        if message == "reset":
            self.reset(obj)

    def reset(self, obj) -> None:
        """Put the ghost back at its start (new life or new level)."""
        if self.breed.starts_outside:
            obj.place(GHOST_DOOR[0] * TILE, GHOST_DOOR[1] * TILE)
            obj.direction = obj.facing = Direction.LEFT
            self.machine.change(roaming_state_for(obj.world.ghost_mode))
        else:
            obj.place(self.breed.house_x * TILE, HOUSE_CENTRE_Y * TILE)
            obj.direction = obj.facing = Direction.UP
            self.machine.change(InHouse())
        obj.target = None
        obj.speed = FULL_SPEED * self.breed.speed

    # Observer (p03): a power pellet is "input" to the state machine.
    def on_notify(self, entity, event, data) -> None:
        self.machine.handle(event, data)

    # Called by the Chase state: run the breed's bytecode.
    def chase_target(self):
        self._result = None
        self.vm.interpret(self.breed.chase_code, self)
        return self._result or self.owner.tile

    # -- the VM's API ------------------------------------------------------------
    def pacman_tile(self):
        return self.owner.world.pacman.tile

    def pacman_heading(self):
        d = self.owner.world.pacman.facing
        return d.dx, d.dy

    def self_tile(self):
        return self.owner.tile

    def blinky_tile(self):
        blinky = self.owner.world.ghost_named("blinky")
        return blinky.tile if blinky else self.owner.tile

    def corner(self):
        return self.breed.scatter_corner

    def set_target(self, x, y) -> None:
        self._result = (x, y)


# ---------------------------------------------------------------------------
# Graphics
# ---------------------------------------------------------------------------
class PacmanGraphics(GraphicsComponent):
    def render(self, obj, surface, alpha: float) -> None:
        x, y = obj.lerp_position(alpha)
        if obj.dying > 0:
            mouth = 180 * obj.dying
        else:
            mouth = 5 + 40 * abs(math.sin(obj.distance_travelled / (TILE * 0.5)))
        drawing.pacman(surface, x, y, obj.facing, mouth)
        if x < TILE:                          # half in the tunnel: draw the other half too
            drawing.pacman(surface, x + MAZE_W, y, obj.facing, mouth)
        elif x > MAZE_W - TILE:
            drawing.pacman(surface, x - MAZE_W, y, obj.facing, mouth)


class GhostGraphics(GraphicsComponent):
    def render(self, obj, surface, alpha: float) -> None:
        x, y = obj.lerp_position(alpha)
        wobble = int(obj.distance_travelled / 6) % 2
        heading = obj.direction if obj.direction != Direction.NONE else obj.facing
        drawing.ghost(surface, x, y, obj.breed.colour, heading, obj.look, wobble)


# ---------------------------------------------------------------------------
# Assembly: no Pacman or Ghost classes, just different components.
# ---------------------------------------------------------------------------
def make_pacman(maze, input_component: InputComponent) -> GameObject:
    return GameObject("pacman", input_component, PacmanMover(maze), PacmanGraphics())


def make_ghost(breed, maze, vm, rng: random.Random) -> GameObject:
    brain = GhostBrain(breed, vm)
    ghost = GameObject(breed.key, brain, GhostMover(maze, rng), GhostGraphics())
    brain.attach(ghost)
    # Direct references for the State pattern's ghost interface (p06).
    ghost.breed = breed
    ghost.brain = brain.machine
    ghost.chase_target = brain.chase_target
    return ghost
