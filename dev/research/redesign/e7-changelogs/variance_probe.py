"""PEP 695 inferred variance: does each checker infer covariance for a read-only generic?"""
from typing import reveal_type


class Base: ...
class Child(Base): ...


class Box[T]:                      # T never written -> should infer covariant
    def __init__(self, x: T) -> None:
        self._x = x
    def get(self) -> T:
        return self._x


class MBox[T]:                     # T written -> invariant
    x: T
    def __init__(self, x: T) -> None:
        self.x = x


def f(b: Box[Base]) -> None: ...
def g(b: MBox[Base]) -> None: ...

f(Box(Child()))                    # OK only with inferred covariance
g(MBox(Child()))                   # constructor infers MBox[Base] -> OK either way
cb: Box[Child] = Box(Child())
f(cb)                              # covariance check
mb: MBox[Child] = MBox(Child())
g(mb)                              # ERROR expected: invariant
