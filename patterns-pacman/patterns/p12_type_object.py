"""
Pattern 12 of 19 - TYPE OBJECT
==============================
Book: "Behavioral Patterns > Type Object"
      https://gameprogrammingpatterns.com/type-object.html

  "Allow the flexible creation of new 'classes' by creating a single class,
   each instance of which represents a different type of object."

THE PROBLEM (book section "The typical OOP answer")
    The obvious design is ``class Blinky(Ghost)``, ``class Pinky(Ghost)``...
    But the four ghosts differ only in *data*: colour, speed, home corner,
    release time and targeting rule. A subclass per ghost means a programmer
    and a recompile (or at least a code change) for every new ghost.

THE PATTERN (book section "A class for a class")
    Two classes instead of N:
      * ``Breed``: the *type object*. One instance per kind of ghost,
        loaded from data/breeds.json.
      * the ghost itself (p13_component.py): the *typed object*. It holds a
        reference to its breed and asks it for anything type-specific
        (``ghost.breed.speed``, ``ghost.breed.colour``...).
    Adding a fifth ghost is a JSON edit. That is the book's "When to Use It":
    you don't know which types you'll need up front, or want to change them
    without code changes.

SHARING DATA THROUGH INHERITANCE (book section of the same name)
    Breeds can name a ``parent`` breed and inherit any field they don't
    define. Following the book's advice we use *copy-down* inheritance: at
    load time each field is resolved once and copied into the child, so a
    lookup at runtime is just an attribute read. In breeds.json, the abstract
    "ghost" breed holds the shared defaults and the four real ghosts override
    only what makes them different.

BEHAVIOUR AS WELL AS DATA (book section "It's harder to define *behavior* for each type")
    The book suggests combining Type Object with Bytecode for per-type
    *behaviour*. That is exactly what ``chase_program`` is: each breed's
    targeting rule is assembled into bytecode for the VM in p10.

DESIGN DECISIONS (book section "Design Decisions")
    * "Is the type object encapsulated or exposed?": exposed; ghosts read
      ``ghost.breed`` directly.
    * "How are typed objects created?": the book's "Making type objects more
      like types: constructors" has the breed construct its monsters. Here
      ``make_ghost(breed)`` lives in p13_component.py instead, because a ghost
      is assembled from components we haven't met yet.
    * "Can the type change?": it could (just assign another breed), but
      it doesn't in this game.
    * "What kind of inheritance is supported?": single, copy-down.
"""
import json

from patterns.p10_bytecode import assemble


class Breed:
    """A kind of ghost. Instances are created from data, not by subclassing."""

    FIELDS = ("display_name", "nickname", "colour", "speed", "tunnel_speed",
              "frightened_speed", "eaten_speed", "elroy_dots", "elroy_speed",
              "release_delay", "starts_outside", "house_x", "scatter_corner",
              "chase_program")

    def __init__(self, key: str, data: dict, parent: "Breed" = None):
        self.key = key
        self.parent = parent
        self.abstract = bool(data.get("abstract", False))
        for field in self.FIELDS:
            if field in data:
                value = data[field]
            elif parent is not None:
                value = getattr(parent, field)          # copy-down from the parent
            else:
                raise ValueError(f"breed '{key}' has no '{field}' and no parent")
            setattr(self, field, value)
        self.colour = tuple(self.colour)
        self.scatter_corner = tuple(self.scatter_corner)
        # Behaviour as data: compile the targeting rule once, at load time.
        self.chase_code = assemble(self.chase_program)

    def __repr__(self) -> str:
        return f"<Breed {self.key}>"


class BreedRegistry:
    """Loads breeds from JSON and resolves their parents (in any order)."""

    def __init__(self, data: dict):
        self.breeds = {}
        raw = {k: v for k, v in data.items() if not k.startswith("_")}
        self._order = list(raw)            # file order
        for key in raw:
            self._resolve(key, raw, set())

    @classmethod
    def from_file(cls, path: str) -> "BreedRegistry":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def _resolve(self, key: str, raw: dict, visiting: set) -> Breed:
        if key in self.breeds:
            return self.breeds[key]
        if key not in raw:
            raise ValueError(f"unknown parent breed '{key}'")
        if key in visiting:
            raise ValueError(f"breed inheritance cycle at '{key}'")
        visiting.add(key)
        parent_key = raw[key].get("parent")
        parent = self._resolve(parent_key, raw, visiting) if parent_key else None
        breed = Breed(key, raw[key], parent)
        self.breeds[key] = breed
        return breed

    def __getitem__(self, key: str) -> Breed:
        return self.breeds[key]

    def playable(self):
        """Concrete breeds in file order (abstract ones are only parents)."""
        return [self.breeds[k] for k in self._order if not self.breeds[k].abstract]
