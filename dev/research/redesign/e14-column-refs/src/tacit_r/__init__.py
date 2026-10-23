"""E14: T2 (`DataFrame[S]` + `df.c`) plus owner-typed unbound class refs.

    class Orders(tr.Schema):
        amount: Column[float]

    Orders.amount                       # Ref[Orders, float]   (runtime: ibis `_["amount"]`)
    orders.c.amount                     # Column[float]        (bound to `orders`)
    orders.filter(Orders.amount > 0)    # owner-checked: a Customers ref is a static error
"""

from tacit_thin import Column, Scalar, cases, field, lit, row_number
from tacit_thin._column import Ref, RefScalar

from ._df import DataFrame, Into, Schema

__all__ = ["Column", "DataFrame", "Into", "Ref", "RefScalar", "Scalar", "Schema", "cases", "field", "lit", "row_number"]
