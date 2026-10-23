"""Spelling 2: owner-typed unbound class refs `Schema.x` (E14)."""

import tacit_r as tr
from tacit_r import DataFrame

from common import load
from schemas import CountryStats, Keyed, NetAmount, Order, RawCustomer, RawOrder


def clean_orders(orders: DataFrame[RawOrder]) -> DataFrame[Order]:
    kept = orders.filter(RawOrder.status != "cancelled")
    return Order.extend(kept, NetAmount.build(kept, net_amount=RawOrder.amount - RawOrder.discount.fill_null(0)))


def country_stats(orders: DataFrame[Order], customers: DataFrame[RawCustomer]) -> DataFrame[CountryStats]:
    j = orders.join(customers, [(Order.customer_id, RawCustomer.customer_id)])
    return CountryStats.conform(
        j.group_by(RawCustomer.country).agg(order_count=Order.order_id.count(), total_net=Order.net_amount.sum())
    )


def latest_per_key[S: Keyed](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(tr.row_number().over(group_by=Keyed.customer_id, order_by=Keyed.order_ts.desc()) == 0)


def main() -> tuple[object, ...]:
    raw_o, raw_c = load()
    orders = clean_orders(RawOrder.parse(raw_o))
    stats = country_stats(orders, RawCustomer.parse(raw_c))
    latest = latest_per_key(orders)
    return (stats.order_by("country").to_pandas().round(2).to_dict("list"), latest.count().execute())


if __name__ == "__main__":
    print(main())
