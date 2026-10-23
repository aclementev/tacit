# ruff: noqa: B015, B018
"""Frame wrapper: Self-returning methods, escape hatch, nominal subtyping, boundaries."""

from typing import reveal_type

import ibis.expr.types as ir
from _schemas import Customers, NetOrders, Orders


def takes_orders(o: Orders) -> Orders:
    return o


def methods(o: Orders, t: ir.Table) -> None:
    # @feature schema-preserving methods return Self
    reveal_type(o.filter(o.amount > 0))  # R: Orders
    reveal_type(o.order_by(o.order_ts.desc()))  # R: Orders
    reveal_type(o.limit(10))  # R: Orders
    reveal_type(o.distinct(on=o.order_id))  # R: Orders
    reveal_type(o.cache())  # R: Orders
    reveal_type(o.filter(Orders.amount > 0))  # R: Orders
    o.filter(o.amount)  # E: non-boolean predicate
    o.filter("amount > 0")  # E: string predicate
    o.mutate(x=1)  # E: no ibis passthrough on the frame
    # @feature escape hatch .ibis
    reveal_type(o.ibis)  # R: Table
    # @feature boundaries: parse / cast return the frame
    reveal_type(Orders.parse(t))  # R: Orders
    reveal_type(Orders.cast(t))  # R: Orders
    reveal_type(Orders.cast(o))  # R: Orders


def subtyping(o: Orders, n: NetOrders, c: Customers, t: ir.Table) -> None:
    # @feature nominal subtyping: subclass has at least these columns
    takes_orders(n)  # ok: NetOrders is an Orders
    takes_orders(c)  # E: Customers is not Orders
    takes_orders(t)  # E: raw ibis table is not a frame
    x: NetOrders = o  # E: Orders is not NetOrders
    takes_orders(1)  # E: int is not a frame
