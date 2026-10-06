"""Headless end-to-end tests: the whole game, driven with fake time and keys."""
import unittest

import tests  # noqa: F401  (sets up sys.path and the headless SDL drivers)
import pygame

from patterns.p05_singleton import Settings
from patterns.p06_state import Eaten
from patterns.p03_observer import Event
from app.game import PatternManGame
from app.game_states import PlayingState

FRAME_MS = 1000 / 60


def run(game, seconds, keys=()):
    inp = game.get_input()
    for _ in range(int(seconds * 60)):
        inp.update()
        for key in keys:
            inp.keys[key] = True
        game.tick(FRAME_MS)


def press(game, key):
    inp = game.get_input()
    inp.update()
    inp.key_hits.add(key)
    inp.keys[key] = True
    game.tick(FRAME_MS)
    inp.keys[key] = False


class TestGame(unittest.TestCase):
    def setUp(self):
        Settings._reset_for_tests()
        self.game = PatternManGame(seed=1)
        self.assertTrue(self.game.init())

    def tearDown(self):
        Settings._reset_for_tests()

    def test_attract_mode_plays_by_itself(self):
        run(self.game, 8)
        self.assertEqual(self.game.flow.names(), ["attract"])
        self.assertLess(self.game.maze.dots_left, self.game.maze.total_dots)
        self.assertEqual(self.game.scoreboard.score, 0)   # scoreboard not subscribed in the demo

    def test_start_play_pause_and_score(self):
        g = self.game
        press(g, pygame.K_RETURN)
        self.assertEqual(g.flow.state.name, "ready")
        run(g, 3, keys=[pygame.K_LEFT])
        self.assertEqual(g.flow.state.name, "playing")
        self.assertGreater(g.scoreboard.score, 0)
        press(g, pygame.K_p)
        self.assertEqual(g.flow.names(), ["playing", "paused"])
        x = g.pacman.x
        run(g, 1)
        self.assertEqual(g.pacman.x, x)                   # frozen while paused
        press(g, pygame.K_p)
        self.assertEqual(g.flow.names(), ["playing"])

    def test_eat_ghost_and_lose_life(self):
        g = self.game
        g.new_game()
        g.flow.change(PlayingState())
        blinky = g.world.ghost_named("blinky")
        g.notify(g.pacman, Event.POWER_PELLET_EATEN, {"points": 50})
        self.assertTrue(blinky.brain.state.edible)
        blinky.place(g.pacman.x, g.pacman.y)
        g._collide()
        self.assertIsInstance(blinky.brain.state, Eaten)
        self.assertEqual(g.scoreboard.score, 50 + 200)
        # Back to normal, then touching a dangerous ghost costs a life.
        g.reset_actors()
        blinky.place(g.pacman.x, g.pacman.y)
        lives = g.scoreboard.lives
        run(g, 0.1)
        self.assertEqual(g.flow.state.name, "dying")
        self.assertEqual(g.scoreboard.lives, lives - 1)

    def test_level_complete_advances(self):
        g = self.game
        g.new_game()
        g.flow.change(PlayingState())
        for row in range(g.maze.rows):
            for col in range(g.maze.cols):
                g.maze.eat(col, row)
        run(g, 0.1)
        self.assertEqual(g.flow.state.name, "level complete")
        self.assertIn("clean_sweep", g.achievements.unlocked)
        run(g, 3)
        self.assertEqual(g.world.level, 2)
        self.assertEqual(g.maze.dots_left, g.maze.total_dots)

    def test_fruit_spawns_and_mute_swaps_service(self):
        from patterns.p15_service_locator import Locator
        g = self.game
        g.new_game()
        for _ in range(70):
            col, row = next((c, r) for r in range(g.maze.rows) for c in range(g.maze.cols)
                            if g.maze.tile(c, r).is_dot and not g.maze.tile(c, r).is_power)
            g.pacman.place(col * 16 + 8, row * 16 + 8)
            g._eat_dots()
        self.assertIsNotNone(g.fruit)
        self.assertEqual(g.fruit.kind, "cherry")
        g.toggle_mute()
        self.assertTrue(Locator.is_null())
        g.toggle_mute()
        self.assertEqual(Locator.is_null(), g.audio_engine is None)


if __name__ == "__main__":
    unittest.main()
