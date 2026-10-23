"""Typed join scope.

    j = tc.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    OrderWithCountry(order_id=j.left.order_id, country=j.right.country, ...)

`j.left` is an `Orders` view and `j.right` a `Customers` view whose columns
reference the joined relation. Both sides are prefixed internally, so name
collisions cannot happen: the output constructor names every column.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

import ibis.expr.types as ir

from ._column import Column
from ._frame import Frame, as_table

How = Literal["inner", "left", "right", "outer", "semi", "anti"]


class Join[L: Frame, R: Frame]:
    """Result of `tc.join`: typed views of both sides over the joined relation."""

    __slots__ = ("left", "right", "table")

    def __init__(self, left: L, right: R, table: ir.Table) -> None:
        self.left = left
        self.right = right
        self.table = table  # raw joined ibis table (prefixed column names)


def _prefixed(frame: Frame, prefix: str) -> tuple[ir.Table, dict[str, str]]:
    t = as_table(frame)
    names = {spec.attr: f"{prefix}{spec.attr}" for spec in type(frame).__tacit_fields__.values()}
    return t.select(**{names[s.attr]: t[s.name] for s in type(frame).__tacit_fields__.values()}), names


def join[L: Frame, R: Frame](
    left: L,
    right: R,
    on: Callable[[L, R], Column[bool]] | Sequence[tuple[Column[Any], Column[Any]]],
    *,
    how: How = "inner",
) -> Join[L, R]:
    """Join two frames. `on` is a predicate over typed views, or (left_col, right_col) pairs.

    Note: with how="left"/"outer", right-side columns become nullable at runtime;
    the static types of `j.right` cannot express that (see report, open problems).
    """
    lt, lnames = _prefixed(left, "l__")
    rt, rnames = _prefixed(right, "r__")
    lview = type(left)._wrap(lt, lnames)
    rview = type(right)._wrap(rt, rnames)
    preds: list[ir.BooleanValue]
    if callable(on):
        preds = [on(lview, rview)]  # type: ignore[list-item]
    else:
        preds = []
        for lc, rc in on:
            preds.append(lt[lnames[_attr_of(left, lc)]] == rt[rnames[_attr_of(right, rc)]])
    joined = lt.join(rt, preds, how=how)
    return Join(type(left)._wrap(joined, lnames), type(right)._wrap(joined, rnames), joined)


def _attr_of(frame: Frame, col: Column[Any]) -> str:
    """Map a column handle taken from `frame` back to its attribute name (and check it is bound to it)."""
    expr: Any = col
    for spec in type(frame).__tacit_fields__.values():
        if expr.op() == as_table(frame)[spec.name].op():
            return spec.attr
    raise ValueError(f"join key {expr.get_name()!r} is not a column of this {type(frame).__name__} frame")
