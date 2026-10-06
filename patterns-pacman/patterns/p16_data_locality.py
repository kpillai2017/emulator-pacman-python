"""
Pattern 16 of 19 - DATA LOCALITY
================================
Book: "Optimization Patterns > Data Locality"
      https://gameprogrammingpatterns.com/data-locality.html

  "Accelerate memory access by arranging data to take advantage of CPU
   caching."

THE IDEA (book sections "A data warehouse" / "A pallet for your CPU")
    Reading memory is far slower than computing. The CPU fetches memory a
    whole *cache line* at a time, so data that is used together should sit
    together. Then one fetch brings in the next several items too.

THE BOOK'S TECHNIQUES (book section "Sample Code")
    * "Contiguous arrays": store the things you loop over in flat arrays,
      not as scattered objects reached through pointers.
    * "Packed data": keep the *active* items at the front of the array, so
      the update loop touches only live data and never tests "is this one
      alive?". When an item dies, swap the last active item into its slot.
    * "Hot/cold splitting": keep the fields used every update (position,
      velocity, life: *hot*) apart from fields used rarely (colour, used only
      when drawing: *cold*).

WHERE IT IS USED IN THE GAME
    ``ParticleSystem`` (the sparks when Pac-Man eats a pellet, a ghost or a
    fruit, or dies) follows all three ideas. It is a "structure of arrays":
    one ``array.array`` per field instead of a list of Particle objects. Each
    ``array.array`` really is a contiguous block of C floats.

AN HONEST PYTHON CAVEAT
    CPython interprets bytecode, and every value read from an array becomes a
    Python object, so cache effects are mostly hidden behind interpreter
    overhead. The *layout* is still the right habit: it is exactly how you
    would write this in C/C++ (or with NumPy, where it gives big speed-ups),
    and "packed data" saves real work here because dead particles are never
    visited. The book's own advice applies: measure before you optimise.

SEE ALSO
    Object Pool (p18): a packed particle array is also a pool, since memory is
    allocated once and reused. The book's Object Pool chapter uses particles
    too. We use a different technique (a free list) for the score popups there.
"""
import random
from array import array

GRAVITY = 220.0     # pixels / s^2, so sparks fall a little


class ParticleSystem:
    """Particles as a structure of arrays, with live particles packed at the front."""

    def __init__(self, capacity: int = 512, rng: random.Random = None):
        self.capacity = capacity
        self.rng = rng or random.Random()
        # HOT data: touched by every update.
        self.x = array("f", [0.0]) * capacity
        self.y = array("f", [0.0]) * capacity
        self.vx = array("f", [0.0]) * capacity
        self.vy = array("f", [0.0]) * capacity
        self.life = array("f", [0.0]) * capacity
        # COLD data: only read when drawing.
        self.colour = [(255, 255, 255)] * capacity
        self.num_active = 0       # particles [0, num_active) are alive
        self.peak = 0

    def emit(self, x: float, y: float, count: int, colour, speed: float = 90.0) -> None:
        rnd = self.rng.uniform
        for _ in range(count):
            if self.num_active == self.capacity:
                return                       # full: simply emit fewer sparks
            i = self.num_active              # the first dead slot
            self.x[i], self.y[i] = x, y
            self.vx[i] = rnd(-speed, speed)
            self.vy[i] = rnd(-speed * 1.2, speed * 0.4)
            self.life[i] = rnd(0.35, 0.8)
            self.colour[i] = colour
            self.num_active += 1
        self.peak = max(self.peak, self.num_active)

    def update(self, dt: float) -> None:
        x, y, vx, vy, life = self.x, self.y, self.vx, self.vy, self.life
        i = 0
        while i < self.num_active:           # only live data is visited
            life[i] -= dt
            if life[i] <= 0:
                self._deactivate(i)          # don't advance i: a new one moved in
                continue
            vy[i] += GRAVITY * dt
            x[i] += vx[i] * dt
            y[i] += vy[i] * dt
            i += 1

    def _deactivate(self, i: int) -> None:
        """Packed data: move the last live particle into slot i."""
        last = self.num_active - 1
        if i != last:
            self.x[i], self.y[i] = self.x[last], self.y[last]
            self.vx[i], self.vy[i] = self.vx[last], self.vy[last]
            self.life[i] = self.life[last]
            self.colour[i] = self.colour[last]
        self.num_active = last

    def clear(self) -> None:
        self.num_active = 0

    def render(self, surface) -> None:
        fill = surface.fill
        for i in range(self.num_active):
            fill(self.colour[i], (int(self.x[i]), int(self.y[i]), 3, 3))
