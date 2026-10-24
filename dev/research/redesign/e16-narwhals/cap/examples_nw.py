"""The three E8/E13 examples (iris, TPC-H Q1, e-commerce) written in plain narwhals (stable.v2).

Every function takes and returns narwhals frames; the same code runs on every backend.
The ibis reference versions are in examples_ibis.py.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import narwhals.stable.v2 as nw

Frame = Any  # nw.DataFrame[Any] | nw.LazyFrame[Any]


# ----------------------------------------------------------------------------- iris
def iris(df: Frame) -> Frame:
    feats = df.with_columns(
        sepal_ratio=nw.col("sepal_length") / nw.col("sepal_width"),
        petal_ratio=nw.col("petal_length") / nw.col("petal_width"),
        petal_area=nw.col("petal_length") * nw.col("petal_width"),
    )
    species = (
        nw.when(nw.col("petal_length") < 2.5)
        .then(nw.lit("setosa"))
        .when(nw.col("petal_length") < 4.8)
        .then(nw.lit("versicolor"))
        .otherwise(nw.lit("virginica"))
    )
    return feats.with_columns(predicted_species=species)


# ----------------------------------------------------------------------------- TPC-H Q1
def tpch_q1(li: Frame) -> Frame:
    shipped = li.filter(nw.col("l_shipdate") <= date(1998, 9, 2))
    disc_price = nw.col("l_extendedprice") * (1 - nw.col("l_discount"))
    return (
        shipped.group_by("l_returnflag", "l_linestatus")
        .agg(
            sum_qty=nw.col("l_quantity").sum(),
            sum_base_price=nw.col("l_extendedprice").sum(),
            sum_disc_price=disc_price.sum(),
            sum_charge=(disc_price * (1 + nw.col("l_tax"))).sum(),
            avg_qty=nw.col("l_quantity").mean(),
            avg_price=nw.col("l_extendedprice").mean(),
            avg_disc=nw.col("l_discount").mean(),
            count_order=nw.col("l_orderkey").count(),
        )
        .sort("l_returnflag", "l_linestatus")
    )


# ----------------------------------------------------------------------------- e-commerce
def clean_orders(orders: Frame) -> Frame:
    kept = orders.filter(nw.col("status") != "cancelled")
    return kept.with_columns(net_amount=nw.col("amount") - nw.col("discount").fill_null(0))


def country_month_stats(orders: Frame, customers: Frame) -> Frame:
    j = orders.join(customers, on="customer_id", how="inner")
    return (
        j.with_columns(order_month=nw.col("order_ts").dt.truncate("1mo").dt.date())
        .group_by("country", "order_month")
        .agg(
            order_count=nw.col("order_id").count(),
            total_net=nw.col("net_amount").sum(),
            avg_net=nw.col("net_amount").mean(),
            distinct_customers=nw.col("customer_id").n_unique(),
        )
    )


def status_summary(orders: Frame) -> Frame:
    by_status = orders.group_by("status").agg(
        orders=nw.col("order_id").count(), revenue=nw.col("net_amount").sum()
    )
    return by_status.with_columns(share=nw.col("revenue") / nw.col("revenue").sum())


def latest_per_key(df: Frame) -> Frame:
    """row_number() over (partition by customer_id order by order_ts desc) == 1."""
    rn = nw.col("order_ts").rank("ordinal", descending=True).over("customer_id")
    return df.filter(rn == 1)


def latest_per_key_rowidx(df: Frame) -> Frame:
    """Variant without rank: keep rows whose ts equals the partition max (max().over())."""
    return df.filter(nw.col("order_ts") == nw.col("order_ts").max().over("customer_id"))


def validate_customers(c: Frame) -> Frame:
    """The string checks behind RawCustomer's fields: regex and length."""
    return c.select(
        bad_email=(~nw.col("email").str.contains(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).sum(),
        bad_country=(nw.col("country").str.len_chars() != 2).sum(),
    )


def ecommerce(orders: Frame, customers: Frame) -> dict[str, Frame]:
    cleaned = clean_orders(orders)
    return {
        "stats": country_month_stats(cleaned, customers),
        "status": status_summary(cleaned),
        "latest": latest_per_key(cleaned),
        "latest_max": latest_per_key_rowidx(cleaned),
        "checks": validate_customers(customers),
    }
