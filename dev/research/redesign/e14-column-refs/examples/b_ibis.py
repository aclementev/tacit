# ruff: noqa: B015, B018
"""Injected bugs, spelling 4 (plain ibis `_`)."""

import ibis.expr.types as ir
from ibis import _


def bugs(orders: ir.Table, customers: ir.Table) -> None:
    # @feature bug matrix
    orders.filter(_.statuz != "cancelled")  # E: B1 typo
    orders.filter(_.status > 5)  # E: B2 str compared with int
    orders.filter(customers.country == "DE")  # E: B3 other frame's column
    orders.mutate(net_amount=_.amount - _.discount)  # E: B4 nullable into non-null
    x: ir.Table = orders.mutate(net_amount=_.amount)  # E: B5 forgot to conform (no schema to forget)
    orders.group_by(_.status).agg(t=_.net_amount)  # E: B6 agg of a non-reduced column
    orders.join(customers, _.customer_id == customers.country)  # E: B7 int key vs str key


def bad_generic(df: ir.Table) -> ir.Table:
    return df.filter(_.status == "x")  # E: B8 column outside the generic bound
