# ruff: noqa: B015, B018
"""E14 spelling A: owner-typed unbound class refs, `Orders.amount` : Ref[Orders, float]."""

from datetime import datetime
from typing import Any, reveal_type

import ibis.expr.types as ir

import tacit_r as tr
from tacit_r import Column, DataFrame


class Orders(tr.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]
    count: Column[int]  # allowed (T2: columns are not table attributes)


class Customers(tr.Schema):
    customer_id: Column[int]
    country: Column[str]
    credit: Column[float]


class Net(tr.Schema):
    net_amount: Column[float]


class NetOrders(Orders, Net):
    pass


class Stats(tr.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class HasEventTs(tr.Schema):
    event_ts: Column[datetime]


class Clicks(HasEventTs):
    url: Column[str]


def takes_column(x: Column[float]) -> None: ...


def access(o: DataFrame[Orders]) -> None:
    # @feature ref access, typos, value types
    reveal_type(Orders.amount)  # R: Ref[Orders, float]
    reveal_type(NetOrders.amount)  # R: Ref[NetOrders, float]
    reveal_type(Orders.count)  # R: Ref[Orders, int]
    reveal_type(o.c.amount)  # R: Column[float]
    Orders.amout  # E: typo
    Orders.amount.upper()  # E: wrong method for float
    reveal_type(Orders.amount * 2)  # R: Ref[Orders, float]
    reveal_type(Orders.status.length())  # R: Ref[Orders, int]
    reveal_type(Orders.order_ts.desc())  # R: Ref[Orders, datetime]
    reveal_type(Orders.amount / Orders.amount.sum())  # R: Ref[Orders, float]
    reveal_type(Orders.amount.sum())  # R: RefScalar[Orders, float]
    Orders.amount + "x"  # E: str operand
    # @feature nullability through refs
    reveal_type(Orders.discount + 1.0)  # R: Ref[Orders, float | None]
    reveal_type(Orders.discount.fill_null(0.0))  # R: Ref[Orders, float]
    reveal_type(Orders.amount - Orders.discount.fill_null(0.0))  # R: Ref[Orders, float]
    # @feature E8 section 6 unsoundness fixed: a ref is not a column
    Orders.amount.get_name()  # E: Deferred has no name until resolved
    Orders.amount.execute()  # E: unbound
    takes_column(Orders.amount)  # E: Ref is not a Column
    v: ir.Value = Orders.amount  # E: Ref is not an ibis Value


def frame_methods(o: DataFrame[Orders], n: DataFrame[NetOrders], c: DataFrame[Customers]) -> None:
    # @feature owner check on DataFrame methods
    reveal_type(o.filter(Orders.amount > 0))  # R: DataFrame[Orders]
    o.filter(Customers.country == "x")  # E: Customers ref on an Orders frame
    reveal_type(n.filter(Orders.amount > 0))  # R: DataFrame[NetOrders]
    o.filter(NetOrders.net_amount > 0)  # E: child-schema ref on parent frame
    o.filter(Orders.amount)  # E: not a boolean
    reveal_type(o.order_by(Orders.order_ts.desc()))  # R: DataFrame[Orders]
    o.order_by(Customers.country.desc())  # E: wrong owner
    reveal_type(o.order_by(Orders.amount))  # R: DataFrame[Orders]
    reveal_type(n.order_by(Orders.amount))  # R: DataFrame[NetOrders]
    o.order_by(NetOrders.net_amount)  # E: bare child-schema ref on parent frame
    reveal_type(o.distinct(on=Orders.order_id))  # R: DataFrame[Orders]
    # @feature owner check on the generated ibis API (mutate/select/group_by/agg)
    reveal_type(o.mutate(x=Orders.amount * 2))  # R: Table
    o.mutate(x=Customers.country)  # E: wrong owner
    reveal_type(o.select(Orders.order_id, Orders.amount))  # R: Table
    o.select(Customers.country)  # E: wrong owner
    reveal_type(o.group_by(Orders.status).agg(total=Orders.amount.sum()))  # R: Table
    o.group_by(Customers.country)  # E: wrong owner
    o.group_by(Orders.status).agg(total=Orders.amount)  # E: not a reduction
    o.group_by(Orders.status).agg(total=Customers.customer_id.sum())  # E: wrong owner in agg
    reveal_type(o.group_by(key=Orders.status).agg(Orders.amount.mean()))  # R: Table
    # @feature intermediate (untyped) tables: owner unchecked by design
    m = o.mutate(x=Orders.amount * 2)
    m.filter(Orders.amount > 0)
    m.filter(Customers.country == "x")  # E: wrong owner, but m is a plain Table (TableAPI[Any])


def mixing(o: DataFrame[Orders]) -> None:
    # @feature combining refs from two schemas
    Orders.amount + Customers.customer_id  # E: unrelated owners
    Orders.amount + Customers.credit  # E: unrelated owners, same value type
    o.filter(Orders.amount > Customers.credit)  # E: unrelated owners in a predicate
    reveal_type(NetOrders.net_amount + Orders.amount)  # R: Ref[NetOrders, float]
    reveal_type(Orders.amount + NetOrders.net_amount)  # R: Ref[NetOrders, float]
    reveal_type(NetOrders.amount + NetOrders.net_amount)  # R: Ref[NetOrders, float]
    Orders.amount + o.c.amount  # E: policy: no ref/bound mixing


def joins(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    # @feature joins with refs: key pairs are (left schema, right schema)
    reveal_type(o.join(c, [(Orders.customer_id, Customers.customer_id)]))  # R: Table
    o.join(c, [(Customers.customer_id, Orders.customer_id)])  # E: swapped key pair
    o.join(c, Orders.customer_id == Customers.customer_id)  # E: one predicate cannot have two owners
    o.join(o.view(), [(Orders.order_id, Orders.customer_id)])  # self-join: pair is positional


def construct(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    # @feature build(src, ...) / extend with refs
    reveal_type(Net.build(o, net_amount=Orders.amount - 1))  # R: DataFrame[Net]
    Net.build(o, net_amount=Orders.status)  # E: str into float
    Net.build(c, net_amount=Orders.amount)  # E: owner vs src (not expressible: build kwargs come from the schema)
    reveal_type(Stats.build(o, status=Orders.status, n=Orders.order_id.count(), total=Orders.amount.sum()))  # R: DataFrame[Stats]
    Stats.build(o, status=Orders.status, n=Orders.amount.sum(), total=Orders.amount.sum())  # E: float into int
    reveal_type(NetOrders.extend(o, Net.build(o, net_amount=Orders.amount)))  # R: DataFrame[NetOrders]
    NetOrders.extend(c, Net.build(o, net_amount=Orders.amount))  # E: Customers is not a base


def recent[S: HasEventTs](df: DataFrame[S], since: datetime) -> DataFrame[S]:
    HasEventTs.event_tss  # E: typo in generic body
    return df.filter(HasEventTs.event_ts >= since)


def newest_first[S: HasEventTs](df: DataFrame[S]) -> DataFrame[S]:
    return df.order_by(HasEventTs.event_ts)


def wrong_generic[S: HasEventTs](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(Clicks.url == "x")  # E: S is only known to be a HasEventTs


def generic(o: DataFrame[Orders], k: DataFrame[Clicks]) -> None:
    # @feature generic steps with parent-schema refs
    reveal_type(recent(k, datetime(2024, 1, 1)))  # R: DataFrame[Clicks]
    reveal_type(newest_first(k))  # R: DataFrame[Clicks]
    recent(o, datetime(2024, 1, 1))  # E: Orders has no event_ts
