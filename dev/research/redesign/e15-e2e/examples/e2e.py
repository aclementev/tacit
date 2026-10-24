"""Monthly revenue and top customers for an e-commerce shop.

Sources: order status events (one row per status change) and the CRM customer export.
Revenue is recognised on delivery.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import ibis
import pandera.ibis as pa
from ibis import _

import tacit_t3 as tacit
from tacit_t3 import Column, DataFrame, field

COUNTRIES = ["ES", "FR", "DE", "IT", "PT"]


# --- contracts -----------------------------------------------------------------------------
class Customers(tacit.Schema):
    """CRM export, one row per customer."""

    customer_id: Column[int] = field(unique=True)
    email: Column[str] = field(checks=[pa.Check.str_matches(r"^[^@\s]+@[^@\s]+\.\w+$")])
    country: Column[str] = field(isin=COUNTRIES)
    segment: Column[str | None] = field(isin=["consumer", "business"])
    signup_date: Column[date]


class OrderEvents(tacit.Schema):
    """Order service events: an order appears once per status change."""

    order_id: Column[int]
    customer_id: Column[int]
    status: Column[str] = field(isin=["shipped", "delivered", "cancelled", "returned"])
    channel: Column[str] = field(isin=["web", "app"])
    amount: Column[float] = field(ge=0, description="gross, EUR")
    discount: Column[float | None] = field(ge=0)
    ordered_at: Column[datetime]
    delivered_at: Column[datetime | None]
    updated_at: Column[datetime]


class OrderMetrics(tacit.Schema):
    net_amount: Column[float]
    order_month: Column[date]


class Orders(OrderEvents, OrderMetrics):
    """Latest state of each order."""


class DeliveryTime(tacit.Schema):
    delivery_hours: Column[int]


class DeliveredOrders(Orders, DeliveryTime):
    pass


class OrderFacts(tacit.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    country: Column[str]
    segment: Column[str]
    channel: Column[str]
    order_month: Column[date]
    net_amount: Column[float]
    delivery_hours: Column[int]


class MonthlyRevenue(tacit.Schema):
    country: Column[str]
    order_month: Column[date]
    orders: Column[int]
    app_orders: Column[int]
    revenue: Column[float]
    avg_order_value: Column[float]
    avg_delivery_hours: Column[float]


class CustomerValue(tacit.Schema):
    customer_id: Column[int]
    country: Column[str]
    orders: Column[int]
    revenue: Column[float]
    first_month: Column[date]
    share_of_country: Column[float] = field(ge=0, le=1)


class Rank(tacit.Schema):
    rank_in_country: Column[int]


class TopCustomers(CustomerValue, Rank):
    pass


# --- steps ---------------------------------------------------------------------------------
def keep_latest[S: tacit.Schema](df: DataFrame[S], key: Column[Any], ts: Column[datetime]) -> DataFrame[S]:
    """The most recent row per key, for any schema."""
    return df.filter(tacit.row_number().over(group_by=key, order_by=ts.desc()) == 0)


def add_metrics(events: DataFrame[OrderEvents]) -> DataFrame[Orders]:
    e = events.c
    return Orders.extend(events, OrderMetrics.build(
        net_amount=e.amount - e.discount.fill_null(0),
        order_month=e.ordered_at.truncate("M").date(),
    ))


def delivered(orders: DataFrame[Orders]) -> DataFrame[DeliveredOrders]:
    done = orders.filter(orders.c.status == "delivered")
    return DeliveredOrders.extend(done, DeliveryTime.build(
        delivery_hours=done.c.delivered_at.assume_not_null().delta(done.c.ordered_at, unit="hour"),
    ))


def with_customer(orders: DataFrame[DeliveredOrders], customers: DataFrame[Customers]) -> DataFrame[OrderFacts]:
    j = tacit.join(orders, customers, on=lambda o, c: o.customer_id == c.customer_id)
    o, c = j.left, j.right
    return OrderFacts.build(
        order_id=o.order_id,
        customer_id=o.customer_id,
        country=c.country,
        segment=c.segment.fill_null("unknown"),
        channel=o.channel,
        order_month=o.order_month,
        net_amount=o.net_amount,
        delivery_hours=o.delivery_hours,
    )


def monthly_revenue(facts: DataFrame[OrderFacts]) -> DataFrame[MonthlyRevenue]:
    f = facts.c
    return MonthlyRevenue.aggregate(by=[f.country, f.order_month])(
        country=f.country,
        order_month=f.order_month,
        orders=f.order_id.count(),
        app_orders=f.order_id.count(where=f.channel == "app"),
        revenue=f.net_amount.sum(),
        avg_order_value=f.net_amount.mean(),
        avg_delivery_hours=f.delivery_hours.mean(),
    ).order_by(MonthlyRevenue.country, MonthlyRevenue.order_month)


@tacit.step(validate=True)
def customer_value(facts: DataFrame[OrderFacts]) -> DataFrame[CustomerValue]:
    per_customer = facts.group_by("customer_id", "country").agg(
        orders=_.order_id.count(), revenue=_.net_amount.sum(), first_month=_.order_month.min()
    )
    return CustomerValue.conform(
        per_customer.mutate(share_of_country=_.revenue / _.revenue.sum().over(group_by="country"))
    )


def top_customers(value: DataFrame[CustomerValue], n: int = 3) -> DataFrame[TopCustomers]:
    v = value.c
    ranked = TopCustomers.extend(value, Rank.build(
        rank_in_country=tacit.row_number().over(group_by=v.country, order_by=v.revenue.desc()) + 1,
    ))
    return ranked.filter(ranked.c.rank_in_country <= n).order_by(ranked.c.country, ranked.c.rank_in_country)


def run(sources: Path, out: Path) -> tuple[DataFrame[MonthlyRevenue], DataFrame[TopCustomers]]:
    con = ibis.duckdb.connect()
    events = OrderEvents.parse(con.read_csv(sources / "orders.csv"))
    customers = Customers.parse(con.read_csv(sources / "customers.csv"))

    orders = add_metrics(keep_latest(events, key=events.c.order_id, ts=events.c.updated_at))
    facts = with_customer(delivered(orders), customers)
    monthly = monthly_revenue(facts)
    top = top_customers(customer_value(facts))

    out.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(out / "monthly_revenue.parquet")
    top.to_csv(out / "top_customers.csv")
    return monthly, top


if __name__ == "__main__":
    here = Path(__file__).parent
    monthly, top = run(Path(sys.argv[1]) if len(sys.argv) > 1 else here / "sources", here.parent / "out" / "e2e")
    print(monthly.head(6).execute())
    print(top.head(6).execute())
