"""Typed join scope (E8's design, ported to DataFrame[S]).

    j = tacit.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    OrderCountry.build(order_id=j.left.order_id, country=j.right.country)

`j.left` / `j.right` are the column namespaces (like `df.c`) of each side, bound to
the joined relation. Both sides are prefixed internally, so name collisions cannot
happen: the output schema names every column.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

import ibis.expr.types as ir

from ._column import Column
from ._df import DataFrame, Schema, _plain
from ._errors import Issue, ValidationError

How = Literal["inner", "left", "right", "outer", "semi", "anti"]


class Join[L: Schema, R: Schema]:
    """Result of `tacit.join`: typed column views of both sides over the joined relation."""

    __slots__ = ("left", "right", "table")

    def __init__(self, left: L, right: R, table: ir.Table) -> None:
        self.left = left
        self.right = right
        self.table = table  # raw joined ibis table (prefixed column names)

    def __repr__(self) -> str:
        return f"Join[{type(self.left).__name__}, {type(self.right).__name__}]"


def _prefixed(df: DataFrame[Any], prefix: str) -> ir.Table:
    t = _plain(df)
    return t.select(**{prefix + f.name: t[f.name] for f in df._schema.__tacit_fields__.values()})


def _key(df: DataFrame[Any], col: Any, side: str) -> str:
    if col.op().relations != {df.op()}:
        raise ValidationError(df._schema.__name__, "join", [Issue("relation", detail=f"{side} key {col.get_name()!r} is not a column of the {side} frame")])
    return col.get_name()


def join[L: Schema, R: Schema](
    left: DataFrame[L],
    right: DataFrame[R],
    on: Callable[[L, R], Column[bool | None]] | Sequence[tuple[Column[Any], Column[Any]]],
    *,
    how: How = "inner",
) -> Join[L, R]:
    """Join two frames. `on` is a predicate over the two typed views, or (left_col, right_col) pairs.

    With how="left"/"outer", right-side columns become nullable at runtime; the static
    types of `j.right` cannot express that (known limit).
    """
    lt, rt = _prefixed(left, "l__"), _prefixed(right, "r__")
    ls, rs = left._schema, right._schema
    if callable(on):
        preds: list[Any] = [on(ls._bind(lt, "l__"), rs._bind(rt, "r__"))]  # type: ignore[arg-type]
    else:
        preds = [lt["l__" + _key(left, a, "left")] == rt["r__" + _key(right, b, "right")] for a, b in on]
    joined = lt.join(rt, preds, how=how)
    return Join(ls._bind(joined, "l__"), rs._bind(joined, "r__"), joined)  # type: ignore[arg-type]
