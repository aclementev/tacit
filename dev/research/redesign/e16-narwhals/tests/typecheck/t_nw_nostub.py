# ruff: noqa: B015, B018
"""T2 on narwhals: DataFrame[S] (nw.LazyFrame subclass + generated return-type rewrite) + typed df.c.

Markers: `# E` = an error is expected on this line; `# R: X` = reveal_type must contain X;
no marker = must be clean. Scored by tests/score.py.
"""

from datetime import datetime
from typing import Any, reveal_type

import narwhals.stable.v2 as nw
import polars as pl

import tacit_nwn as tc
from tacit_nwn import Column, DataFrame


class Orders(tc.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]
    count: Column[int]  # allowed: columns live in .c


class Customers(tc.Schema):
    customer_id: Column[int]
    country: Column[str]


class Net(tc.Schema):
    net_amount: Column[float]


class NetOrders(Orders, Net):
    pass


class Stats(tc.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class HasEventTs(tc.Schema):
    event_ts: Column[datetime]


class Clicks(HasEventTs):
    url: Column[str]


def takes_orders(df: DataFrame[Orders]) -> None: ...


def access(o: DataFrame[Orders], c: DataFrame[Customers], plain: nw.LazyFrame[Any], raw: pl.LazyFrame) -> None:
    # typed namespace, typos
    reveal_type(o.c.amount)  # R: Column[float]
    reveal_type(o.c.discount)  # R: Column[float | None]
    reveal_type(Orders.amount)  # R: str
    o.c.amout  # E typo in namespace
    o.amount  # E columns are not frame attributes
    o.c.amount.str.to_uppercase()  # E str method on a float column
    o.c.status.dt.year()  # E dt method on a str column
    o.c.amount.fill_nul(0)  # E method typo
    reveal_type(o.c.amount * 2)  # R: Column[float]
    reveal_type(o.c.discount * 2)  # R: Column[float | None]
    reveal_type(o.c.amount > 0)  # R: Column[bool]
    reveal_type(o.c.discount > 0)  # R: Column[bool | None]
    reveal_type(o.c.status.str.len_chars())  # R: Column[int]
    reveal_type(o.c.order_ts.dt.truncate("1mo").dt.date())  # R: Column[date]
    reveal_type(o.c.amount.sum())  # R: Column[float]
    reveal_type(o.c.order_id.count())  # R: Column[int]
    reveal_type(o.c.amount.rank("dense").over("customer_id"))  # R: Column[int]
    o.c.status + 1  # E str + int
    pl.col(Orders.amount)  # ok: class access is the name
    pl.col(Orders.amout)  # E typo in native code via class access
    Orders.amount > 0  # E name (str) used as an expression
    # schema-preserving methods keep DataFrame[S]
    reveal_type(o.filter(o.c.amount > 0))  # R: DataFrame[Orders]
    reveal_type(o.sort("order_ts").head(5))  # R: DataFrame[Orders]
    reveal_type(o.unique(["order_id"]))  # R: DataFrame[Orders]
    # narwhals API directly; schema-changing results are plain LazyFrames
    reveal_type(o.with_columns(x=o.c.amount * 2))  # R: LazyFrame[Any]
    reveal_type(o.group_by("status").agg(total=o.c.amount.sum()))  # R: LazyFrame[Any]
    reveal_type(o.join(c, on="customer_id"))  # R: LazyFrame[Any]
    reveal_type(o.select(o.c.order_id, "status"))  # R: LazyFrame[Any]
    reveal_type(nw.to_native(o))  # R: Any
    nw.concat([o, o])  # ok: a DataFrame[S] is a narwhals LazyFrame
    reveal_type(Orders.conform(o.with_columns(amount=o.c.amount * 2)))  # R: DataFrame[Orders]
    # wrong frame / forgot cast / raw frames / subtyping
    takes_orders(c)  # E Customers frame
    takes_orders(o.with_columns(x=o.c.amount * 2))  # E forgot to conform
    takes_orders(o.group_by("status").agg(n=o.c.order_id.count()))  # E forgot to conform
    takes_orders(plain)  # E raw narwhals frame
    takes_orders(raw)  # E raw polars frame
    takes_orders(o)
    x: DataFrame[NetOrders] = o  # E Orders is not NetOrders


def construct(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    reveal_type(Net.build(o, net_amount=o.c.amount - 1))  # R: DataFrame[Net]
    Net.build(o, net_amount=o.c.status)  # E str into float
    Net.build(o)  # E missing column
    Net.build(o, net_amount=o.c.amount, bogus=o.c.amount)  # E extra column
    Net.build(o, net_amount=o.c.discount)  # E nullable into non-null
    Net.build(o, net_amount=o.c.amount - o.c.discount)  # E float | None into float (forgot fill_null)
    Net.build(o, net_amount=o.c.amount - o.c.discount.fill_null(0))
    reveal_type(Stats.build(o.group_by("status"), status=o.c.status, n=o.c.order_id.count(), total=o.c.amount.sum()))  # R: DataFrame[Stats]
    Stats.build(o.group_by("status"), status=o.c.status, n=o.c.amount.sum(), total=o.c.amount.sum())  # E float into int
    reveal_type(NetOrders.extend(o, Net.build(o, net_amount=o.c.amount)))  # R: DataFrame[NetOrders]
    NetOrders.extend(c, Net.build(o, net_amount=o.c.amount))  # E Customers is not a base of NetOrders
    Stats.extend(o, Net.build(o, net_amount=o.c.amount))  # E Stats does not subclass Orders
    label = tc.when(o.c.amount > 100).then("big").otherwise("small")
    reveal_type(label)  # R: Column[str]
    Net.build(o, net_amount=tc.when(o.c.amount > 100).then("big").otherwise("small"))  # E str into float
    Net.build(o, net_amount=nw.col("amount"))  # E untyped narwhals Expr is not a Column[float]
    Net.build(o, net_amount=tc.expr(nw.col("amount")))  # ok: explicit escape hatch


def dedupe[S: tc.Schema](df: DataFrame[S], key: str) -> DataFrame[S]:
    return df.unique([key])


def recent[S: HasEventTs](df: DataFrame[S], since: datetime) -> DataFrame[S]:
    reveal_type(df.c.event_ts)  # R: Column[datetime]
    df.c.event_tss  # E typo in generic body
    return df.filter(df.c.event_ts >= since)


def generic(o: DataFrame[Orders], n: DataFrame[NetOrders], k: DataFrame[Clicks]) -> None:
    reveal_type(dedupe(o, "order_id"))  # R: DataFrame[Orders]
    reveal_type(recent(k, datetime(2024, 1, 1)))  # R: DataFrame[Clicks]
    recent(o, datetime(2024, 1, 1))  # E Orders has no event_ts
    takes_orders(n)  # ok: covariant
    Net.build(o, net_amount=o.c.amount).c.net_amont  # E typo after build
    reveal_type(Net.build(o, net_amount=o.c.amount).c.net_amount)  # R: Column[float]
