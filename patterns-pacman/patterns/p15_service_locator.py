"""
Pattern 15 of 19 - SERVICE LOCATOR
==================================
Book: "Decoupling Patterns > Service Locator"
      https://gameprogrammingpatterns.com/service-locator.html

  "Provide a global point of access to a service without coupling users to
   the concrete class that implements it."

THE PROBLEM (book section "Motivation")
    Lots of code wants to play a sound: the observer reacting to events, the
    fruit sandbox, the game states. Passing an audio object through every
    constructor is noisy. A Singleton (p05) would hard-wire *which* class
    plays sound, and you couldn't mute by swapping it out.

THE PATTERN (book section "The Pattern")
    * "The service": an abstract ``Audio`` interface.
    * "The service provider": ``AudioEngine`` from p14 (the queued pygame
      implementation) is registered as an Audio.
    * "A simple locator": ``Locator.get_audio()`` / ``Locator.provide(...)``.
      Users only know the interface. Main code decides which provider.
    * "A null service": ``NullAudio`` does nothing. The locator returns it
      when nothing (or None) was provided, so callers *never* need an
      ``if audio is not None`` check, and the game runs fine without a sound card.
    * "Logging decorator": ``LoggedAudio`` wraps another Audio and prints
      every call (``python main.py --log-audio``), with no change to any caller.

WHERE IT IS USED IN THE GAME
    * app/game.py provides the AudioEngine at start-up (or nothing, if the
      mixer failed to start: then the NullAudio is used automatically).
    * Pressing M (MuteCommand, p01) provides None -> NullAudio, and pressing M
      again provides the engine again: the book's "disable audio" trick.
    * ``AudioObserver`` below listens to gameplay events (Observer, p03) and
      plays sounds through the locator.

DESIGN DECISIONS (book section "Design Decisions")
    * "How is the service located?": registered at runtime by outside code
      (``provide``).
    * "What happens if the service can't be located?": return a null service.
    * "What is the scope of the service?": global (class-level).

PYTHON NOTE
    ``Audio.register(AudioEngine)`` makes AudioEngine a *virtual subclass* of
    the abstract interface without p14 having to import p15 (which would break
    our "only import earlier modules" rule).
"""
from abc import ABC, abstractmethod

from patterns.p03_observer import Observer, Event
from patterns.p14_event_queue import AudioEngine


class Audio(ABC):
    """The service interface."""

    @abstractmethod
    def play_sound(self, sound_id: str, volume: float = 1.0) -> None: ...

    @abstractmethod
    def stop_all(self) -> None: ...

    @abstractmethod
    def update(self) -> None: ...


Audio.register(AudioEngine)     # the real provider, from p14


class NullAudio(Audio):
    """Does nothing, successfully."""

    def play_sound(self, sound_id: str, volume: float = 1.0) -> None:
        pass

    def stop_all(self) -> None:
        pass

    def update(self) -> None:
        pass


class LoggedAudio(Audio):
    """Decorator: logs every request, then forwards it to the wrapped service."""

    def __init__(self, wrapped: Audio, log=print):
        self.wrapped = wrapped
        self.log = log

    def play_sound(self, sound_id: str, volume: float = 1.0) -> None:
        self.log(f"[audio] play {sound_id} (volume {volume:.2f})")
        self.wrapped.play_sound(sound_id, volume)

    def stop_all(self) -> None:
        self.log("[audio] stop all")
        self.wrapped.stop_all()

    def update(self) -> None:
        self.wrapped.update()

    def __getattr__(self, name):
        return getattr(self.wrapped, name)    # expose stats of the wrapped service


class Locator:
    """Where code finds the audio service."""
    _null = NullAudio()
    _service = _null

    @classmethod
    def get_audio(cls) -> Audio:
        return cls._service

    @classmethod
    def provide(cls, service) -> None:
        cls._service = service if service is not None else cls._null

    @classmethod
    def is_null(cls) -> bool:
        return cls._service is cls._null


class AudioObserver(Observer):
    """Plays a sound for gameplay events, via the locator."""

    SOUNDS = {
        Event.DOT_EATEN: "chomp",
        Event.POWER_PELLET_EATEN: "power",
        Event.GHOST_EATEN: "eat_ghost",
        Event.FRUIT_EATEN: "eat_fruit",
        Event.PACMAN_DIED: "death",
        Event.EXTRA_LIFE: "extra_life",
        Event.ACHIEVEMENT_UNLOCKED: "achievement",
        Event.LEVEL_CLEARED: "level_clear",
        Event.GAME_STARTED: "start",
    }

    def on_notify(self, entity, event, data) -> None:
        sound = self.SOUNDS.get(event)
        if sound:
            Locator.get_audio().play_sound(sound, 0.6 if sound == "chomp" else 1.0)
