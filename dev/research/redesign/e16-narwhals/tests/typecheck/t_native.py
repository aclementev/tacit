# ruff: noqa: B015, B018
"""The native story: users write polars / PySpark; tacit tags frames (PolarsFrame[S], SparkFrame[S])."""

from typing import reveal_type

import polars as pl
from pyspark.sql import DataFrame as SparkDF
from pyspark.sql import functions as F

import tacit_nw as tc
from tacit_nw import Column, PolarsFrame, SparkFrame


class Orders(tc.Schema):
    order_id: Column[int]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]


class Customers(tc.Schema):
    customer_id: Column[int]


class Net(tc.Schema):
    order_id: Column[int]
    net_amount: Column[float]


O = tc.names(Orders)


@tc.step
def net_polars(o: PolarsFrame[Orders]) -> PolarsFrame[Net]:
    out = o.with_columns(net_amount=pl.col(O.amount) - pl.col(O.discount).fill_null(0)).select(O.order_id, "net_amount")
    reveal_type(out)  # R: DataFrame
    return tc.tag(Net, out)


@tc.step
def net_polars_forgot(o: PolarsFrame[Orders]) -> PolarsFrame[Net]:
    return o.with_columns(net_amount=pl.col(O.amount))  # E forgot to tag/validate


@tc.step
def net_polars_filter(o: PolarsFrame[Orders]) -> PolarsFrame[Orders]:
    return o.filter(pl.col(O.amount) > 0)  # E (false positive) filter drops the tag too


def typos_polars(o: PolarsFrame[Orders]) -> None:
    pl.col(O.amout)  # E typo caught via the schema
    pl.col("amout")  # E (ideal) raw string, unchecked
    o.amount  # E polars has no attribute access
    pl.col(O.status) + 1  # E (ideal) str + int: pl.Expr has no dtype
    reveal_type(pl.col(O.amount).sum())  # R: Expr


def wrong_frames(o: PolarsFrame[Orders], c: PolarsFrame[Customers], raw: pl.DataFrame, s: SparkFrame[Orders]) -> None:
    net_polars(c)  # E Customers frame
    net_polars(raw)  # E untagged native frame
    net_polars(s)  # E spark frame into a polars step
    net_polars(o)
    reveal_type(tc.tag(Orders, raw))  # R: PolarsFrame[Orders]


@tc.step
def net_spark(o: SparkFrame[Orders]) -> SparkFrame[Net]:
    out = o.withColumn("net_amount", F.col(O.amount) - F.coalesce(F.col(O.discount), F.lit(0))).select(O.order_id, "net_amount")
    reveal_type(out)  # R: DataFrame
    return tc.tag(Net, out)


def typos_spark(o: SparkFrame[Orders], raw: SparkDF) -> None:
    F.col(O.amout)  # E typo caught via the schema
    o.amout  # E (ideal) PySpark __getattr__ returns a Column for any name
    o[O.amount]
    net_spark(raw)  # E untagged native frame
    o.withColumn("x", F.col(O.amount)).amount  # E (ideal) __getattr__ again
    F.col(O.status) + 1  # E (ideal) Column has no dtype
