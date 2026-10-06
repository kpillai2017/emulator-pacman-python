"""The game flow as states on a pushdown automaton (State pattern, p06).

    Attract --start--> Ready --> Playing --caught--> Dying --lives left--> Ready
                                   |  ^                 \\--no lives--> GameOver --> Attract
                          dots gone|  |pause/unpause
                                   v  |
                          LevelComplete   Paused (pushed on top of Playing, then popped)

Each state's ``handle`` receives the game-flow inputs "start" and "pause"
(sent by StartCommand / PauseCommand, Command pattern p01). ``overlay`` draws the
state's text over the maze (READY!, GAME OVER...).

Book: https://gameprogrammingpatterns.com/state.html
      ("Enter and Exit Actions", "Pushdown Automata")
"""
from support.constants import TILE, MAZE_W, PACMAN_YELLOW, WHITE
from patterns.p03_observer import Event
from patterns.p06_state import State
from patterns.p15_service_locator import Locator

MESSAGE_Y = 17 * TILE + 1      # the row under the ghost house, like the arcade


class FlowState(State):
    def overlay(self, game, surface) -> None:
        pass


class AttractState(FlowState):
    """The demo: Robo-Pac-Man (Component pattern's "Robo-Bjørn") plays itself."""
    name = "attract"

    def enter(self, game) -> None:
        game.setup_demo()
        self.time = 0.0

    def update(self, game, dt) -> None:
        self.time += dt
        game.step_world(dt)
        if game.pacman_caught or game.maze.dots_left == 0 or self.time > 60:
            game.setup_demo()            # start the demo again
            self.time = 0.0

    def handle(self, game, event, data) -> bool:
        if event == "start":
            game.new_game()
            game.flow.change(ReadyState(first=True))
            return True
        return False

    def overlay(self, game, surface) -> None:
        game.big_text.draw_centred(surface, "PATTERN-MAN", MAZE_W / 2, 11 * TILE - 4, PACMAN_YELLOW)
        if int(self.time * 2) % 2 == 0:
            game.text.draw_centred(surface, "PRESS ENTER TO PLAY", MAZE_W / 2, MESSAGE_Y, WHITE)


class ReadyState(FlowState):
    """A short pause before play begins."""
    name = "ready"

    def __init__(self, first: bool = False):
        self.first = first

    def enter(self, game) -> None:
        self.timer = 2.2 if self.first else 1.5
        game.hold_world()

    def update(self, game, dt) -> None:
        self.timer -= dt
        game.hold_world()
        if self.timer <= 0:
            game.flow.change(PlayingState())

    def overlay(self, game, surface) -> None:
        game.text.draw_centred(surface, "READY!", MAZE_W / 2, MESSAGE_Y, PACMAN_YELLOW)


class PlayingState(FlowState):
    name = "playing"

    def update(self, game, dt) -> None:
        game.step_world(dt)
        if game.pacman_caught:
            game.flow.change(DyingState())
        elif game.maze.dots_left == 0:
            game.flow.change(LevelCompleteState())

    def handle(self, game, event, data) -> bool:
        if event == "pause":
            game.flow.push(PausedState())        # pushdown: Playing stays underneath
            return True
        return False


class PausedState(FlowState):
    name = "paused"

    def enter(self, game) -> None:
        Locator.get_audio().stop_all()

    def update(self, game, dt) -> None:
        game.hold_world()

    def handle(self, game, event, data) -> bool:
        if event in ("pause", "start"):
            game.flow.pop()                      # back to exactly where Playing was
            return True
        return False

    def overlay(self, game, surface) -> None:
        game.big_text.draw_centred(surface, "PAUSED", MAZE_W / 2, MESSAGE_Y - 4, WHITE)


class DyingState(FlowState):
    name = "dying"
    FREEZE = 0.6
    SHRINK = 1.4

    def enter(self, game) -> None:
        self.time = 0.0
        game.notify(game.pacman, Event.PACMAN_DIED)   # Scoreboard takes a life

    def update(self, game, dt) -> None:
        self.time += dt
        game.hold_world()
        game.particles.update(dt)
        game.popups.update(dt)
        if self.time > self.FREEZE:
            for ghost in game.ghosts:
                ghost.active = False                  # hide the ghosts
            game.pacman.dying = min(1.0, (self.time - self.FREEZE) / self.SHRINK)
        if self.time > self.FREEZE + self.SHRINK + 0.5:
            if game.scoreboard.lives > 0:
                game.reset_actors()
                game.flow.change(ReadyState())
            else:
                game.flow.change(GameOverState())


class LevelCompleteState(FlowState):
    name = "level complete"

    def enter(self, game) -> None:
        self.time = 0.0
        game.notify(game.pacman, Event.LEVEL_CLEARED)
        for ghost in game.ghosts:
            ghost.active = False

    def update(self, game, dt) -> None:
        self.time += dt
        game.hold_world()
        game.particles.update(dt)
        game.popups.update(dt)
        game.maze_flash = int(self.time * 5) % 2 == 1
        if self.time > 2.4:
            game.maze_flash = False
            game.start_level(game.world.level + 1)
            game.flow.change(ReadyState())


class GameOverState(FlowState):
    name = "game over"

    def enter(self, game) -> None:
        self.timer = 3.0

    def update(self, game, dt) -> None:
        self.timer -= dt
        game.hold_world()
        if self.timer <= 0:
            game.flow.change(AttractState())

    def handle(self, game, event, data) -> bool:
        if event == "start" and self.timer < 2.0:
            game.flow.change(AttractState())
            return True
        return False

    def overlay(self, game, surface) -> None:
        game.text.draw_centred(surface, "GAME  OVER", MAZE_W / 2, MESSAGE_Y, (255, 0, 0))
