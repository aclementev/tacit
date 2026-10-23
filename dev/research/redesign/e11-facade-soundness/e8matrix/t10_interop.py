# ruff: noqa: B015, B018
"""Interop with raw ibis: typed columns are ibis values; escape hatches both ways."""

from typing import reveal_type

import ibis
import ibis.expr.types as ir
from _schemas import Orders, Proj2

import tacit_next as tc


def interop(o: Orders) -> None:
    # @feature typed columns accepted by ibis APIs
    o.ibis.select(o.amount, o.status)
    o.ibis.mutate(x=o.amount * 2)
    o.ibis.order_by(ibis.desc(o.amount))
    o.ibis.order_by(o.amount.desc())
    o.ibis.filter(o.amount > 0)
    o.ibis.filter(tc.as_ibis(o.amount > 0))
    o.ibis.order_by(tc.as_ibis(o.amount).desc())
    o.ibis.group_by(o.status).aggregate(total=o.amount.sum())
    tc.row_number().over(group_by=o.status, order_by=o.order_ts.desc())
    # @feature as_ibis / as_column / cases / lit
    reveal_type(tc.as_ibis(o.status))  # R: StringColumn
    reveal_type(tc.as_ibis(o.amount))  # R: FloatingColumn
    reveal_type(tc.as_column(tc.as_ibis(o.status).re_extract("a", 0)))  # R: Column[str]
    reveal_type(tc.cases((o.amount < 1, "small"), (o.amount < 10, "mid"), else_="big"))  # R: Column[str]
    reveal_type(tc.lit(1.5))  # R: Scalar[float]
    Proj2(label=tc.cases((o.amount < 1, "small"), else_="big"), amount=o.amount)  # ok
    Proj2(label=tc.cases((o.amount < 1, 1), else_=2), amount=o.amount)  # E: int cases into str
    # @feature raw ibis values are not typed columns
    raw: ir.FloatingColumn = tc.as_ibis(o.amount)
    Proj2(label=o.status, amount=raw)  # E: untyped ibis expr needs tc.as_column
    Proj2(label=o.status, amount=tc.as_column(raw))  # ok
