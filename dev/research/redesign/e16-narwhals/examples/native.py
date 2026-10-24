"""The e-commerce example written in *native* polars and in *native* PySpark; tacit only tags,
validates and names columns (tacit_nw.tag / names / step)."""

from __future__ import annotations

import polars as pl
from pyspark.sql import Window
from pyspark.sql import functions as F

import tacit_nw as tc
from tacit_nw import PolarsFrame, SparkFrame

from t2nw import CountryMonthStats, NetAmount, Order, RawCustomer, RawOrder, StatusSummary

O, C = tc.names(Order), tc.names(RawCustomer)


# ----------------------------------------------------------------------------- polars
@tc.step
def clean_orders_pl(o: PolarsFrame[RawOrder]) -> PolarsFrame[Order]:
    kept = o.filter(pl.col(O.status) != "cancelled")
    return tc.tag(Order, kept.with_columns(pl.col(O.amount).sub(pl.col(O.discount).fill_null(0)).alias(NetAmount.net_amount)))


@tc.step
def country_month_stats_pl(o: PolarsFrame[Order], c: PolarsFrame[RawCustomer]) -> PolarsFrame[CountryMonthStats]:
    out = (
        o.join(c, on=O.customer_id)
        .group_by(C.country, pl.col(O.order_ts).dt.truncate("1mo").dt.date().alias("order_month"))
        .agg(
            order_count=pl.col(O.order_id).count(),
            total_net=pl.col(O.net_amount).sum(),
            avg_net=pl.col(O.net_amount).mean(),
            distinct_customers=pl.col(O.customer_id).n_unique(),
        )
    )
    return tc.tag(CountryMonthStats, out)


@tc.step
def status_summary_pl(o: PolarsFrame[Order]) -> PolarsFrame[StatusSummary]:
    by = o.group_by(O.status).agg(orders=pl.len(), revenue=pl.col(O.net_amount).sum())
    return tc.tag(StatusSummary, by.with_columns(share=pl.col("revenue") / pl.col("revenue").sum()))


def latest_pl(o: PolarsFrame[Order]) -> PolarsFrame[Order]:
    return tc.tag(Order, o.filter(pl.col(O.order_ts).rank("ordinal", descending=True).over(O.customer_id) == 1), validate=False)


def ecommerce_polars(orders: pl.DataFrame, customers: pl.DataFrame) -> dict[str, pl.DataFrame]:
    cust = tc.tag(RawCustomer, customers)
    cleaned = clean_orders_pl(tc.tag(RawOrder, orders))
    return {"stats": country_month_stats_pl(cleaned, cust), "status": status_summary_pl(cleaned), "latest": latest_pl(cleaned)}


# ----------------------------------------------------------------------------- pyspark
@tc.step
def clean_orders_sp(o: SparkFrame[RawOrder]) -> SparkFrame[Order]:
    kept = o.filter(F.col(O.status) != "cancelled")
    return tc.tag(Order, kept.withColumn(NetAmount.net_amount, F.col(O.amount) - F.coalesce(F.col(O.discount), F.lit(0.0))))


@tc.step
def country_month_stats_sp(o: SparkFrame[Order], c: SparkFrame[RawCustomer]) -> SparkFrame[CountryMonthStats]:
    out = (
        o.join(c, on=O.customer_id)
        .groupBy(F.col(C.country), F.to_date(F.date_trunc("month", F.col(O.order_ts))).alias("order_month"))
        .agg(
            F.count(O.order_id).alias("order_count"),
            F.sum(O.net_amount).alias("total_net"),
            F.avg(O.net_amount).alias("avg_net"),
            F.count_distinct(O.customer_id).alias("distinct_customers"),
        )
    )
    return tc.tag(CountryMonthStats, out)


@tc.step
def status_summary_sp(o: SparkFrame[Order]) -> SparkFrame[StatusSummary]:
    by = o.groupBy(O.status).agg(F.count("*").alias("orders"), F.sum(O.net_amount).alias("revenue"))
    return tc.tag(StatusSummary, by.withColumn("share", F.col("revenue") / F.sum("revenue").over(Window.partitionBy())))


def latest_sp(o: SparkFrame[Order]) -> SparkFrame[Order]:
    w = Window.partitionBy(O.customer_id).orderBy(F.col(O.order_ts).desc())
    return tc.tag(Order, o.withColumn("_rn", F.row_number().over(w)).filter(F.col("_rn") == 1).drop("_rn"), validate=False)


def ecommerce_spark(orders: object, customers: object) -> dict[str, object]:
    from pyspark.sql import DataFrame as SDF

    assert isinstance(orders, SDF) and isinstance(customers, SDF)
    cust = tc.tag(RawCustomer, customers)
    cleaned = clean_orders_sp(tc.tag(RawOrder, orders))
    return {"stats": country_month_stats_sp(cleaned, cust), "status": status_summary_sp(cleaned), "latest": latest_sp(cleaned)}
