"""One small test class per pattern, in book order. Reading these is another way
to see what each pattern promises.  Run:  python -m unittest discover -s tests
"""
import ast
import glob
import os
import random
import re
import unittest

import tests  # noqa: F401  (sets up sys.path and the headless SDL drivers)
import pygame

from support.constants import Direction, TILE, tile_centre


class FakeInput:
    """Stands in for core.input.Input."""

    def __init__(self, down=(), hits=()):
        self.down, self.hits = set(down), set(hits)

    def key_down(self, key):
        return key in self.down

    def key_hit(self, key):
        return key in self.hits


class TestImportOrder(unittest.TestCase):
    """Each pattern module may only import *earlier* pattern modules."""

    def test_modules_only_import_earlier_patterns(self):
        files = sorted(glob.glob(os.path.join(tests.GAME_DIR, "patterns", "p[0-9][0-9]_*.py")))
        self.assertEqual(len(files), 19)
        for path in files:
            number = int(os.path.basename(path)[1:3])
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    m = re.match(r"patterns\.p(\d\d)_", node.module)
                    if m:
                        self.assertLess(int(m.group(1)), number,
                                        f"{os.path.basename(path)} imports {node.module}")
                    self.assertFalse(node.module.startswith("app"),
                                     f"{os.path.basename(path)} imports the app layer")


class TestP01Command(unittest.TestCase):
    def test_keys_map_to_shared_move_commands(self):
        from patterns.p01_command import InputHandler, MOVE_UP

        class Actor:
            steered = None

            def steer(self, d):
                self.steered = d
        handler = InputHandler()
        command = handler.handle_actor_input(FakeInput(down={pygame.K_w}))
        self.assertIs(command, MOVE_UP)
        actor = Actor()
        command.execute(actor)
        self.assertEqual(actor.steered, Direction.UP)

    def test_rebinding(self):
        from patterns.p01_command import InputHandler, MOVE_LEFT
        handler = InputHandler()
        handler.bind_move(pygame.K_j, MOVE_LEFT)
        self.assertIs(handler.handle_actor_input(FakeInput(down={pygame.K_j})), MOVE_LEFT)

    def test_undo_redo(self):
        from patterns.p01_command import Command, CommandHistory

        class Add(Command):
            def __init__(self, n):
                self.n = n

            def execute(self, box):
                box.append(self.n)

            def undo(self, box):
                box.pop()
        box, history = [], CommandHistory()
        history.execute(Add(1), box)
        history.execute(Add(2), box)
        history.undo(box)
        self.assertEqual(box, [1])
        history.redo(box)
        self.assertEqual(box, [1, 2])


class TestP02Flyweight(unittest.TestCase):
    def test_cells_share_six_tiles(self):
        from patterns.p02_flyweight import Maze, FLOOR
        maze = Maze()
        self.assertEqual(len(maze.tiles), 28 * 31)
        self.assertLessEqual(maze.distinct_tile_objects(), 6)
        self.assertEqual(maze.total_dots, 244)       # 240 dots + 4 power pellets, like the arcade
        self.assertTrue(maze.tile(1, 1).is_dot)
        eaten = maze.eat(1, 1)
        self.assertEqual(eaten.points, 10)
        self.assertIs(maze.tile(1, 1), FLOOR)        # the cell now points at another flyweight
        self.assertTrue(maze.tile(2, 1).is_dot)      # ...the shared DOT tile is untouched
        self.assertIn((1, 1), maze.changed)

    def test_tunnel_wraps(self):
        from patterns.p02_flyweight import Maze
        maze = Maze()
        self.assertIs(maze.tile(-1, 14), maze.tile(27, 14))
        self.assertTrue(maze.pacman_can_enter(-1, 14))


class TestP03Observer(unittest.TestCase):
    def test_notify_and_remove(self):
        from patterns.p03_observer import Subject, Observer, Event
        heard = []

        class Ear(Observer):
            def on_notify(self, entity, event, data):
                heard.append(event)
        subject, ear = Subject(), Ear()
        subject.add_observer(ear)
        subject.notify(None, Event.DOT_EATEN)
        subject.remove_observer(ear)
        subject.notify(None, Event.DOT_EATEN)
        self.assertEqual(heard, [Event.DOT_EATEN])

    def test_scoreboard_and_achievements(self):
        from patterns.p03_observer import Subject, Event, Scoreboard, Achievements
        subject = Subject()
        board, ach = Scoreboard(subject), Achievements(subject)
        subject.add_observer(board)
        subject.add_observer(ach)
        subject.notify(None, Event.POWER_PELLET_EATEN, {"points": 50})
        for points in (200, 400, 800, 1600):
            subject.notify(None, Event.GHOST_EATEN, {"points": points})
        self.assertEqual(board.score, 3050)
        self.assertIn("ghost_buster", ach.unlocked)
        subject.notify(None, Event.FRUIT_EATEN, {"points": 7000})
        self.assertEqual(board.lives, 4)             # extra life at 10,000


class TestP04Prototype(unittest.TestCase):
    def test_spawner_clones(self):
        from patterns.p04_prototype import Spawner
        from patterns.p11_subclass_sandbox import Orange
        proto = Orange()
        proto.lifetime = 3.0
        spawner = Spawner(proto)
        a, b = spawner.spawn(), spawner.spawn()
        self.assertIsNot(a, b)
        self.assertIsInstance(a, Orange)
        self.assertEqual(a.lifetime, 3.0)            # the prototype's state is copied
        a.x = 99
        self.assertNotEqual(b.x, 99)


class TestP05Singleton(unittest.TestCase):
    def test_one_instance(self):
        from patterns.p05_singleton import Settings
        self.assertIs(Settings(), Settings.instance())


class TestP06State(unittest.TestCase):
    def test_enter_exit_and_pushdown(self):
        from patterns.p06_state import State, StateMachine, PushdownAutomaton
        log = []

        class S(State):
            def __init__(self, name):
                self.name = name

            def enter(self, owner):
                log.append("enter " + self.name)

            def exit(self, owner):
                log.append("exit " + self.name)

            def resume(self, owner):
                log.append("resume " + self.name)
        machine = StateMachine(None, S("a"))
        machine.change(S("b"))
        self.assertEqual(log, ["enter a", "exit a", "enter b"])
        log.clear()
        stack = PushdownAutomaton(None)
        stack.push(S("playing"))
        stack.push(S("paused"))
        stack.pop()
        self.assertEqual(log, ["enter playing", "enter paused", "exit paused", "resume playing"])
        self.assertEqual(stack.state.name, "playing")


class TestP07DoubleBuffer(unittest.TestCase):
    def test_swap(self):
        from patterns.p07_double_buffer import FrameBuffer, DoubleBufferedValue
        fb = FrameBuffer(4, 4)
        front, back = fb.current, fb.next
        fb.swap()
        self.assertIs(fb.current, back)
        self.assertIs(fb.next, front)
        v = DoubleBufferedValue(1)
        v.set(2)
        self.assertEqual(v.get(), 1)
        v.swap()
        self.assertEqual(v.get(), 2)


class TestP08GameLoop(unittest.TestCase):
    def test_fixed_steps_and_clamp(self):
        from patterns.p08_game_loop import FixedTimestepGame

        class Counting(FixedTimestepGame):
            updates = 0
            alphas = []

            def fixed_update(self):
                self.updates += 1

            def render(self, surface, alpha):
                self.alphas.append(alpha)
        pygame.display.init()
        game = Counting()
        game.graphics.init(8, 8, False)
        game.init_frame_buffer(8, 8)
        game.tick(25)                       # 1.5 updates' worth of time
        self.assertEqual(game.updates, 1)
        self.assertAlmostEqual(game.alphas[-1], 0.5, places=2)
        game.tick(5000)                     # a huge hitch is clamped (spiral of death)
        self.assertEqual(game.updates, 1 + 15)


class TestP09UpdateMethod(unittest.TestCase):
    def test_add_and_remove_during_update(self):
        from patterns.p09_update_method import Entity, World
        world = World()
        born = []

        class Parent(Entity):
            def update(self, dt):
                if not born:
                    born.append(self.world.add(Entity()))
                self.alive = False
        world.add(Parent())
        world.update(1 / 60)
        self.assertEqual(world.entities, born)       # parent swept, child joined after the loop


class TestP10Bytecode(unittest.TestCase):
    class Api:
        def __init__(self, pac=(10, 10), heading=(1, 0), me=(0, 0), blinky=(5, 5), corner=(0, 32)):
            self.pac, self.heading, self.me, self.blinky, self.c = pac, heading, me, blinky, corner
            self.target = None

        def pacman_tile(self):
            return self.pac

        def pacman_heading(self):
            return self.heading

        def self_tile(self):
            return self.me

        def blinky_tile(self):
            return self.blinky

        def corner(self):
            return self.c

        def set_target(self, x, y):
            self.target = (x, y)

    def setUp(self):
        from patterns.p12_type_object import BreedRegistry
        from app.game import BREEDS_FILE
        self.breeds = BreedRegistry.from_file(BREEDS_FILE)

    def run_breed(self, key, **kw):
        from patterns.p10_bytecode import VM
        api = self.Api(**kw)
        VM().interpret(self.breeds[key].chase_code, api)
        return api.target

    def test_personalities(self):
        self.assertEqual(self.run_breed("blinky"), (10, 10))
        self.assertEqual(self.run_breed("pinky", heading=(0, -1)), (10, 6))
        # Inky: 2 * (pac + 2*heading) - blinky = 2*(12,10) - (5,5)
        self.assertEqual(self.run_breed("inky"), (19, 15))
        self.assertEqual(self.run_breed("clyde", me=(0, 0)), (10, 10))     # far: chase
        self.assertEqual(self.run_breed("clyde", me=(9, 9)), (0, 32))      # near: go home

    def test_assembler_errors_and_safety(self):
        from patterns.p10_bytecode import assemble, disassemble, VM, BytecodeError
        with self.assertRaises(BytecodeError):
            assemble("JUMP nowhere")
        with self.assertRaises(BytecodeError):
            assemble("LIT 300")
        loop = assemble("top: JUMP top")
        self.assertEqual(disassemble(loop), ["  0  JUMP 0"])
        with self.assertRaises(BytecodeError):
            VM().interpret(loop, self.Api())


class TestP11SubclassSandbox(unittest.TestCase):
    def test_fruit_uses_only_provided_operations(self):
        from patterns.p11_subclass_sandbox import Key, Strawberry
        calls = []

        class Context:
            def __getattr__(self, name):
                return lambda *a: calls.append(name)
        Key().init(Context()).activate()
        self.assertIn("add_life", calls)
        self.assertIn("bonus_score", calls)
        calls.clear()
        Strawberry().init(Context()).activate()
        self.assertIn("freeze_ghosts", calls)


class TestP12TypeObject(unittest.TestCase):
    def test_copy_down_inheritance(self):
        from patterns.p12_type_object import BreedRegistry
        reg = BreedRegistry({"base": {"abstract": True, "display_name": "G", "nickname": "",
                                      "colour": [1, 2, 3], "speed": 0.5, "tunnel_speed": 0.4,
                                      "frightened_speed": 0.5, "eaten_speed": 2,
                                      "elroy_dots": 0, "elroy_speed": 1, "release_delay": 0,
                                      "starts_outside": False, "house_x": 14,
                                      "scatter_corner": [0, 0], "chase_program": "HALT"},
                             "fast": {"parent": "base", "speed": 0.9}})
        self.assertEqual(reg["fast"].speed, 0.9)
        self.assertEqual(reg["fast"].colour, (1, 2, 3))
        self.assertEqual([b.key for b in reg.playable()], ["fast"])

    def test_cycle_detected(self):
        from patterns.p12_type_object import BreedRegistry
        with self.assertRaises(ValueError):
            BreedRegistry({"a": {"parent": "b"}, "b": {"parent": "a"}})


class TestP13Component(unittest.TestCase):
    def make_world(self):
        from patterns.p02_flyweight import Maze
        from patterns.p09_update_method import World
        world = World()
        world.maze = Maze()
        world.pacman_speed = lambda: 120.0
        return world

    def test_pacman_runs_and_stops_at_wall(self):
        from patterns.p13_component import make_pacman, InputComponent
        world = self.make_world()
        pac = world.add(make_pacman(world.maze, InputComponent()))
        pac.place(*tile_centre(6, 1))
        pac.direction = Direction.LEFT
        for _ in range(120):
            world.update(1 / 60)
        self.assertEqual(pac.tile, (1, 1))           # stopped at the left wall
        self.assertEqual(pac.direction, Direction.NONE)
        pac.steer(Direction.DOWN)
        for _ in range(30):
            world.update(1 / 60)
        self.assertEqual(pac.tile[0], 1)
        self.assertGreater(pac.tile[1], 1)

    def test_ghost_mover_heads_for_target(self):
        from patterns.p02_flyweight import Maze
        from patterns.p13_component import GhostMover, GameObject
        mover = GhostMover(Maze(), random.Random(0))
        ghost = GameObject("g", None, mover, None)
        ghost.direction = Direction.LEFT
        ghost.target = (9, 8)                          # straight below the junction (9, 5)
        self.assertEqual(mover.decide(ghost, 9, 5), Direction.DOWN)
        ghost.target = (0, 5)                          # far left
        self.assertEqual(mover.decide(ghost, 9, 5), Direction.LEFT)
        ghost.direction = Direction.RIGHT              # ...but ghosts never reverse by choice
        self.assertNotEqual(mover.decide(ghost, 9, 5), Direction.LEFT)


class TestP14EventQueue(unittest.TestCase):
    def test_ring_buffer_wraps(self):
        from patterns.p14_event_queue import RingBuffer
        ring = RingBuffer(3)
        for i in range(3):
            self.assertTrue(ring.push(i))
        self.assertFalse(ring.push(99))
        self.assertEqual(ring.pop(), 0)
        ring.push(3)                                  # tail wraps to index 0
        self.assertEqual([ring.pop() for _ in range(3)], [1, 2, 3])
        self.assertIsNone(ring.pop())

    def test_aggregation(self):
        from patterns.p14_event_queue import AudioEngine, RingBuffer
        engine = AudioEngine.__new__(AudioEngine)     # skip sound synthesis
        engine.queue, engine.sounds = RingBuffer(4), {}
        engine.requested = engine.merged = engine.dropped = engine.played = 0
        engine.play_sound("chomp", 0.3)
        engine.play_sound("chomp", 0.8)
        engine.play_sound("death")
        self.assertEqual(len(engine.queue), 2)
        self.assertEqual(engine.merged, 1)
        self.assertEqual(next(engine.queue.pending()).volume, 0.8)


class TestP15ServiceLocator(unittest.TestCase):
    def test_null_and_logged(self):
        from patterns.p15_service_locator import Locator, NullAudio, LoggedAudio, Audio
        from patterns.p14_event_queue import AudioEngine
        self.assertTrue(issubclass(AudioEngine, Audio))
        Locator.provide(None)
        self.assertIsInstance(Locator.get_audio(), NullAudio)
        lines = []
        Locator.provide(LoggedAudio(NullAudio(), lines.append))
        Locator.get_audio().play_sound("chomp")
        self.assertEqual(len(lines), 1)
        Locator.provide(None)


class TestP16DataLocality(unittest.TestCase):
    def test_live_particles_stay_packed(self):
        from patterns.p16_data_locality import ParticleSystem
        ps = ParticleSystem(capacity=8, rng=random.Random(1))
        ps.emit(0, 0, 20, (1, 1, 1))
        self.assertEqual(ps.num_active, 8)            # capacity is a hard limit
        ps.life[2] = 0.001
        ps.update(0.01)
        self.assertEqual(ps.num_active, 7)
        self.assertTrue(all(ps.life[i] > 0 for i in range(ps.num_active)))


class TestP17DirtyFlag(unittest.TestCase):
    def test_only_dirty_tiles_are_redrawn(self):
        from patterns.p02_flyweight import Maze
        from patterns.p17_dirty_flag import MazeRenderer
        maze = Maze()
        renderer = MazeRenderer(maze)
        surface = pygame.Surface((448, 496))
        renderer.render(surface, True)
        self.assertEqual(renderer.full_rebuilds, 1)
        renderer.render(surface, True)
        self.assertEqual(renderer.tiles_redrawn_last, 0)
        maze.eat(1, 1)
        renderer.render(surface, True)
        self.assertEqual(renderer.tiles_redrawn_last, 1)


class TestP18ObjectPool(unittest.TestCase):
    def test_reuse_and_exhaustion(self):
        from patterns.p18_object_pool import PopupPool
        pool = PopupPool(2)
        self.assertTrue(pool.create(0, 0, "a"))
        self.assertTrue(pool.create(0, 0, "b"))
        self.assertFalse(pool.create(0, 0, "c"))
        self.assertEqual(pool.refused, 1)
        pool.update(5.0)                              # both expire, back on the free list
        self.assertEqual(pool.in_use_count, 0)
        self.assertTrue(pool.create(0, 0, "d"))
        self.assertEqual([p.text for p in pool.popups if p.in_use], ["d"])


class TestP19SpatialPartition(unittest.TestCase):
    def test_same_pairs_as_brute_force(self):
        from patterns.p19_spatial_partition import Grid, Unit
        rng = random.Random(7)
        grid = Grid(448, 496, 32)
        units = [Unit(i, rng.uniform(0, 448), rng.uniform(0, 496)) for i in range(150)]
        for u in units:
            grid.add(u)
        for u in units[:50]:
            grid.move(u, rng.uniform(0, 448), rng.uniform(0, 496))
        found = set()
        grid.handle_collisions(20, lambda a, b: found.add(frozenset((a, b))))
        brute = {frozenset((a.owner, b.owner)) for i, a in enumerate(units) for b in units[i + 1:]
                 if (a.x - b.x) ** 2 + (a.y - b.y) ** 2 < 400}
        self.assertEqual(found, brute)
        self.assertLess(grid.checks_last, grid.brute_force_checks())


if __name__ == "__main__":
    unittest.main()
