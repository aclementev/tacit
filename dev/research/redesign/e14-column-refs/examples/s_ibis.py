"""Spelling 4: plain ibis `_.x` (untyped baseline, no schemas)."""

import ibis
import ibis.expr.types as ir
from ibis import _

from common import load


def clean_orders(orders: ir.Table) -> ir.Table:
    kept = orders.filter(_.status != "cancelled")
    return kept.mutate(net_amount=_.amount - _.discount.fill_null(0))


def country_stats(orders: ir.Table, customers: ir.Table) -> ir.Table:
    j = orders.join(customers, "customer_id")
    return j.group_by(_.country).agg(order_count=_.order_id.count(), total_net=_.net_amount.sum())


def latest_per_key(df: ir.Table, key: str = "customer_id", ts: str = "order_ts") -> ir.Table:
    return df.filter(ibis.row_number().over(group_by=_[key], order_by=_[ts].desc()) == 0)


def main() -> tuple[object, ...]:
    raw_o, raw_c = load()
    orders = clean_orders(raw_o)
    stats = country_stats(orders, raw_c)
    latest = latest_per_key(orders)
    return (stats.order_by("country").to_pandas().round(2).to_dict("list"), latest.count().execute())


if __name__ == "__main__":
    print(main())
