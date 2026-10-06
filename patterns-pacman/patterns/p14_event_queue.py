"""
Pattern 14 of 19 - EVENT QUEUE
==============================
Book: "Decoupling Patterns > Event Queue"
      https://gameprogrammingpatterns.com/event-queue.html

  "Decouple when a message or event is sent from when it is processed."

THE PROBLEM (book section "Motivation", and its audio sample)
    Observer (p03) is *synchronous*: ``play_sound`` would run inside the
    dot-eating code, in the middle of a game update. Three problems, all
    straight from the book's audio example:
      1. The caller is blocked while the sound starts.
      2. Requests can't be combined: eat two dots in one frame and the same
         sound starts twice, twice as loud.
      3. Requests can arrive from anywhere at any time (the book even worries
         about other threads).

THE PATTERN (book section "The Pattern")
    A queue stores messages in the order they were sent. ``play_sound`` just
    *enqueues* a request and returns at once. Later, once per update, the
    audio engine *processes* what is queued. Sender and receiver are
    decoupled in *time*, not just in code.

SAMPLE CODE (book sections "A ring buffer" / "Aggregating requests")
    * ``RingBuffer``: a fixed array with ``head`` and ``tail`` indices that
      wrap around. No allocation per message, and both push and pop are O(1).
      When it is full we drop the request and count it (the book asserts).
    * Aggregating: before enqueuing, ``play_sound`` walks the pending
      requests. If the same sound is already waiting, it merges the two
      (keeping the louder volume) instead of queuing a duplicate.
    * Like the book, ``update`` processes ONE request per call, so the panel
      can show a queue that really fills and drains.

WHERE IT IS USED IN THE GAME
    ``AudioEngine`` is the real (pygame) audio service. The Service Locator
    (p15) hands it out, and the AudioObserver (p15) and fruit sandbox (p11) call
    ``play_sound``. The game loop calls ``audio.update()`` every fixed step.

KEEP IN MIND (book section "Keep in Mind")
    * "A central event queue is a global variable": ours is private to the
      audio engine. Only ``play_sound`` can write to it.
    * "The state of the world can change under you": by the time a request
      is processed, the event that caused it is in the past. Fine for sounds.
    * "You can get stuck in feedback loops": processing a request here never
      sends a new one.
"""
import pygame

from support import synth


class RingBuffer:
    """A fixed-capacity FIFO queue in a circular array."""

    def __init__(self, capacity: int):
        self._items = [None] * capacity
        self.capacity = capacity
        self.head = 0       # index of the oldest item
        self.tail = 0       # index where the next item goes
        self.count = 0

    def __len__(self) -> int:
        return self.count

    def push(self, item) -> bool:
        if self.count == self.capacity:
            return False                      # full: the caller decides what to do
        self._items[self.tail] = item
        self.tail = (self.tail + 1) % self.capacity    # wrap around
        self.count += 1
        return True

    def pop(self):
        if self.count == 0:
            return None
        item = self._items[self.head]
        self._items[self.head] = None
        self.head = (self.head + 1) % self.capacity
        self.count -= 1
        return item

    def pending(self):
        """Iterate over queued items, oldest first, without removing them."""
        for i in range(self.count):
            yield self._items[(self.head + i) % self.capacity]


class PlayMessage:
    """One queued request: which sound, how loud."""
    __slots__ = ("sound_id", "volume")

    def __init__(self, sound_id: str, volume: float):
        self.sound_id = sound_id
        self.volume = volume


class AudioEngine:
    """The real audio service: queued, aggregated, played by pygame."""
    MAX_PENDING = 16

    def __init__(self):
        self.queue = RingBuffer(self.MAX_PENDING)
        self.sounds = synth.render_all() if pygame.mixer.get_init() else {}
        self.requested = 0
        self.merged = 0
        self.dropped = 0
        self.played = 0

    def play_sound(self, sound_id: str, volume: float = 1.0) -> None:
        """Enqueue a request and return immediately."""
        self.requested += 1
        for message in self.queue.pending():       # "Aggregating requests"
            if message.sound_id == sound_id:
                message.volume = max(message.volume, volume)
                self.merged += 1
                return
        if not self.queue.push(PlayMessage(sound_id, volume)):
            self.dropped += 1

    def update(self) -> None:
        """Process one pending request (call once per game update)."""
        message = self.queue.pop()
        if message is None:
            return
        sound = self.sounds.get(message.sound_id)
        if sound is not None:
            sound.set_volume(message.volume)
            sound.play()
            self.played += 1

    def stop_all(self) -> None:
        while self.queue.pop() is not None:
            pass
        if pygame.mixer.get_init():
            pygame.mixer.stop()
