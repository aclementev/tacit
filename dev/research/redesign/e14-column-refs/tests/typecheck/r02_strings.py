# ruff: noqa: B015, B018
"""E14 spelling B: string keys typed by GENERATED Literal overloads (`gen_schemas.pyi`, tools/tacit_gen.py)."""

from datetime import datetime
from typing import reveal_type

from gen_schemas import Clicks, Customers, HasEventTs, Net, NetOrders, Orders

from tacit_r import DataFrame


def schema_getitem(o: DataFrame[Orders], n: DataFrame[NetOrders], key: str) -> None:
    # @feature df.c["x"]: generated __getitem__ overloads on the schema class
    reveal_type(o.c["amount"])  # R: Column[float]
    reveal_type(o.c["discount"])  # R: Column[float | None]
    o.c["amout"]  # E: typo
    o.c[key]  # E: non-literal key
    reveal_type(o.c["amount"] * 2)  # R: Column[float]
    o.c["amount"].upper()  # E: wrong method
    reveal_type(n.c["amount"])  # R: Column[float]
    reveal_type(n.c["net_amount"])  # R: Column[float]
    o.c["net_amount"]  # E: child column on parent
    reveal_type(o.filter(o.c["amount"] > 0))  # R: DataFrame[Orders]


def frame_getitem(o: DataFrame[Orders], n: DataFrame[NetOrders], c: DataFrame[Customers]) -> None:
    # @feature df["x"]: DataFrame.__getitem__ through a Protocol over the schema's overloads
    reveal_type(o["amount"])  # R: Column[float]
    reveal_type(o["discount"])  # R: Column[float | None]
    o["amout"]  # E: typo
    reveal_type(n["net_amount"])  # R: Column[float]
    reveal_type(c["country"])  # R: Column[str]
    reveal_type(o.filter(o["amount"] > 0))  # R: DataFrame[Orders]


def schema_col(o: DataFrame[Orders], n: DataFrame[NetOrders]) -> None:
    # @feature Orders.col("x"): generated classmethod overloads -> owner-typed Ref
    reveal_type(Orders.col("amount"))  # R: Ref[Orders, float]
    reveal_type(NetOrders.col("amount"))  # R: Ref[NetOrders, float]
    Orders.col("amout")  # E: typo
    reveal_type(o.filter(Orders.col("amount") > 0))  # R: DataFrame[Orders]
    o.filter(Customers.col("country") == "x")  # E: wrong owner
    reveal_type(n.filter(Orders.col("amount") > 0))  # R: DataFrame[NetOrders]


def recent[S: HasEventTs](df: DataFrame[S], since: datetime) -> DataFrame[S]:
    reveal_type(df.c["event_ts"])  # R: Column[datetime]
    df.c["url"]  # E: S is only a HasEventTs
    reveal_type(df["event_ts"])  # R: Column[datetime]
    return df.filter(df.c["event_ts"] >= since)


def generic(k: DataFrame[Clicks], net: DataFrame[Net]) -> None:
    # @feature generic steps with string keys
    reveal_type(recent(k, datetime(2024, 1, 1)))  # R: DataFrame[Clicks]
    reveal_type(k.c["url"])  # R: Column[str]
    reveal_type(net["net_amount"])  # R: Column[float]
