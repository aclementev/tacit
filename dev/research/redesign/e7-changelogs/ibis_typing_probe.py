import ibis
from typing import reveal_type
import ibis.expr.types as ir

t = ibis.table({"x": "float64", "y": "float64", "s": "string"})

r1 = t.x / t.y            # Issue 1: Column has no __truediv__?
r2 = t.x.sum()            # Issue 1b
r3 = t.x < 5.0            # comparison with python scalar
r4 = t.x >= 0
r5 = t.mutate(a=1)        # mutate kwarg python literal
r6 = t.mutate(a=1.5, b="x", c=True)
names = set(t.schema().names)   # Schema.names Attribute?
types = list(t.schema().types)
reveal_type(t.x)
reveal_type(t.schema().names)
reveal_type(t.mutate)
