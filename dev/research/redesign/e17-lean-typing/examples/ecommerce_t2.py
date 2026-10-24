"""E6 e-commerce pipeline (E13 examples/ecommerce/pipeline.py) in the T2 spelling."""

from datetime import date, datetime
from pathlib import Path

import ibis
from ibis import _

import tacit_t2 as tc2
from tacit_t2 import AnyCol, Column, DataFrame, TsCol

E6 = Path(__file__).resolve().parents[2] / "e6-agent-trial"


class RawCustomer(tc2.Schema):
    customer_id: Column[int]
    name: Column[str]
    email: Column[str] = tc2.field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    country: Column[str] = tc2.field(length=2)
    signup_date: Column[date]


class RawOrder(tc2.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc2.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc2.field(ge=0)
    discount: Column[float | None] = tc2.field(ge=0)


class NetAmount(tc2.Schema):
    net_amount: Column[float]


class Order(RawOrder, NetAmount):
    pass


class CountryMonthStats(tc2.Schema):
    country: Column[str]
    order_month: Column[date]
    order_count: Column[int]
    total_net: Column[float]
    avg_net: Column[float]
    distinct_customers: Column[int]


class StatusSummary(tc2.Schema):
    status: Column[str]
    orders: Column[int]
    revenue: Column[float]
    share: Column[float]


def clean_orders(orders: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = orders.filter(orders.c.status != "cancelled")
    k = kept.c
    return Order.extend(kept, NetAmount.build(net_amount=k.amount - k.discount.fill_null(0)))


def country_month_stats(orders: DataFrame[Order], customers: DataFrame[RawCustomer]) -> DataFrame[CountryMonthStats]:
    j = tc2.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    o, c = j.left, j.right
    return CountryMonthStats.build(
        country=c.country,
        order_month=o.order_ts.truncate("M").date(),
        order_count=o.order_id.count(),
        total_net=o.net_amount.sum(),
        avg_net=o.net_amount.mean(),
        distinct_customers=o.customer_id.nunique(),
    )


def status_summary(orders: DataFrame[Order]) -> DataFrame[StatusSummary]:
    """Plain ibis on a frame (group_by/agg/mutate with a window), then a structural re-entry."""
    o = orders.c
    by_status = orders.group_by(o.status).agg(orders=o.order_id.count(), revenue=o.net_amount.sum())
    return StatusSummary.conform(by_status.mutate(share=_.revenue / _.revenue.sum()))


def latest_per_key[S: tc2.Schema](df: DataFrame[S], key: AnyCol, ts: TsCol) -> DataFrame[S]:
    return df.filter(tc2.row_number().over(group_by=key, order_by=ts.desc()) == 0)


def run_steps(
    orders: DataFrame[RawOrder], customers: DataFrame[RawCustomer]
) -> tuple[DataFrame[Order], DataFrame[CountryMonthStats], DataFrame[Order], DataFrame[StatusSummary]]:
    """Every step, building expressions only (no query runs here)."""
    cleaned = clean_orders(orders)
    stats = country_month_stats(cleaned, customers)
    latest = latest_per_key(cleaned, key=cleaned.c.customer_id, ts=cleaned.c.order_ts)
    return cleaned, stats, latest, status_summary(cleaned)


def main(customers_csv: Path = E6 / "customers.csv", orders_csv: Path = E6 / "orders.csv") -> None:
    con = ibis.duckdb.connect()
    customers = RawCustomer.parse(con.read_csv(customers_csv))
    orders = RawOrder.parse(con.read_csv(orders_csv))
    cleaned, stats, latest, summary = run_steps(orders, customers)
    print("latest order per customer:", latest.count().execute(), "rows")
    print(stats.order_by(stats.c.country, stats.c.order_month).to_pandas())
    print(summary.order_by(StatusSummary.status).to_pandas())


if __name__ == "__main__":
    main()
