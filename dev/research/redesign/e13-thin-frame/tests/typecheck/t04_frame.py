# ruff: noqa: B015, B018
"""Frame (E13: an ir.Table subclass): Self-returning overrides, boundaries, nominal subtyping."""

from typing import reveal_type

import ibis.expr.types as ir
from _schemas import Customers, NetOrders, Orders

import tacit_thin as tc


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
    reveal_type(o.head(3))  # R: Orders
    # @feature no escape hatch needed: the frame is the table
    reveal_type(o.mutate(x=o.amount * 2))  # R: Table
    reveal_type(tc.as_table(o))  # R: Table
    o.ibis  # E: no .ibis member (removed)
    # @feature boundaries: parse / conform return the frame
    reveal_type(Orders.parse(t))  # R: Orders
    reveal_type(Orders.conform(t))  # R: Orders
    reveal_type(Orders.conform(o))  # R: Orders
    reveal_type(Orders.conform(o.mutate(x=o.amount * 2)))  # R: Orders


def subtyping(o: Orders, n: NetOrders, c: Customers, t: ir.Table) -> None:
    # @feature nominal subtyping: subclass has at least these columns
    takes_orders(n)  # ok: NetOrders is an Orders
    takes_orders(c)  # E: Customers is not Orders
    takes_orders(t)  # E: raw ibis table is not a frame
    x: NetOrders = o  # E: Orders is not NetOrders
    takes_orders(1)  # E: int is not a frame
    # @feature forgot to cast/construct: ibis results are not frames
    takes_orders(o.mutate(x=o.amount * 2))  # E: ibis op result is not Orders
    takes_orders(o.select(o.order_id, o.amount))  # E: select result is not Orders
    takes_orders(o.group_by(o.status).agg(n=o.order_id.count()))  # E: aggregate result is not Orders
    takes_orders(o.join(c, o.customer_id == c.customer_id))  # E: join result is not Orders
    takes_orders(o.cast({"amount": "float32"}))  # E: ibis cast result is not Orders
