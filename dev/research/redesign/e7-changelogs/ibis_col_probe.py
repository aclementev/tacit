import ibis
from typing import reveal_type
t = ibis.table({"x": "float64", "y": "float64"})
a = t.x
reveal_type(a)
reveal_type(a / t.y)
reveal_type(t.x.sum())
