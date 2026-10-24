# Probe: does dataclass_transform honor an OVERLOADED, self-typed __set__? (run against layers/l1 with the
# per-family __set__ overloads restored). Result: no on pyright and mypy ("Unsupported __set__"); ty/pyrefly
# accept everything (Unknown base). Hence L1 uses one loose __set__ and L2 a phantom _Fam[T] marker.
from datetime import datetime
from typing import reveal_type
import tacit_t2 as tc2
from tacit_t2 import Column, DataFrame

class Orders(tc2.Schema):
    order_id: Column[int]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]
    ts: Column[datetime]

class Stats(tc2.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]

def f(o: DataFrame[Orders]) -> None:
    reveal_type(o.c.amount)
    reveal_type(o.c.discount)
    reveal_type(o.c.order_id)
    reveal_type(o.c.ts)
    reveal_type(Orders.amount)
    o.c.amout
    o.c.amount.upper()
    reveal_type(Stats.build(status=o.c.status, n=o.c.order_id.count(), total=o.c.amount.sum()))
    Stats.build(status=o.c.amount, n=o.c.order_id.count(), total=o.c.amount.sum())  # E
    Stats.build(status=o.c.status, n=o.c.order_id.count())  # E
    Stats.build(status="x", n=1, total=2.0)
