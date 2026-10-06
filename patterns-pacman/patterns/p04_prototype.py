"""
Pattern 4 of 19 - PROTOTYPE
===========================
Book: "Design Patterns Revisited > Prototype"
      https://gameprogrammingpatterns.com/prototype.html

  "Specify the kinds of objects to create using a prototypical instance, and
   create new objects by copying this prototype."

THE PROBLEM
    A bonus fruit appears twice per level, and which fruit depends on the
    level (cherry, strawberry, orange...). A separate spawner class for every
    kind of fruit (CherrySpawner, StrawberrySpawner, ...) would mirror the
    whole fruit class hierarchy for no good reason.

THE PATTERN (book section "The Prototype Design Pattern")
    * Objects that can be copied implement ``clone()``.
    * A single ``Spawner`` class holds *an instance* (the prototype) and
      produces new objects by cloning it. One Spawner class, any kind of
      object, and even the prototype's *state* is copied (a "fast" fruit
      prototype yields fast fruit).

WHERE IT IS USED IN THE GAME
    The fruit classes in p11_subclass_sandbox.py derive from ``Prototype``.
    At the start of each level app/game.py builds
    ``Spawner(<the level's fruit prototype>)`` and calls ``spawn()`` when
    70 and 170 dots have been eaten.

ALTERNATIVES THE BOOK DISCUSSES
    * "Spawn functions": pass a function instead of a prototype:
          Spawner(make_cherry)
    * "Templates": C++ templates parameterised by the class.
    * "First-class types": in Python *classes are objects*, so
          Spawner(Cherry)  ...  self.kind()
      would also work and is often the most Pythonic answer. The book makes
      exactly this point. ``FunctionSpawner`` below shows the spawn-function
      flavour so you can compare.

PROTOTYPES FOR DATA MODELING (book section of the same name)
    The idea also works for *data*: a data record can name another record as
    its prototype and inherit any field it doesn't define. The ghost
    definitions in data/breeds.json do exactly that with a "parent" key, and
    p12_type_object.py resolves it.
"""
import copy


class Prototype:
    """Mixin: gives an object a ``clone()`` method.

    ``copy.copy`` makes a *shallow* copy: the clone gets its own attribute
    dictionary but shares the objects the attributes point to. Subclasses that
    own mutable state of their own (lists, dicts) should override
    ``_after_clone`` to copy that state. In C++ you would write this by hand
    for every class, which is the pattern's biggest cost.
    """

    def clone(self):
        twin = copy.copy(self)
        twin._after_clone()
        return twin

    def _after_clone(self) -> None:
        pass


class Spawner:
    """Creates objects by cloning the prototype it was given."""

    def __init__(self, prototype: Prototype):
        self.prototype = prototype
        self.spawned = 0

    def spawn(self):
        self.spawned += 1
        return self.prototype.clone()


class FunctionSpawner:
    """The book's "Spawn functions" alternative, for comparison."""

    def __init__(self, spawn_function):
        self.spawn_function = spawn_function
        self.spawned = 0

    def spawn(self):
        self.spawned += 1
        return self.spawn_function()
