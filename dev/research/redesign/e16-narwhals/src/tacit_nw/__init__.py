"""E16 prototype: tacit's T2 design on narwhals.

    class Orders(tc.Schema):
        amount: Column[float] = tc.field(ge=0)
    orders = Orders.parse(native)        # polars / duckdb / pyspark / sqlframe / ibis frame
    orders.c.amount                      # Column[float]  (runtime: nw.col("amount"))
    Net.build(orders, net=orders.c.amount - 1)
"""

from ._column import Column, expr, lit, when
from ._frame import DataFrame, Into, Schema, field
from ._native import NativeFrame, PolarsFrame, PolarsLazyFrame, SparkFrame, names, step, tag
from ._validate import Issue, ValidationError

__all__ = ["Column", "DataFrame", "Into", "Issue", "NativeFrame", "PolarsFrame", "PolarsLazyFrame", "SparkFrame", "Schema", "ValidationError", "expr", "field", "lit", "names", "step", "tag", "when"]
