"""Spelling 1: bound namespace `df.c.x` (E13 T2)."""

import tacit_r as tr
from tacit_r import DataFrame

from common import load
from schemas import CountryStats, Keyed, NetAmount, Order, RawCustomer, RawOrder


def clean_orders(orders: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = orders.filter(orders.c.status != "cancelled")
    return Order.extend(kept, NetAmount.build(net_amount=kept.c.amount - kept.c.discount.fill_null(0)))


def country_stats(orders: DataFrame[Order], customers: DataFrame[RawCustomer]) -> DataFrame[CountryStats]:
    o, c = orders.c, customers.c
    j = orders.join(customers, o.customer_id == c.customer_id)
    return CountryStats.conform(j.group_by(c.country).agg(order_count=o.order_id.count(), total_net=o.net_amount.sum()))


def latest_per_key[S: Keyed](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(tr.row_number().over(group_by=df.c.customer_id, order_by=df.c.order_ts.desc()) == 0)


def main() -> tuple[object, ...]:
    raw_o, raw_c = load()
    orders = clean_orders(RawOrder.parse(raw_o))
    stats = country_stats(orders, RawCustomer.parse(raw_c))
    latest = latest_per_key(orders)
    return (stats.order_by("country").to_pandas().round(2).to_dict("list"), latest.count().execute())


if __name__ == "__main__":
    print(main())
