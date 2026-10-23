# ruff: noqa: B018
"""P6: refs with ownerless helpers and ibis top-level functions (expected OK at runtime)."""
from typing import reveal_type

import ibis

import tacit_r as tr
from tacit_r import DataFrame
from gen_schemas import Orders


def f(o: DataFrame[Orders]) -> None:
    Orders.amount + tr.lit(1.0)  # L1 helper scalar (bound type)
    tr.cases((Orders.amount > 0, 1), else_=0)  # L2 tacit cases with a ref condition
    ibis.coalesce(Orders.discount, 0.0)  # L3 ibis function with a ref
    ibis.greatest(Orders.amount, 0.0)  # L4
    o.mutate(r=ibis.row_number().over(order_by=Orders.order_ts))  # L5 ibis window with ref keys
    o.filter(Orders.status.isin(["a", "b"]))  # L6
    reveal_type(Orders.order_ts.year())  # R: Ref[Orders, int]
    o.mutate(s=Orders.amount.sum().over(group_by=Orders.status))  # L8 windowed reduction
