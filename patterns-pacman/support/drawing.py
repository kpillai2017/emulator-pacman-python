"""Vector drawing of Pac-Man, ghosts and fruit with pygame.draw (no image files)."""
import math

import pygame

from support.constants import (Direction, PACMAN_YELLOW, FRIGHT_BLUE, WHITE, TILE)

R = TILE * 0.8   # actor radius: a bit larger than half a tile, like the arcade


def pacman(surface, x, y, facing: Direction, mouth: float, radius: float = R):
    """Draw Pac-Man. ``mouth`` is the half-angle of the mouth in degrees (0..180)."""
    if mouth <= 1:
        pygame.draw.circle(surface, PACMAN_YELLOW, (int(x), int(y)), int(radius))
        return
    if mouth >= 179:
        return  # fully "opened": nothing left (end of the death animation)
    base = {Direction.RIGHT: 0, Direction.UP: 90, Direction.LEFT: 180,
            Direction.DOWN: 270}.get(facing, 0)
    points = [(x, y)]
    steps = 24
    start, end = base + mouth, base + 360 - mouth
    for i in range(steps + 1):
        a = math.radians(start + (end - start) * i / steps)
        points.append((x + radius * math.cos(a), y - radius * math.sin(a)))
    pygame.draw.polygon(surface, PACMAN_YELLOW, points)


def ghost(surface, x, y, colour, facing: Direction, look: str, wobble: int):
    """Draw a ghost. ``look`` is 'normal', 'frightened', 'flash' or 'eyes'."""
    r = R
    if look != "eyes":
        body = colour
        if look == "frightened":
            body = FRIGHT_BLUE
        elif look == "flash":
            body = WHITE
        # Round head + rectangular skirt with wavy feet.
        pygame.draw.circle(surface, body, (int(x), int(y - r * 0.15)), int(r))
        top = y - r * 0.15
        bottom = y + r
        feet = [(x - r, top), (x + r, top), (x + r, bottom)]
        n = 6
        for i in range(n + 1):
            fx = x + r - (2 * r) * i / n
            fy = bottom - (r * 0.35 if (i + wobble) % 2 else 0)
            feet.append((fx, fy))
        feet.append((x - r, bottom))
        pygame.draw.polygon(surface, body, feet)
        if look in ("frightened", "flash"):
            face = (255, 184, 151) if look == "frightened" else (255, 0, 0)
            for ex in (-0.35, 0.35):
                pygame.draw.circle(surface, face, (int(x + ex * r), int(y - r * 0.3)), 2)
            pts = [(x - r * 0.6 + i * r * 0.2, y + r * 0.3 + (3 if i % 2 else 0)) for i in range(7)]
            pygame.draw.lines(surface, face, False, pts, 1)
            return
    # Eyes look the way the ghost is heading.
    for ex in (-0.38, 0.38):
        cx, cy = x + ex * r, y - r * 0.3
        pygame.draw.circle(surface, WHITE, (int(cx), int(cy)), int(r * 0.3))
        pygame.draw.circle(surface, (33, 33, 222),
                           (int(cx + facing.dx * r * 0.14), int(cy + facing.dy * r * 0.14)),
                           int(r * 0.15))


FRUIT_COLOURS = {
    "cherry": (255, 0, 0), "strawberry": (255, 40, 80), "orange": (255, 160, 0),
    "apple": (230, 0, 0), "melon": (60, 200, 60), "galaxian": (255, 255, 0),
    "bell": (255, 220, 0), "key": (120, 200, 255),
}


def fruit(surface, x, y, kind: str, scale: float = 1.0):
    """Draw a simple fruit icon."""
    colour = FRUIT_COLOURS.get(kind, WHITE)
    r = int(TILE * 0.45 * scale)
    if kind == "cherry":
        pygame.draw.line(surface, (180, 120, 40), (x - r // 2, y), (x + r // 2, y - r * 1.4), 2)
        pygame.draw.line(surface, (180, 120, 40), (x + r // 2, y + 2), (x + r // 2, y - r * 1.4), 2)
        pygame.draw.circle(surface, colour, (int(x - r // 2), int(y + 2)), r - 1)
        pygame.draw.circle(surface, colour, (int(x + r // 2), int(y + 4)), r - 1)
    elif kind == "key":
        pygame.draw.circle(surface, colour, (int(x), int(y - r // 2)), r // 2 + 2, 2)
        pygame.draw.line(surface, WHITE, (x, y), (x, y + r + 2), 2)
        pygame.draw.line(surface, WHITE, (x, y + r), (x + 3, y + r), 2)
    elif kind == "bell":
        pygame.draw.polygon(surface, colour, [(x, y - r), (x + r, y + r // 2), (x - r, y + r // 2)])
        pygame.draw.circle(surface, WHITE, (int(x), int(y + r // 2 + 2)), 2)
    elif kind == "galaxian":
        pygame.draw.polygon(surface, colour, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)])
        pygame.draw.circle(surface, (255, 0, 0), (int(x), int(y)), r // 3)
    else:
        pygame.draw.circle(surface, colour, (int(x), int(y + 1)), r)
        pygame.draw.line(surface, (60, 160, 60), (x, y - r + 1), (x + 3, y - r - 3), 2)
