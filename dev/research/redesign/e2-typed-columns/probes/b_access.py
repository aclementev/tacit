"""B. Wrapper vs subclass: what does each checker say about a typo in each design?"""

from typing import TYPE_CHECKING, Any, reveal_type

import ibis
import ibis.expr.types as ir


# B1: subclass ir.Table and declare typed columns (today's DataFrame[S] shape)
class IrisSub(ir.Table):
    sepal_length: ir.FloatingColumn


# B3: wrapper with typed __getattr__ delegation to the ibis table
class IrisGetattrAny:
    sepal_length: ir.FloatingColumn

    def __init__(self, t: ir.Table) -> None:
        self._t = t

    def __getattr__(self, name: str) -> Any:
        return getattr(self._t, name)


# B3b: delegation hidden from checkers (runtime convenience only)
class IrisGetattrHidden:
    sepal_length: ir.FloatingColumn

    def __init__(self, t: ir.Table) -> None:
        self._t = t

    if not TYPE_CHECKING:

        def __getattr__(self, name):
            return getattr(self._t, name)


def probe(sub: IrisSub, g: IrisGetattrAny, h: IrisGetattrHidden) -> None:
    reveal_type(sub.sepal_length)
    reveal_type(sub.sepal_lenght)  # typo
    reveal_type(sub.mutate(x=sub.sepal_length * 2))
    reveal_type(g.sepal_length)
    reveal_type(g.sepal_lenght)  # typo
    reveal_type(g.mutate)  # ibis API: Any
    reveal_type(h.sepal_length)
    reveal_type(h.sepal_lenght)  # typo
    reveal_type(h.mutate)  # ibis API: not visible statically


if __name__ == "__main__":
    t = ibis.memtable({"sepal_length": [1.0]})
    g = IrisGetattrAny(t)
    h = IrisGetattrHidden(t)
    print(type(g.sepal_length).__name__, type(h.mutate(x=1)).__name__)
