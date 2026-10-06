"""PatternManGame: the rules of Pac-Man, assembled from the 19 pattern modules.

Every pattern appears here at least once. Search for "(pNN" to find where.
The flow of one fixed update (p08 Game Loop):

    process_input()                  Command (p01): keys -> commands
    fixed_update()
        flow.update(dt)              State (p06): the current game-flow state
            step_world(dt)           (only in Attract / Playing)
                world.update(dt)     Update Method (p09) -> Component (p13)
                _eat_dots()          Flyweight (p02) + Observer (p03) + Prototype (p04)
                _collide()           Spatial Partition (p19)
                particles / popups   Data Locality (p16) / Object Pool (p18)
        audio.update()               Event Queue (p14) via Service Locator (p15)
    render(surface, alpha)           Double Buffer (p07) + Dirty Flag (p17)
"""
import os
import random

import pygame

from support.constants import (TILE, MAZE_W, MAZE_H, HUD_TOP, SCREEN_W, SCREEN_H,
                               BLACK, WHITE, PACMAN_YELLOW, FULL_SPEED, PACMAN_SPEED,
                               PACMAN_FRIGHT_SPEED, DT, Direction, tile_centre)
from support.maze_layout import PACMAN_START, FRUIT_SPOT
from support.text import Text
from support import drawing

from patterns.p01_command import InputHandler
from patterns.p02_flyweight import Maze
from patterns.p03_observer import Subject, Observer, Event, Scoreboard, Achievements
from patterns.p04_prototype import Spawner
from patterns.p05_singleton import Settings
from patterns.p06_state import PushdownAutomaton, Eaten
from patterns.p08_game_loop import FixedTimestepGame
from patterns.p09_update_method import World
from patterns.p10_bytecode import VM
from patterns.p11_subclass_sandbox import fruit_prototype_for
from patterns.p12_type_object import BreedRegistry
from patterns.p13_component import (make_pacman, make_ghost, PlayerInputComponent,
                                    DemoInputComponent)
from patterns.p14_event_queue import AudioEngine
from patterns.p15_service_locator import Locator, LoggedAudio, AudioObserver
from patterns.p16_data_locality import ParticleSystem
from patterns.p17_dirty_flag import MazeRenderer, CachedText
from patterns.p18_object_pool import PopupPool
from patterns.p19_spatial_partition import Grid, Unit

from app.game_states import AttractState
from app.panel import Panel

HERE = os.path.dirname(os.path.abspath(__file__))
BREEDS_FILE = os.path.join(HERE, "..", "data", "breeds.json")

# The arcade's level-1 scatter/chase schedule (seconds); the last chase is endless.
MODE_SCHEDULE = [("scatter", 7), ("chase", 20), ("scatter", 7), ("chase", 20),
                 ("scatter", 5), ("chase", 20), ("scatter", 5), ("chase", None)]
FRUIT_AT_DOTS_EATEN = (70, 170)
COLLISION_RADIUS = TILE * 0.6


class PlayWorld(World):
    """The Update Method's World (p09), plus what the ghost states need (p06)."""

    def __init__(self, maze):
        super().__init__()
        self.maze = maze
        self.pacman = None
        self.ghosts = []
        self.level = 1
        self.fright_seconds = 6.0
        self.speed_scale = 1.0
        self.freeze_timer = 0.0
        self.boost_timer = 0.0
        self.reset_mode_timer()

    def reset_mode_timer(self) -> None:
        self._mode_index = 0
        self.ghost_mode, self._mode_time = MODE_SCHEDULE[0]

    def ghost_named(self, name: str):
        for ghost in self.ghosts:
            if ghost.name == name:
                return ghost
        return None

    def ghosts_frozen(self) -> bool:
        return self.freeze_timer > 0

    def any_ghost_frightened(self) -> bool:
        return any(g.brain.state.edible for g in self.ghosts)

    def pacman_speed(self) -> float:
        factor = PACMAN_FRIGHT_SPEED if self.any_ghost_frightened() else PACMAN_SPEED
        if self.boost_timer > 0:
            factor *= 1.3
        return FULL_SPEED * factor * self.speed_scale

    def update(self, dt: float) -> None:
        # The scatter/chase clock pauses while the ghosts are blue (as in the arcade).
        if self._mode_time is not None and not self.any_ghost_frightened():
            self._mode_time -= dt
            if self._mode_time <= 0:
                self._mode_index += 1
                self.ghost_mode, self._mode_time = MODE_SCHEDULE[self._mode_index]
        self.freeze_timer = max(0.0, self.freeze_timer - dt)
        self.boost_timer = max(0.0, self.boost_timer - dt)
        super().update(dt)

    def hold(self) -> None:
        """No simulation this step: stop interpolation from wobbling actors."""
        for entity in self.entities:
            entity.prev_x, entity.prev_y = entity.x, entity.y


class PatternManGame(FixedTimestepGame, Observer):
    """The game. Also an Observer (p03) of its own events, for popups."""

    def __init__(self, scale: int = 1, fullscreen: bool = False, seed: int = None):
        super().__init__()
        self.scale = scale
        self.fullscreen = fullscreen
        self.rng = random.Random(seed)
        self.settings = Settings.instance()            # Singleton (p05)

    # ------------------------------------------------------------------ set-up
    def init(self) -> bool:
        if not self.init_system("Pattern-Man: Game Programming Patterns in Pac-Man",
                                SCREEN_W * self.scale, SCREEN_H * self.scale, self.fullscreen):
            return False
        self.init_frame_buffer(SCREEN_W, SCREEN_H)      # Double Buffer (p07)
        self.text = Text(20)
        self.big_text = Text(34)
        self.small_text = Text(17)

        # Service Locator (p15) + Event Queue (p14): provide the real audio if
        # the mixer started. If not, the locator's NullAudio is used.
        self.audio_engine = None
        if pygame.mixer.get_init():
            try:
                self.audio_engine = AudioEngine()
            except pygame.error:
                self.audio_engine = None
        self.audio_service = self.audio_engine
        if self.audio_service is not None and self.settings.log_audio:
            self.audio_service = LoggedAudio(self.audio_service)
        Locator.provide(self.audio_service)
        self.muted = False

        # Command (p01)
        self.input_handler = InputHandler()
        self.last_command = "-"

        # Flyweight (p02) + Dirty Flag (p17)
        self.maze = Maze()
        self.maze_renderer = MazeRenderer(self.maze)
        self.maze_flash = False

        # Observer (p03)
        self.subject = Subject()
        self.scoreboard = Scoreboard(self.subject)
        self.achievements = Achievements(self.subject)
        self.audio_observer = AudioObserver()
        self.subject.add_observer(self)               # popups for achievements / 1UP

        # Type Object (p12) + Bytecode (p10)
        self.breeds = BreedRegistry.from_file(BREEDS_FILE)
        self.vm = VM()

        # Update Method (p09) + Component (p13)
        self.world = PlayWorld(self.maze)
        self.player_input = PlayerInputComponent(self.input_handler, self.get_input())
        self.demo_input = DemoInputComponent()
        self.pacman = self.world.add(make_pacman(self.maze, self.demo_input))
        self.world.pacman = self.pacman
        self.ghosts = [self.world.add(make_ghost(b, self.maze, self.vm, self.rng))
                       for b in self.breeds.playable()]
        self.world.ghosts = self.ghosts
        for ghost in self.ghosts:
            self.subject.add_observer(ghost.input)     # the GhostBrain hears power pellets

        # Prototype (p04) + Subclass Sandbox (p11)
        self.fruit_spawner = None
        self.fruit = None
        self.fruits_spawned = 0
        self.last_bonus = "-"

        # Data Locality (p16), Object Pool (p18), Spatial Partition (p19)
        self.particles = ParticleSystem(rng=self.rng)
        self.popups = PopupPool()
        self.grid = Grid(MAZE_W, MAZE_H, TILE * 2)
        self.units = {}

        # Dirty-flagged HUD text (p17)
        self.score_text = CachedText(self.text.font.font, WHITE)
        self.high_text = CachedText(self.text.font.font, WHITE)
        self.panel = Panel(self)

        self.pacman_caught = False
        self.ghost_combo = 0
        self.hit_pause = 0.0
        self.time = 0.0

        # State (p06): the game flow is a pushdown automaton.
        self.flow = PushdownAutomaton(self)
        self.flow.push(AttractState())
        return True

    # ----------------------------------------------------------- level control
    def setup_demo(self) -> None:
        """Attract mode: Robo-Pac-Man, and the observers that shouldn't listen are removed."""
        for observer in (self.scoreboard, self.achievements, self.audio_observer):
            self.subject.remove_observer(observer)
        self.pacman.input = self.demo_input            # Component swap ("Robo-Bjørn")
        self.start_level(1)

    def new_game(self) -> None:
        for observer in (self.scoreboard, self.achievements, self.audio_observer):
            self.subject.add_observer(observer)
        self.pacman.input = self.player_input
        self.scoreboard.new_game()
        self.notify(None, Event.GAME_STARTED)
        self.start_level(self.settings.start_level)

    def start_level(self, level: int) -> None:
        world = self.world
        world.level = level
        world.fright_seconds = max(0.0, 7.0 - level)
        world.speed_scale = min(1.0 + 0.04 * (level - 1), 1.2)
        self.maze.reset()                               # sets the coarse dirty flag
        # Prototype (p04): one Spawner, holding this level's fruit prototype.
        self.fruit_spawner = Spawner(fruit_prototype_for(level))
        self.fruits_spawned = 0
        self.reset_actors()
        self.notify(None, Event.LEVEL_STARTED, {"level": level})

    def reset_actors(self) -> None:
        self.world.reset_mode_timer()
        self.world.freeze_timer = self.world.boost_timer = 0.0
        x, y = PACMAN_START
        self.pacman.place(x * TILE, y * TILE)
        self.pacman.direction = self.pacman.desired_direction = self.pacman.facing = Direction.LEFT
        self.pacman.dying = 0.0
        self.pacman.send("reset")                      # component messaging (p13)
        for ghost in self.ghosts:
            ghost.active = True
            ghost.send("reset")
        if self.fruit is not None:
            self.fruit.alive = False
            self.fruit = None
        self.particles.clear()
        self.popups.clear()
        self.pacman_caught = False
        self.ghost_combo = 0
        self.hit_pause = 0.0

    def notify(self, entity, event, data=None) -> None:
        self.subject.notify(entity, event, data)

    # --------------------------------------------------------------- the loop
    def process_input(self) -> None:
        """Once per frame (p08): game commands from key hits (p01)."""
        for command in self.input_handler.handle_game_input(self.get_input()):
            self.last_command = command.name
            command.execute(self)
        move = self.input_handler.handle_actor_input(self.get_input())
        if move is not None and self.pacman.input is self.player_input:
            self.last_command = move.name

    def fixed_update(self) -> None:
        self.time += DT
        self.flow.update(DT)
        Locator.get_audio().update()                   # Event Queue: one request per update

    def hold_world(self) -> None:
        self.world.hold()

    def step_world(self, dt: float) -> None:
        if self.hit_pause > 0:                          # brief freeze after eating a ghost
            self.hit_pause -= dt
            self.world.hold()
        else:
            self.world.update(dt)                       # Update Method -> Components
            self._eat_dots()
            self._collide()
        self.particles.update(dt)
        self.popups.update(dt)

    # -------------------------------------------------------------- the rules
    def _eat_dots(self) -> None:
        col, row = self.pacman.tile
        tile = self.maze.eat(col, row)                  # Flyweight: which Tile was it?
        if tile is None:
            return
        cx, cy = tile_centre(col, row)
        if tile.is_power:
            self.ghost_combo = 0
            self.particles.emit(cx, cy, 14, (255, 184, 151))
            self.notify(self.pacman, Event.POWER_PELLET_EATEN, {"points": tile.points})
        else:
            self.notify(self.pacman, Event.DOT_EATEN, {"points": tile.points})
        eaten = self.maze.total_dots - self.maze.dots_left
        if eaten in FRUIT_AT_DOTS_EATEN and self.fruits_spawned < len(FRUIT_AT_DOTS_EATEN):
            self._spawn_fruit()

    def _spawn_fruit(self) -> None:
        fruit = self.fruit_spawner.spawn().init(self)   # Prototype clone + two-stage init
        fruit.place(FRUIT_SPOT[0] * TILE, FRUIT_SPOT[1] * TILE)
        if self.fruit is not None:
            self.fruit.alive = False
        self.fruit = self.world.add(fruit)
        self.fruits_spawned += 1

    def _collide(self) -> None:
        """Spatial Partition (p19): file everyone in the grid, then find touching pairs."""
        live = [self.pacman] + [g for g in self.ghosts if g.active]
        if self.fruit is not None:
            if self.fruit.alive:
                live.append(self.fruit)
            else:
                self.fruit = None
        for entity in list(self.units):
            if entity not in live:
                self.grid.remove(self.units.pop(entity))
        for entity in live:
            unit = self.units.get(entity)
            if unit is None:
                unit = self.units[entity] = Unit(entity, entity.x, entity.y)
                self.grid.add(unit)
            else:
                self.grid.move(unit, entity.x, entity.y)
        self.grid.handle_collisions(COLLISION_RADIUS, self._on_touch)

    def _on_touch(self, a, b) -> None:
        if b is self.pacman:
            a, b = b, a
        if a is not self.pacman:
            return                                      # ghost meets ghost: nothing
        if b is self.fruit:
            self.last_bonus = type(b).__name__
            b.activate()                                # Subclass Sandbox (p11)
            b.alive = False
            return
        state = getattr(b, "brain", None) and b.brain.state
        if state is None:
            return
        if state.edible:
            points = 200 * (2 ** min(self.ghost_combo, 3))
            self.ghost_combo += 1
            b.brain.change(Eaten())
            self.popups.create(b.x, b.y, str(points), (0, 255, 255))
            self.particles.emit(b.x, b.y, 24, b.breed.colour, speed=120)
            self.hit_pause = 0.5
            self.notify(b, Event.GHOST_EATEN, {"points": points})
        elif state.dangerous and not self.settings.invincible:
            if not self.pacman_caught:
                self.particles.emit(self.pacman.x, self.pacman.y, 30, PACMAN_YELLOW, speed=110)
            self.pacman_caught = True

    # The Subclass Sandbox's context (p11): the operations fruits may use.
    def bonus_score(self, fruit, points: int) -> None:
        self.notify(fruit, Event.FRUIT_EATEN, {"points": points})

    def play_sound(self, name: str) -> None:
        Locator.get_audio().play_sound(name)

    def spawn_particles(self, x, y, count, colour) -> None:
        self.particles.emit(x, y, count, colour)

    def show_popup(self, x, y, text, colour) -> None:
        self.popups.create(x, y, text, colour, seconds=1.5)

    def freeze_ghosts(self, seconds: float) -> None:
        self.world.freeze_timer = max(self.world.freeze_timer, seconds)

    def frighten_ghosts(self) -> None:
        self.ghost_combo = 0
        for ghost in self.ghosts:
            ghost.brain.handle(Event.POWER_PELLET_EATEN)

    def boost_pacman(self, seconds: float) -> None:
        self.world.boost_timer = max(self.world.boost_timer, seconds)

    def add_life(self) -> None:
        self.notify(None, Event.EXTRA_LIFE)

    # Observer (p03): banners for achievements and extra lives.
    def on_notify(self, entity, event, data) -> None:
        if event == Event.ACHIEVEMENT_UNLOCKED:
            self.popups.create(MAZE_W / 2, 20.5 * TILE, data["text"], (255, 220, 90),
                               seconds=3.0, rise=4.0)
        elif event == Event.EXTRA_LIFE:
            self.popups.create(MAZE_W / 2, 23.5 * TILE, "EXTRA LIFE!", PACMAN_YELLOW,
                               seconds=2.0, rise=4.0)

    # ---------------------------------------------------- commands' receivers
    def toggle_pause(self) -> None:
        self.flow.handle("pause")

    def start_pressed(self) -> None:
        self.flow.handle("start")

    def toggle_mute(self) -> None:
        """Service Locator (p15): swap in the null service, and back."""
        self.muted = not self.muted
        if self.muted:
            Locator.get_audio().stop_all()
        Locator.provide(None if self.muted else self.audio_service)

    def toggle_debug(self) -> None:
        self.settings.show_debug = not self.settings.show_debug

    def toggle_panel(self) -> None:
        self.settings.show_panel = not self.settings.show_panel

    # ---------------------------------------------------------------- render
    def render(self, surface, alpha: float) -> None:
        surface.fill(BLACK)
        self._render_hud(surface)
        maze_view = surface.subsurface(pygame.Rect(0, HUD_TOP, MAZE_W, MAZE_H))
        blink = int(self.time * 4) % 2 == 0 or self.flow.state.name != "playing"
        self.maze_renderer.render(maze_view, blink, self.maze_flash)   # Dirty Flag (p17)
        self.world.render(maze_view, alpha)                            # interpolated (p08)
        self.particles.render(maze_view)                               # Data Locality (p16)
        self.popups.render(maze_view, self.small_text)                 # Object Pool (p18)
        if self.settings.show_debug:
            self._render_debug(maze_view)
        for state in self.flow.stack:                                  # Paused over Playing
            state.overlay(self, maze_view)
        self.panel.render(surface)

    def _render_hud(self, surface) -> None:
        demo = self.flow.state.name == "attract"
        self.text.draw(surface, "1UP", 24, 2, WHITE)
        self.score_text.set("DEMO" if demo else self.scoreboard.score)   # Dirty Flag (p17)
        surface.blit(self.score_text.surface(), (24, 16))
        self.text.draw_centred(surface, "HIGH SCORE", MAZE_W / 2, 2, WHITE)
        self.high_text.set(self.scoreboard.high_score)
        hs = self.high_text.surface()
        surface.blit(hs, (MAZE_W / 2 - hs.get_width() / 2, 16))
        self.text.draw(surface, f"LEVEL {self.world.level}", MAZE_W - 90, 2, WHITE)
        bottom = HUD_TOP + MAZE_H + 16
        if not demo:
            for i in range(max(0, self.scoreboard.lives - 1)):
                drawing.pacman(surface, 24 + i * 26, bottom, Direction.LEFT, 35, radius=10)
        for i in range(min(self.world.level, 7)):
            proto = fruit_prototype_for(self.world.level - i)
            drawing.fruit(surface, MAZE_W - 24 - i * 26, bottom, proto.kind)

    def _render_debug(self, view) -> None:
        cell = self.grid.cell_size
        for c in range(self.grid.cols + 1):
            pygame.draw.line(view, (40, 40, 70), (c * cell, 0), (c * cell, MAZE_H))
        for r in range(self.grid.rows + 1):
            pygame.draw.line(view, (40, 40, 70), (0, r * cell), (MAZE_W, r * cell))
        for unit in self.units.values():
            col, row = unit.cell
            pygame.draw.rect(view, (90, 90, 140), (col * cell, row * cell, cell, cell), 1)
        for ghost in self.ghosts:
            if ghost.target is not None and ghost.active and ghost.brain.state.name in ("chase", "scatter", "eaten"):
                tx, ty = tile_centre(*ghost.target)
                colour = ghost.breed.colour
                pygame.draw.line(view, colour, (tx - 5, ty - 5), (tx + 5, ty + 5), 2)
                pygame.draw.line(view, colour, (tx - 5, ty + 5), (tx + 5, ty - 5), 2)
                pygame.draw.line(view, colour, (ghost.x, ghost.y), (tx, ty), 1)
