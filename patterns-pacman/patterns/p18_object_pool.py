"""
Pattern 18 of 19 - OBJECT POOL
==============================
Book: "Optimization Patterns > Object Pool"
      https://gameprogrammingpatterns.com/object-pool.html

  "Improve performance and memory use by reusing objects from a fixed pool
   instead of allocating and freeing them individually."

THE PROBLEM (book section "The curse of fragmentation")
    Short-lived objects created and destroyed all the time (particles,
    bullets, floating score numbers) fragment the heap in C++ and
    keep the garbage collector busy in Python.

THE PATTERN (book section "The Pattern")
    Allocate a fixed array of objects once. "Creating" an object means
    finding an unused one and initialising it. "Destroying" it just marks it
    unused. Nothing is allocated during gameplay.

A FREE LIST (book section "A free list")
    Searching the array for an unused object is O(n). The book's trick:
    unused objects store a pointer to the *next unused object*, forming a
    linked list threaded through the pool itself. ``first_available`` points
    at its head, so create and destroy are O(1) with no extra memory. (In C++
    the book overlays the pointer on the particle's live data with a
    ``union``. Python has no unions, so ``next_free`` is its own field, only
    meaningful while the popup is unused.)

WHERE IT IS USED IN THE GAME
    ``PopupPool`` holds the floating texts: "200", "400", "800", "1600" when
    ghosts are eaten, the fruit bonuses and achievement banners. The panel
    shows how many are in use.

KEEP IN MIND (book section "Keep in Mind")
    * "Only a fixed number of objects can be active at any one time": when
      the pool is empty, ``create`` refuses (and counts the refusal). For
      cosmetic popups, dropping one is the right choice.
    * "Reused objects aren't automatically cleared": ``create`` sets *every*
      field, so no stale text or colour can leak from a previous use.
    * "Memory size for each object is fixed": all popups are the same class.
"""


class Popup:
    """A floating text. Either in use (timer > 0) or a link in the free list."""
    __slots__ = ("x", "y", "text", "colour", "timer", "rise", "next_free")

    def __init__(self):
        self.x = self.y = 0.0
        self.text = ""
        self.colour = (255, 255, 255)
        self.timer = 0.0          # > 0 means "in use"
        self.rise = 0.0
        self.next_free = None     # only meaningful while unused

    @property
    def in_use(self) -> bool:
        return self.timer > 0


class PopupPool:
    POOL_SIZE = 12

    def __init__(self, size: int = POOL_SIZE):
        self.popups = [Popup() for _ in range(size)]
        # Thread the free list through the pool: each popup points at the next.
        self.first_available = self.popups[0]
        for current, following in zip(self.popups, self.popups[1:]):
            current.next_free = following
        self.popups[-1].next_free = None
        self.refused = 0
        self.created = 0

    def create(self, x, y, text, colour=(255, 255, 255), seconds=1.0, rise=14.0) -> bool:
        popup = self.first_available
        if popup is None:
            self.refused += 1                    # pool exhausted
            return False
        self.first_available = popup.next_free   # pop the head of the free list
        # Initialise every field: reused objects aren't cleared automatically.
        popup.x, popup.y = x, y
        popup.text = text
        popup.colour = colour
        popup.timer = seconds
        popup.rise = rise
        popup.next_free = None
        self.created += 1
        return True

    def update(self, dt: float) -> None:
        for popup in self.popups:
            if popup.in_use:
                popup.timer -= dt
                popup.y -= popup.rise * dt
                if popup.timer <= 0:
                    # Push it back onto the free list: O(1), no deallocation.
                    popup.timer = 0.0
                    popup.next_free = self.first_available
                    self.first_available = popup

    def clear(self) -> None:
        for popup in self.popups:
            if popup.in_use:
                popup.timer = 0.0
                popup.next_free = self.first_available
                self.first_available = popup

    @property
    def in_use_count(self) -> int:
        return sum(1 for p in self.popups if p.in_use)

    def render(self, surface, text) -> None:
        """``text`` is a support.text.Text used to draw the strings."""
        for popup in self.popups:
            if popup.in_use:
                text.draw_centred(surface, popup.text, popup.x, popup.y - text.height / 2, popup.colour)
