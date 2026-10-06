"""The 19 patterns of Robert Nystrom's *Game Programming Patterns*, one module each.

Read them in numeric order, which is the order of the book's table of contents
(https://gameprogrammingpatterns.com/contents.html):

  Design Patterns Revisited  p01 Command, p02 Flyweight, p03 Observer,
                             p04 Prototype, p05 Singleton, p06 State
  Sequencing Patterns        p07 Double Buffer, p08 Game Loop, p09 Update Method
  Behavioral Patterns        p10 Bytecode, p11 Subclass Sandbox, p12 Type Object
  Decoupling Patterns        p13 Component, p14 Event Queue, p15 Service Locator
  Optimization Patterns      p16 Data Locality, p17 Dirty Flag, p18 Object Pool,
                             p19 Spatial Partition

Rule kept throughout: a module only imports from *earlier* modules (and from
``support``), so each one can be understood with what you have read so far.
tests/test_patterns.py checks this rule.
"""
