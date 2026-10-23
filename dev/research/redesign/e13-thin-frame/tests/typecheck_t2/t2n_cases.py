# ruff: noqa: B015, B018
"""T2: DataFrame[S] (ir.Table subclass, clean static base) + typed `df.c` column namespace."""

from datetime import datetime
from typing import Any, reveal_type

import ibis.expr.types as ir
from ibis import _

import tacit_t2n as tc2
import tacit_thin as tc
from tacit_t2n import Column, DataFrame


class Orders(tc2.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str]
    amount: Column[float]
    count: Column[int]  # allowed: columns live in the .c namespace, not on the table


class Customers(tc2.Schema):
    customer_id: Column[int]
    country: Column[str]


class Net(tc2.Schema):
    net_amount: Column[float]


class NetOrders(Orders, Net):
    pass


class Stats(tc2.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class HasEventTs(tc2.Schema):
    event_ts: Column[datetime]


class Clicks(HasEventTs):
    url: Column[str]


def takes_orders(df: DataFrame[Orders]) -> None: ...


def access(o: DataFrame[Orders], c: DataFrame[Customers], t: ir.Table) -> None:
    # @feature typed namespace access, typos
    reveal_type(o.c.amount)  # R: Column[float]
    reveal_type(o.c.count)  # R: Column[int]
    reveal_type(o.count())  # R: IntegerScalar
    reveal_type(Orders.amount)  # R: Column[float]
    o.c.amout  # E: typo in namespace
    o.amount  # E: columns are not table attributes in T2
    o.c.amount.upper()  # E: wrong method
    reveal_type(o.c.amount * 2)  # R: Column[float]
    # @feature schema-preserving methods keep DataFrame[S]
    reveal_type(o.filter(o.c.amount > 0))  # R: DataFrame[Orders]
    reveal_type(o.order_by(o.c.order_ts.desc()).limit(5))  # R: DataFrame[Orders]
    reveal_type(o.distinct(on=o.c.order_id))  # R: DataFrame[Orders]
    # @feature ibis API directly; results are plain tables
    reveal_type(o.mutate(x=o.c.amount * 2))  # R: Table
    reveal_type(o.group_by(o.c.status).agg(total=o.c.amount.sum()))  # R: Table
    reveal_type(o.join(c, o.c.customer_id == c.c.customer_id))  # R: Table
    reveal_type(o.select(o.c.order_id, "status"))  # R: Table
    reveal_type(Orders.conform(o.mutate(amount=_.amount * 2)))  # R: DataFrame[Orders]
    # @feature wrong frame / forgot cast / subtyping
    takes_orders(c)  # E: Customers frame
    takes_orders(o.mutate(x=o.c.amount * 2))  # E: forgot to conform
    takes_orders(o.group_by(o.c.status).agg(n=o.c.order_id.count()))  # E: forgot to conform
    takes_orders(t)  # E: raw ibis table
    takes_orders(o)
    x: DataFrame[NetOrders] = o  # E: Orders is not NetOrders


def construct(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    # @feature build(): checked projection and implicit GROUP BY
    reveal_type(Net.build(net_amount=o.c.amount - 1))  # R: DataFrame[Net]
    Net.build(net_amount=o.c.status)  # E: str into float
    Net.build()  # E: missing column
    Net.build(net_amount=o.c.amount, bogus=o.c.amount)  # E: extra column
    reveal_type(Stats.build(status=o.c.status, n=o.c.order_id.count(), total=o.c.amount.sum()))  # R: DataFrame[Stats]
    Stats.build(status=o.c.status, n=o.c.amount.sum(), total=o.c.amount.sum())  # E: float into int
    # @feature extend: Out must subclass the base schema and every delta
    reveal_type(NetOrders.extend(o, Net.build(net_amount=o.c.amount)))  # R: DataFrame[NetOrders]
    NetOrders.extend(c, Net.build(net_amount=o.c.amount))  # E: Customers is not a base of NetOrders
    Stats.extend(o, Net.build(net_amount=o.c.amount))  # E: Stats does not subclass Orders


def dedupe[S: tc2.Schema](df: DataFrame[S], key: Column[Any]) -> DataFrame[S]:
    return df.distinct(on=key)


def recent[S: HasEventTs](df: DataFrame[S], since: datetime) -> DataFrame[S]:
    reveal_type(df.c.event_ts)  # R: Column[datetime]
    df.c.event_tss  # E: typo in generic body
    return df.filter(df.c.event_ts >= since)


def generic(o: DataFrame[Orders], n: DataFrame[NetOrders], k: DataFrame[Clicks]) -> None:
    # @feature generic steps over S
    reveal_type(dedupe(o, o.c.order_id))  # R: DataFrame[Orders]
    reveal_type(dedupe(n, n.c.order_id))  # R: DataFrame[NetOrders]
    reveal_type(recent(k, datetime(2024, 1, 1)))  # R: DataFrame[Clicks]
    recent(o, datetime(2024, 1, 1))  # E: Orders has no event_ts
    takes_orders(n)  # ok: covariant, NetOrders is an Orders
    tc.as_table(o)
    # @feature typed namespace survives build() (inference of S through Callable[P, S])
    Net.build(net_amount=o.c.amount).c.net_amont  # E: typo after build
    reveal_type(Net.build(net_amount=o.c.amount).c.net_amount)  # R: Column[float]
    # @feature frame accepted by ibis functions typed ir.Table
    xt: ir.Table = o  # ok at runtime
