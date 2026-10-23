# ruff: noqa: B015, B018
"""Quick static probe of the T design."""
from typing import reveal_type

import ibis
import ibis.expr.types as ir

import tacit_thin as tc
from tacit_thin import Column


class Orders(tc.Frame):
    order_id: Column[int]
    status: Column[str]
    amount: Column[float]


class Customers(tc.Frame):
    customer_id: Column[int]
    name: Column[str]


def forgot_cast(o: Orders) -> Orders:
    return o.mutate(x=o.amount * 2)  # E


def raw_table(t: ir.Table) -> Orders:
    return t  # E


def wrong_frame(c: Customers) -> Orders:
    return c  # E


def api(o: Orders, c: Customers, t: ir.Table) -> None:
    reveal_type(o.amount)
    o.amout  # E
    reveal_type(o.mutate(x=o.amount * 2))
    reveal_type(o.select(o.amount, o.status))
    reveal_type(o.group_by(o.status).agg(total=o.amount.sum()))
    reveal_type(o.group_by("status").aggregate(o.amount.sum().name("t")))
    reveal_type(o.join(c, o.order_id == c.customer_id))
    reveal_type(o.join(t, [o.order_id == t.order_id]))
    reveal_type(o.filter(o.amount > 1))
    reveal_type(o.order_by(o.amount.desc()))
    reveal_type(o.mutate(rn=tc.row_number().over(group_by=o.status, order_by=o.amount.desc())))
    reveal_type(o.columns)
    reveal_type(o.schema())
    reveal_type(o["status"])
    reveal_type(o.to_pandas())
    reveal_type(o.count())
    reveal_type(o.head(3))
    reveal_type(o.cast({"amount": "float32"}))
    ibis.union(o, o)
    tc.as_table(o)
    x: ir.Table = o
    y: tc.Table = o.mutate(z=1.0)
    o.mutate(z=1.0).amount  # E typo after ibis op? (mirror has no __getattr__)
    o.mutate(z=1.0)["amount"]
    o.ibis  # E
