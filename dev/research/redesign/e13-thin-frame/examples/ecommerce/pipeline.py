"""E-commerce pipeline from the E6 agent trial, ported to tacit-thin (E13).

Same data (../../../e6-agent-trial/*.csv), same logic as the E8 port. Frames are
ibis Tables, so `status_summary` uses the plain ibis API directly on a frame and
re-enters the typed world with `.conform`.
"""

from datetime import date, datetime
from pathlib import Path
from typing import Any

import ibis
from ibis import _

import tacit_thin as tc
from tacit_thin import Column

E6 = Path(__file__).resolve().parents[3] / "e6-agent-trial"


class RawCustomer(tc.Frame):
    customer_id: Column[int]
    name: Column[str]
    email: Column[str] = tc.field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    country: Column[str] = tc.field(length=2)
    signup_date: Column[date]


class RawOrder(tc.Frame):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str] = tc.field(isin=["pending", "shipped", "cancelled"])
    amount: Column[float] = tc.field(ge=0)
    discount: Column[float | None] = tc.field(ge=0)


class NetAmount(tc.Frame):
    net_amount: Column[float]


class Order(RawOrder, NetAmount):
    pass


class CountryMonthStats(tc.Frame):
    country: Column[str]
    order_month: Column[date]
    order_count: Column[int]
    total_net: Column[float]
    avg_net: Column[float]
    distinct_customers: Column[int]


def clean_orders(orders: RawOrder) -> Order:
    kept = orders.filter(orders.status != "cancelled")
    return Order.extend(kept, NetAmount(net_amount=kept.amount - kept.discount.fill_null(0)))


def country_month_stats(orders: Order, customers: RawCustomer) -> CountryMonthStats:
    j = tc.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    o, c = j.left, j.right
    return CountryMonthStats(
        country=c.country,
        order_month=o.order_ts.truncate("M").date(),
        order_count=o.order_id.count(),
        total_net=o.net_amount.sum(),
        avg_net=o.net_amount.mean(),
        distinct_customers=o.customer_id.nunique(),
    )


class StatusSummary(tc.Frame):
    status: Column[str]
    orders: Column[int]
    revenue: Column[float]
    share: Column[float]


def status_summary(orders: Order) -> StatusSummary:
    """Plain ibis on a frame (group_by/agg/mutate with a window), then a structural re-entry."""
    by_status = orders.group_by(orders.status).agg(orders=orders.order_id.count(), revenue=orders.net_amount.sum())
    # untyped intermediate table: refer to its columns with ibis's deferred `_` (typed `Deferred` everywhere)
    return StatusSummary.conform(by_status.mutate(share=_.revenue / _.revenue.sum()))


def latest_per_key[F: tc.Frame](df: F, key: Column[Any], ts: Column[datetime]) -> F:
    return df.filter(tc.row_number().over(group_by=key, order_by=ts.desc()) == 0)


def main(customers_csv: Path = E6 / "customers.csv", orders_csv: Path = E6 / "orders.csv") -> None:
    con = ibis.duckdb.connect()
    customers = RawCustomer.parse(con.read_csv(customers_csv))
    orders = RawOrder.parse(con.read_csv(orders_csv))
    cleaned = clean_orders(orders)
    stats = country_month_stats(cleaned, customers)
    latest = latest_per_key(cleaned, key=cleaned.customer_id, ts=cleaned.order_ts)
    print("latest order per customer:", latest.count().execute(), "rows")
    print(stats.order_by(stats.country, stats.order_month).to_pandas())
    print(status_summary(cleaned).order_by(StatusSummary.status).to_pandas())


if __name__ == "__main__":
    main()
