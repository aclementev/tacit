"""The three examples in the T2-on-narwhals spelling (tacit_nw). Backend-agnostic: the entry points
take native frames from any narwhals backend (polars, duckdb, pyspark, sqlframe, ibis)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import narwhals.stable.v2 as nw

import tacit_nw as tc
from tacit_nw import Column, DataFrame


# ----------------------------------------------------------------------------- iris
class Iris(tc.Schema):
    sepal_length: Column[float]
    sepal_width: Column[float]
    petal_length: Column[float]
    petal_width: Column[float]
    species: Column[str]


class Ratios(tc.Schema):
    sepal_ratio: Column[float]
    petal_ratio: Column[float]
    petal_area: Column[float]


class IrisFeatures(Iris, Ratios):
    pass


class Prediction(tc.Schema):
    predicted_species: Column[str]


class IrisPrediction(IrisFeatures, Prediction):
    pass


def engineer_features(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    c = df.c
    return IrisFeatures.extend(df, Ratios.build(
        df,
        sepal_ratio=c.sepal_length / c.sepal_width,
        petal_ratio=c.petal_length / c.petal_width,
        petal_area=c.petal_length * c.petal_width,
    ))


def predict(df: DataFrame[IrisFeatures]) -> DataFrame[IrisPrediction]:
    species = tc.when(df.c.petal_length < 2.5).then("setosa").when(df.c.petal_length < 4.8).then("versicolor").otherwise("virginica")
    return IrisPrediction.extend(df, Prediction.build(df, predicted_species=species))


def iris(native: Any) -> DataFrame[IrisPrediction]:
    return IrisPrediction.parse(predict(engineer_features(Iris.parse(native))))


# ----------------------------------------------------------------------------- TPC-H Q1
class LineItem(tc.Schema):
    l_orderkey: Column[int]
    l_quantity: Column[float]
    l_extendedprice: Column[float]
    l_discount: Column[float]
    l_tax: Column[float]
    l_returnflag: Column[str]
    l_linestatus: Column[str]
    l_shipdate: Column[date]


class PricingSummary(tc.Schema):
    l_returnflag: Column[str]
    l_linestatus: Column[str]
    sum_qty: Column[float]
    sum_base_price: Column[float]
    sum_disc_price: Column[float]
    sum_charge: Column[float]
    avg_qty: Column[float]
    avg_price: Column[float]
    avg_disc: Column[float]
    count_order: Column[int]


def tpch_q1(native: Any) -> DataFrame[PricingSummary]:
    li = LineItem.parse(native)
    s = li.filter(li.c.l_shipdate <= date(1998, 9, 2))
    c = s.c
    disc = c.l_extendedprice * (1 - c.l_discount)
    out = PricingSummary.build(
        s.group_by(LineItem.l_returnflag, LineItem.l_linestatus),
        l_returnflag=c.l_returnflag,
        l_linestatus=c.l_linestatus,
        sum_qty=c.l_quantity.sum(),
        sum_base_price=c.l_extendedprice.sum(),
        sum_disc_price=disc.sum(),
        sum_charge=(disc * (1 + c.l_tax)).sum(),
        avg_qty=c.l_quantity.mean(),
        avg_price=c.l_extendedprice.mean(),
        avg_disc=c.l_discount.mean(),
        count_order=c.l_orderkey.count(),
    )
    return out.sort(PricingSummary.l_returnflag, PricingSummary.l_linestatus)


# ----------------------------------------------------------------------------- e-commerce
class RawCustomer(tc.Schema):
    customer_id: Column[int]
    name: Column[str]
    email: Column[str] = tc.field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    country: Column[str] = tc.field(length=2)
    signup_date: Column[date]


class RawOrder(tc.Schema):
    order_id: Column[int] = tc.field(unique=True)
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0)
    discount: Column[float | None] = tc.field(ge=0)


class NetAmount(tc.Schema):
    net_amount: Column[float]


class Order(RawOrder, NetAmount):
    pass


class CountryMonthStats(tc.Schema):
    country: Column[str]
    order_month: Column[date]
    order_count: Column[int]
    total_net: Column[float]
    avg_net: Column[float]
    distinct_customers: Column[int]


class StatusSummary(tc.Schema):
    status: Column[str]
    orders: Column[int]
    revenue: Column[float]
    share: Column[float]


def clean_orders(o: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = o.filter(o.c.status != "cancelled")
    return Order.extend(kept, NetAmount.build(kept, net_amount=kept.c.amount - kept.c.discount.fill_null(0)))


def country_month_stats(o: DataFrame[Order], cust: DataFrame[RawCustomer]) -> DataFrame[CountryMonthStats]:
    # plain narwhals for the join (untyped intermediate), re-entering through conform
    j = o.join(cust, on=Order.customer_id).with_columns(order_month=o.c.order_ts.dt.truncate("1mo").dt.date())
    return CountryMonthStats.conform(j.group_by("country", "order_month").agg(
        order_count=o.c.order_id.count(),
        total_net=o.c.net_amount.sum(),
        avg_net=o.c.net_amount.mean(),
        distinct_customers=o.c.customer_id.n_unique(),
    ))


def status_summary(o: DataFrame[Order]) -> DataFrame[StatusSummary]:
    by = o.group_by(Order.status).agg(orders=o.c.order_id.count(), revenue=o.c.net_amount.sum())
    return StatusSummary.conform(by.with_columns(share=nw.col("revenue") / nw.col("revenue").sum()))


def latest_per_key[S: tc.Schema](df: DataFrame[S], key: str, ts: str) -> DataFrame[S]:
    return df.filter(nw.col(ts).rank("ordinal", descending=True).over(key) == 1)


def ecommerce(orders_native: Any, customers_native: Any) -> dict[str, Any]:
    customers = RawCustomer.parse(customers_native)
    orders = RawOrder.parse(orders_native)
    cleaned = clean_orders(orders)
    return {
        "stats": country_month_stats(cleaned, customers),
        "status": status_summary(cleaned),
        "latest": latest_per_key(cleaned, Order.customer_id, Order.order_ts),
    }
