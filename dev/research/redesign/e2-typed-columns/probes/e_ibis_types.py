"""E. What does ibis 12 type correctly on its own (no tacit)?

Columns are passed as already-typed parameters to isolate ibis' own annotations.
"""

from typing import reveal_type

import ibis
import ibis.expr.types as ir


def probe(
    t: ir.Table,
    x: ir.FloatingColumn,
    y: ir.FloatingColumn,
    s: ir.StringColumn,
    n: ir.IntegerColumn,
) -> None:
    # --- base Table.__getattr__ / __getitem__ ---
    reveal_type(t.x)  # ir.Column (base)
    reveal_type(t["x"])
    reveal_type(t.not_a_column)  # typo: does anything complain? (runtime: AttributeError)

    # --- arithmetic / comparisons ---
    reveal_type(x / y)  # NumericValue (loses Column-ness and Floating-ness)
    reveal_type(x * 2)
    reveal_type(1 - x)  # __rsub__
    reveal_type(x > 5)  # Value.__gt__(other: Value) -> 5 is not a Value!
    reveal_type(x > y)
    reveal_type(x == 1.0)  # Value.__eq__(other: Value)
    reveal_type(s == "a")
    reveal_type(s <= "1998-09-02")
    reveal_type((x > y) & (x < y))
    # --- methods ---
    reveal_type(x.mean())
    reveal_type(x.sum())
    reveal_type(n.sum())
    reveal_type(x.count())
    reveal_type(s.upper())
    reveal_type(s.length())
    reveal_type((x / y).mean())  # NumericValue has no .mean (only NumericColumn)
    reveal_type(x.isnull())
    reveal_type(x.cast("int64"))
    reveal_type(x.round(2))

    # --- wrong-type ops: does any checker flag them? ---
    _ = s / x  # string / float
    _ = s.mean()  # no .mean on strings
    _ = x.upper()  # no .upper on floats

    # --- table methods ---
    reveal_type(t.mutate(z=x / y))
    reveal_type(t.mutate(one=1))  # Python literal kwarg
    reveal_type(t.filter(x > y))
    reveal_type(t.filter(s == "a"))
    reveal_type(t.select("x", "s"))
    g = t.group_by("s")
    reveal_type(g)
    reveal_type(g.agg(m=x.mean()))
    reveal_type(t.join(t, "s"))
    reveal_type(ibis.cases((x > y, "a"), else_="b"))
    reveal_type(ibis._.x)
    reveal_type(ibis._.x > 1)
    reveal_type(t.schema())


t = ibis.memtable({"x": [1.0, 2.0], "y": [3.0, 4.0], "s": ["a", "b"], "n": [1, 2]})
try:
    probe(t, t.x, t.y, t.s, t.n)  # type: ignore[arg-type]
except AttributeError as e:
    print("runtime:", e)
print(type(t.x / t.y).__name__, type(t.x > 5).__name__, type(t.s == "a").__name__)
print(type((t.x / t.y).mean()).__name__, type(t.x.mean()).__name__)
