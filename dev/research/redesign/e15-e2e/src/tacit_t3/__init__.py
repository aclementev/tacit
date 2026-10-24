"""tacit T3 (E15): E13's T2 (`DataFrame[S]` is an ibis Table; typed `df.c`) + E11's derived
column facade + E10's hybrid validation + E8's typed join, `aggregate(by=)` and `@step`.

    import tacit_t3 as tacit
    from tacit_t3 import Column, DataFrame, field

    class Orders(tacit.Schema):
        order_id: Column[int] = field(unique=True)
        amount: Column[float] = field(ge=0)
        discount: Column[float | None]

    orders = Orders.parse(con.read_csv("orders.csv"))   # DataFrame[Orders], an ir.Table
    orders.c.amount                                     # Column[float]
"""

from ._column import Column, Scalar, as_column, as_ibis, cases, lit, row_number
from ._df import DataFrame, Into, Schema, as_table
from ._errors import Issue, ValidationError
from ._fields import field
from ._ibis_api import Table, TableAPI
from ._join import Join, join
from ._step import step

__all__ = [
    "Column", "DataFrame", "Into", "Issue", "Join", "Scalar", "Schema", "Table", "TableAPI",
    "ValidationError", "as_column", "as_ibis", "as_table", "cases", "field", "join", "lit",
    "row_number", "step",
]
