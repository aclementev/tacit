"""Reference: the same three examples in plain ibis 12 (what E13's T2 compiles to)."""

from __future__ import annotations

from datetime import date

import ibis
import ibis.expr.types as ir
from ibis import _


def iris(t: ir.Table) -> ir.Table:
    f = t.mutate(
        sepal_ratio=_.sepal_length / _.sepal_width,
        petal_ratio=_.petal_length / _.petal_width,
        petal_area=_.petal_length * _.petal_width,
    )
    species = ibis.cases((f.petal_length < 2.5, "setosa"), (f.petal_length < 4.8, "versicolor"), else_="virginica")
    return f.mutate(predicted_species=species)


def tpch_q1(li: ir.Table) -> ir.Table:
    s = li.filter(li.l_shipdate <= date(1998, 9, 2))
    disc = s.l_extendedprice * (1 - s.l_discount)
    return (
        s.group_by(["l_returnflag", "l_linestatus"])
        .aggregate(
            sum_qty=s.l_quantity.sum(),
            sum_base_price=s.l_extendedprice.sum(),
            sum_disc_price=disc.sum(),
            sum_charge=(disc * (1 + s.l_tax)).sum(),
            avg_qty=s.l_quantity.mean(),
            avg_price=s.l_extendedprice.mean(),
            avg_disc=s.l_discount.mean(),
            count_order=s.l_orderkey.count(),
        )
        .order_by(["l_returnflag", "l_linestatus"])
    )


def ecommerce(orders: ir.Table, customers: ir.Table) -> dict[str, ir.Table]:
    kept = orders.filter(orders.status != "cancelled")
    cleaned = kept.mutate(net_amount=kept.amount - kept.discount.fill_null(0))
    j = cleaned.join(customers, "customer_id")
    stats = j.group_by(country=j.country, order_month=j.order_ts.truncate("M").date()).aggregate(
        order_count=j.order_id.count(),
        total_net=j.net_amount.sum(),
        avg_net=j.net_amount.mean(),
        distinct_customers=j.customer_id.nunique(),
    )
    by = cleaned.group_by("status").aggregate(orders=_.order_id.count(), revenue=_.net_amount.sum())
    status = by.mutate(share=_.revenue / _.revenue.sum())
    rn = ibis.row_number().over(group_by=cleaned.customer_id, order_by=cleaned.order_ts.desc())
    latest = cleaned.filter(rn == 0)
    latest_max = cleaned.filter(cleaned.order_ts == cleaned.order_ts.max().over(group_by=cleaned.customer_id))
    checks = customers.aggregate(
        bad_email=(~customers.email.re_search(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")).cast("int64").sum(),
        bad_country=(customers.country.length() != 2).cast("int64").sum(),
    )
    return {"stats": stats, "status": status, "latest": latest, "latest_max": latest_max, "checks": checks}
