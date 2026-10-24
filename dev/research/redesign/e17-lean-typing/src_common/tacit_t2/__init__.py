"""T2 variant (E13): tacit 0.2's `DataFrame[S]` spelling + clean static Table mirror + typed `df.c` namespace.

    class Orders(tc2.Schema):
        order_id: Column[int]
        amount: Column[float] = tc.field(ge=0)

    orders: tc2.DataFrame[Orders] = Orders.parse(raw)   # an ir.Table subclass at runtime
    orders.c.amount                                     # Column[float]
    orders.mutate(x=orders.c.amount * 2)                # full ibis API -> tc.Table
    Net.build(net=orders.c.amount - 1)                  # -> DataFrame[Net]
"""

from tacit_thin import Column, Scalar, cases, field, lit, row_number
from tacit_thin._column import AnyCol, TsCol

from ._df import DataFrame, Into, Join, Schema, join

__all__ = ["AnyCol", "TsCol", "Column", "DataFrame", "Into", "Join", "Scalar", "Schema", "cases", "field", "join", "lit", "row_number"]
