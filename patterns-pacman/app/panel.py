"""The "patterns at work" panel: one live line per pattern, in book order.

Each line shows a number that only exists because of that pattern, so you can
watch, for example, the event queue fill and drain or the dirty flag skip work.
"""
from support.constants import (MAZE_W, PANEL_W, SCREEN_H, PANEL_BG, PANEL_TEXT,
                               PANEL_TITLE, PANEL_DIM, PACMAN_YELLOW)
from patterns.p15_service_locator import Locator, LoggedAudio

SECTIONS = [
    ("Design Patterns Revisited", ["01 Command", "02 Flyweight", "03 Observer",
                                   "04 Prototype", "05 Singleton", "06 State"]),
    ("Sequencing", ["07 Double Buffer", "08 Game Loop", "09 Update Method"]),
    ("Behavioral", ["10 Bytecode", "11 Subclass Sandbox", "12 Type Object"]),
    ("Decoupling", ["13 Component", "14 Event Queue", "15 Service Locator"]),
    ("Optimization", ["16 Data Locality", "17 Dirty Flag", "18 Object Pool",
                      "19 Spatial Partition"]),
]

KEYS = ["Arrows/WASD move   Enter start   P pause",
        "M mute   Tab debug overlay   F1 panel   Esc quit"]


class Panel:
    LINE = 18

    def __init__(self, game):
        self.game = game

    def stats(self) -> dict:
        g = self.game
        audio = Locator.get_audio()
        if Locator.is_null():
            audio_name = "NullAudio" + (" (muted)" if g.muted else " (no mixer)")
        elif isinstance(audio, LoggedAudio):
            audio_name = "LoggedAudio(AudioEngine)"
        else:
            audio_name = type(audio).__name__
        engine = g.audio_engine
        blinky = g.world.ghost_named("blinky")
        grid = g.grid
        return {
            "01 Command": f"last: {g.last_command}",
            "02 Flyweight": f"{len(g.maze.tiles)} cells -> {g.maze.distinct_tile_objects()} Tiles",
            "03 Observer": f"{g.subject.observer_count} observers, {g.subject.notifications} sent",
            "04 Prototype": f"{type(g.fruit_spawner.prototype).__name__} x{g.fruit_spawner.spawned}",
            "05 Singleton": f"Settings: debug {'on' if g.settings.show_debug else 'off'}",
            "06 State": f"{'>'.join(g.flow.names())} | Blinky {blinky.brain.state.name}",
            "07 Double Buffer": f"buffer {0 if g.frame_buffer.next is g.frame_buffer._buffers[0] else 1} | {g.frame_buffer.swaps} swaps",
            "08 Game Loop": f"{g.fps:4.0f} fps {g.ups:3.0f} ups, {g.updates_last_frame} upd/frame",
            "09 Update Method": f"{len(g.world.entities)} entities, {g.world.updates} updates",
            "10 Bytecode": f"{g.vm.instructions_run} VM instructions",
            "11 Subclass Sandbox": f"last bonus: {g.last_bonus}",
            "12 Type Object": f"{len(g.breeds.playable())} breeds + 'ghost' parent",
            "13 Component": f"Pac-Man input: {type(g.pacman.input).__name__[:-9]}",
            "14 Event Queue": (f"{len(engine.queue)}/{engine.MAX_PENDING} queued, {engine.merged} merged"
                               if engine else "no audio engine"),
            "15 Service Locator": audio_name,
            "16 Data Locality": f"{g.particles.num_active}/{g.particles.capacity} sparks (packed)",
            "17 Dirty Flag": f"{g.maze_renderer.tiles_redrawn_last} tiles redrawn, text x{g.score_text.renders}",
            "18 Object Pool": f"{g.popups.in_use_count}/{len(g.popups.popups)} popups, {g.popups.refused} refused",
            "19 Spatial Partition": f"{grid.checks_last} checks vs {grid.brute_force_checks()} brute",
        }

    def render(self, surface) -> None:
        g = self.game
        x0 = MAZE_W
        surface.fill(PANEL_BG, (x0, 0, PANEL_W, SCREEN_H))
        if not g.settings.show_panel:
            g.small_text.draw(surface, "F1: show the patterns panel", x0 + 12, 12, PANEL_DIM)
            return
        g.text.draw(surface, "Game Programming Patterns", x0 + 12, 8, PACMAN_YELLOW)
        g.small_text.draw(surface, "R. Nystrom - live in this game", x0 + 12, 28, PANEL_DIM)
        stats = self.stats()
        y = 50
        for title, names in SECTIONS:
            g.small_text.draw(surface, title, x0 + 8, y, PANEL_TITLE)
            y += self.LINE
            for name in names:
                g.small_text.draw(surface, name, x0 + 14, y, PANEL_TEXT)
                g.small_text.draw(surface, stats[name], x0 + 148, y, PANEL_DIM)
                y += self.LINE
            y += 3
        y = SCREEN_H - 40
        for line in KEYS:
            g.small_text.draw(surface, line, x0 + 8, y, PANEL_DIM)
            y += 16
