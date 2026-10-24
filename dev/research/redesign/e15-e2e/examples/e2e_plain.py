"""Monthly revenue and top customers for an e-commerce shop -- plain ibis + pandera.

Same pipeline and outputs as e2e.py. Contracts are pandera models, validated at ingestion
and at the one boundary that e2e.py validates (customer_value).
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import ibis
import ibis.expr.types as ir
import pandera.ibis as pa
from ibis import _

COUNTRIES = ["ES", "FR", "DE", "IT", "PT"]


# --- contracts -----------------------------------------------------------------------------
class Customers(pa.DataFrameModel):
    """CRM export, one row per customer."""

    customer_id: int = pa.Field(unique=True)
    email: str = pa.Field(str_matches=r"^[^@\s]+@[^@\s]+\.\w+$")
    country: str = pa.Field(isin=COUNTRIES)
    segment: str = pa.Field(isin=["consumer", "business"], nullable=True)
    signup_date: date


class OrderEvents(pa.DataFrameModel):
    """Order service events: an order appears once per status change."""

    order_id: int
    customer_id: int
    status: str = pa.Field(isin=["shipped", "delivered", "cancelled", "returned"])
    channel: str = pa.Field(isin=["web", "app"])
    amount: float = pa.Field(ge=0)
    discount: float = pa.Field(ge=0, nullable=True)
    ordered_at: datetime
    delivered_at: datetime = pa.Field(nullable=True)
    updated_at: datetime


class CustomerValue(pa.DataFrameModel):
    customer_id: int
    country: str
    orders: int
    revenue: float
    first_month: date
    share_of_country: float = pa.Field(ge=0, le=1)


# --- steps ---------------------------------------------------------------------------------
def keep_latest(t: ir.Table, key: str, ts: str) -> ir.Table:
    """The most recent row per key."""
    return t.filter(ibis.row_number().over(group_by=key, order_by=ibis.desc(ts)) == 0)


def add_metrics(events: ir.Table) -> ir.Table:
    return events.mutate(
        net_amount=_.amount - _.discount.fill_null(0),
        order_month=_.ordered_at.truncate("M").date(),
    )


def delivered(orders: ir.Table) -> ir.Table:
    return orders.filter(_.status == "delivered").mutate(
        delivery_hours=_.delivered_at.delta(_.ordered_at, unit="hour"),
    )


def with_customer(orders: ir.Table, customers: ir.Table) -> ir.Table:
    return orders.join(customers, "customer_id").select(
        "order_id", "customer_id", "country", "channel", "order_month", "net_amount", "delivery_hours",
        segment=_.segment.fill_null("unknown"),
    )


def monthly_revenue(facts: ir.Table) -> ir.Table:
    return facts.group_by("country", "order_month").agg(
        orders=_.order_id.count(),
        app_orders=_.order_id.count(where=_.channel == "app"),
        revenue=_.net_amount.sum(),
        avg_order_value=_.net_amount.mean(),
        avg_delivery_hours=_.delivery_hours.mean(),
    ).order_by("country", "order_month")


def customer_value(facts: ir.Table) -> ir.Table:
    per_customer = facts.group_by("customer_id", "country").agg(
        orders=_.order_id.count(), revenue=_.net_amount.sum(), first_month=_.order_month.min()
    )
    return CustomerValue.validate(
        per_customer.mutate(share_of_country=_.revenue / _.revenue.sum().over(group_by="country"))
    )


def top_customers(value: ir.Table, n: int = 3) -> ir.Table:
    ranked = value.mutate(rank_in_country=ibis.row_number().over(group_by="country", order_by=ibis.desc("revenue")) + 1)
    return ranked.filter(_.rank_in_country <= n).order_by("country", "rank_in_country")


def read(con: ibis.BaseBackend, path: Path) -> ir.Table:
    # pandera's ibis backend compares dtypes exactly: duckdb's timestamp(6) fails `datetime`
    t = con.read_csv(path)
    return t.cast({c: "timestamp" for c, d in t.schema().items() if d.is_timestamp()})


def run(sources: Path, out: Path) -> tuple[ir.Table, ir.Table]:
    con = ibis.duckdb.connect()
    events = OrderEvents.validate(read(con, sources / "orders.csv"))
    customers = Customers.validate(read(con, sources / "customers.csv"))

    orders = add_metrics(keep_latest(events, key="order_id", ts="updated_at"))
    facts = with_customer(delivered(orders), customers)
    monthly = monthly_revenue(facts)
    top = top_customers(customer_value(facts))

    out.mkdir(parents=True, exist_ok=True)
    monthly.to_parquet(out / "monthly_revenue.parquet")
    top.to_csv(out / "top_customers.csv")
    return monthly, top


if __name__ == "__main__":
    here = Path(__file__).parent
    monthly, top = run(Path(sys.argv[1]) if len(sys.argv) > 1 else here / "sources", here.parent / "out" / "e2e_plain")
    print(monthly.head(6).execute())
    print(top.head(6).execute())
