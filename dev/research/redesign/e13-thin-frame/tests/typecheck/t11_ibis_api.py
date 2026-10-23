# ruff: noqa: B015, B018
"""E13: the whole ibis Table API directly on a frame; results are plain tables (schema dropped)."""

from typing import reveal_type

import ibis
import ibis.expr.types as ir
import ibis.selectors as s
from _schemas import Customers, Orders, Stats
from ibis import _

import tacit_thin as tc


def direct(o: Orders, c: Customers, t: ir.Table) -> None:
    # @feature ibis methods on the frame type-check and return a plain table
    reveal_type(o.mutate(x=o.amount * 2))  # R: Table
    reveal_type(o.mutate(x=_.amount * 2, y=o.status.upper()))  # R: Table
    reveal_type(o.select(o.order_id, o.amount))  # R: Table
    reveal_type(o.select("order_id", s.numeric()))  # R: Table
    reveal_type(o.drop("note"))  # R: Table
    reveal_type(o.rename(oid="order_id"))  # R: Table
    reveal_type(o.cast({"amount": "float32"}))  # R: Table
    reveal_type(o.group_by(o.status).agg(total=o.amount.sum()))  # R: Table
    reveal_type(o.group_by("status").aggregate(n=_.order_id.count()))  # R: Table
    reveal_type(o.aggregate(total=o.amount.sum(), by=[o.status]))  # R: Table
    reveal_type(o.join(c, o.customer_id == c.customer_id))  # R: Table
    reveal_type(o.join(c, [o.customer_id == c.customer_id], how="left"))  # R: Table
    reveal_type(o.left_join(c, "customer_id"))  # R: Table
    reveal_type(o.join(t, "order_id"))  # R: Table
    reveal_type(o.union(o))  # R: Table
    reveal_type(o.distinct())  # R: Orders
    reveal_type(o.mutate(rn=ibis.row_number().over(group_by=o.status, order_by=o.order_ts)))  # R: Table
    reveal_type(o.mutate(rn=tc.row_number().over(group_by=o.status, order_by=o.order_ts.desc())))  # R: Table
    reveal_type(o.mutate(run=o.amount.sum().over(ibis.window(group_by=o.status, order_by=o.order_ts))))  # R: Table
    reveal_type(o.mutate(one=1))  # R: Table
    reveal_type(o.count())  # R: IntegerScalar
    reveal_type(o.schema())  # R: Schema
    reveal_type(o.columns)  # R: tuple[str, ...]
    reveal_type(o.to_pandas())  # R: DataFrame
    reveal_type(o.to_polars())  # R: DataFrame
    reveal_type(o.compile())  # R: str | LazyFrame
    reveal_type(o["amount"])  # R: Column
    o.sample(0.5)
    o.describe()
    o.pivot_longer(s.numeric(), names_to="k", values_to="v")
    o.dropna()  # ok (deprecated; at most a hint)
    # @feature typos stay errors on the frame, and on ibis method names
    o.mutat(x=1)  # E: typo in ibis method name
    o.amout  # E: typo in column
    o.group_by(o.status).agg(total=o.amout.sum())  # E: typo inside an ibis call


def results(o: Orders, c: Customers) -> None:
    # @feature chaining on untyped results (plain ibis idioms)
    m = o.mutate(x=o.amount * 2)
    m.filter(m["x"] > 1).select("x")
    m.filter(_.x > 1)
    m.x  # ok: ibis allows attribute access on untyped tables
    m.filter(m.x > 1)  # ok: same idiom
    # @feature re-entering the schema world
    reveal_type(Orders.conform(o.filter(o.amount > 0).mutate(amount=o.amount * 2)))  # R: Orders
    reveal_type(Stats.conform(o.group_by(o.status).agg(n=o.order_id.count(), total=o.amount.sum())))  # R: Stats


def interop(o: Orders, t: ir.Table) -> None:
    # @feature a frame passed to ibis functions typed `ir.Table`
    ibis.union(o, o)  # ok at runtime: a frame IS an ir.Table
    x: ir.Table = o  # ok at runtime
    ibis.duckdb.connect().create_table("x", o)  # ok at runtime
    ibis.union(tc.as_table(o), t)  # ok: explicit escape
    t.join(o, "order_id")  # ok: ibis method taking a table


def takes_table(t: tc.Table) -> None: ...
def takes_api(t: tc.TableAPI) -> None: ...


def annotations(o: Orders) -> None:
    # @feature tacit's own table annotations accept frames and ibis results
    takes_table(o.mutate(x=o.amount * 2))  # ok
    takes_api(o)  # ok
    takes_api(o.mutate(x=o.amount * 2))  # ok
    takes_table(o)  # ok at runtime (a frame IS a Table)
