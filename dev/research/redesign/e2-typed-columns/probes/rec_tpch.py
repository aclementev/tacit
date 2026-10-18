"""Sketch: examples/tpch_q1.py in the recommended design (runs on duckdb)."""

from typing import reveal_type

import ibis

import proto.newtacit as tacit


class LineItem(tacit.Frame):
    l_orderkey: tacit.Int64
    l_partkey: tacit.Int64
    l_suppkey: tacit.Int64
    l_linenumber: tacit.Int64
    l_quantity: tacit.Float64
    l_extendedprice: tacit.Float64
    l_discount: tacit.Float64
    l_tax: tacit.Float64
    l_returnflag: tacit.String
    l_linestatus: tacit.String
    l_shipdate: tacit.String
    l_commitdate: tacit.String
    l_receiptdate: tacit.String


class PricingSummary(tacit.Frame):
    l_returnflag: tacit.String
    l_linestatus: tacit.String
    sum_qty: tacit.Float64
    sum_base_price: tacit.Float64
    sum_disc_price: tacit.Float64
    sum_charge: tacit.Float64
    avg_qty: tacit.Float64
    avg_price: tacit.Float64
    avg_disc: tacit.Float64
    count_order: tacit.Int64


def filter_shipped(li: LineItem) -> LineItem:
    return li.filter(li.l_shipdate <= "1998-09-02")  # filter() -> Self: schema kept


def pricing_summary_report(li: LineItem) -> PricingSummary:
    disc_price = li.l_extendedprice * (1 - li.l_discount)
    reveal_type(disc_price)
    return PricingSummary(  # reductions + group keys => implicit GROUP BY
        l_returnflag=li.l_returnflag,
        l_linestatus=li.l_linestatus,
        sum_qty=li.l_quantity.sum(),
        sum_base_price=li.l_extendedprice.sum(),
        sum_disc_price=disc_price.sum(),
        sum_charge=(disc_price * (1 + li.l_tax)).sum(),
        avg_qty=li.l_quantity.mean(),
        avg_price=li.l_extendedprice.mean(),
        avg_disc=li.l_discount.mean(),
        count_order=li.l_orderkey.count(),
    ).order_by(PricingSummary.l_returnflag, PricingSummary.l_linestatus)


def pipeline(path: str) -> PricingSummary:
    raw = ibis.duckdb.connect().read_csv(path)
    return pricing_summary_report(filter_shipped(LineItem.parse(raw)))


if __name__ == "__main__":
    out = pipeline("../../../../../examples/data/lineitem.csv")
    reveal_type(out)
    print(out.execute().to_string())
