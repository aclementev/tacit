import datetime as dt
from pathlib import Path
from typing import Annotated, TypeVar

import ibis
from ibis import _
import ibis.expr.types as ir
import tacit
from tacit import Check, Nullable

HERE = Path(__file__).parent.parent


class RawCustomer(tacit.Schema):
    customer_id: int
    name: str
    email: Annotated[str, Check.str_matches(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    country: Annotated[str, Check.str_length(exact_value=2)]
    signup_date: dt.date


class RawOrder(tacit.Schema):
    order_id: int
    customer_id: int
    order_ts: dt.datetime
    status: Annotated[str, Check.isin(["pending", "shipped", "cancelled"])]
    amount: Annotated[float, Check.ge(0)]
    discount: Annotated[float, Nullable(), Check.ge(0)]


class Order(RawOrder):
    net_amount: float


class CountryMonthStats(tacit.Schema):
    country: str
    order_month: dt.date
    order_count: int
    total_net: float
    avg_net: float
    distinct_customers: int


@tacit.contract
def clean_orders(orders: tacit.DataFrame[RawOrder]) -> tacit.DataFrame[Order]:
    kept = orders.filter(orders.status != "cancelled")
    return kept


@tacit.contract(returns=CountryMonthStats)
def country_month_stats(
    orders: tacit.DataFrame[Order], customers: tacit.DataFrame[RawCustomer]
) -> ir.Table:
    joined = orders.join(customers, "customer_id")
    return joined.group_by(
        country=joined.country,
        order_month=_.order_ts.truncate("M").date(),
    ).agg(
        order_count=joined.order_id.count(),
        total_net=_.net_amount.sum(),
        avg_net=_.net_amount.mean(),
        distinct_customers=joined.customer_id.nunique(),
    )


S = TypeVar("S", bound=tacit.Schema)


def latest_per_key(
    df: tacit.DataFrame[S], schema: type[S], key: str, ts: str
) -> tacit.DataFrame[S]:
    ranked = df.mutate(
        _rn=ibis.row_number().over(group_by=key, order_by=ibis.desc(ts))
    )
    return schema.cast(ranked.filter(_._rn == 0).drop("_rn"))


def main() -> None:
    con = ibis.duckdb.connect()
    customers = RawCustomer.parse(con.read_csv(HERE / "customers.csv"))
    orders = RawOrder.parse(con.read_csv(HERE / "orders.csv"))
    cleaned = clean_orders(orders)
    stats = country_month_stats(cleaned, customers)
    latest = latest_per_key(cleaned, Order, "customer_id", "order_ts")
    print(latest.count().execute())
    print(stats.order_by("country", "order_month").to_pandas())


if __name__ == "__main__":
    main()
