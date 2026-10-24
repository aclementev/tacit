"""TPC-H Q1 in the T2 spelling: DataFrame[S] + typed `df.c` namespace (E13 variant)."""

from datetime import date

import ibis

import tacit_t2 as tc2
from tacit_t2 import Column, DataFrame


class LineItem(tc2.Schema):
    l_orderkey: Column[int]
    l_partkey: Column[int]
    l_suppkey: Column[int]
    l_linenumber: Column[int]
    l_quantity: Column[float]
    l_extendedprice: Column[float]
    l_discount: Column[float]
    l_tax: Column[float]
    l_returnflag: Column[str]
    l_linestatus: Column[str]
    l_shipdate: Column[date]
    l_commitdate: Column[date]
    l_receiptdate: Column[date]


class PricingSummary(tc2.Schema):
    l_returnflag: Column[str]
    l_linestatus: Column[str]
    sum_qty: Column[float]
    sum_base_price: Column[float]
    sum_disc_price: Column[float]
    sum_charge: Column[float]
    avg_qty: Column[float]
    avg_price: Column[float]
    avg_disc: Column[float]
    count_order: Column[int]


def filter_shipped(lineitem: DataFrame[LineItem]) -> DataFrame[LineItem]:
    return lineitem.filter(lineitem.c.l_shipdate <= date(1998, 9, 2))


def pricing_summary_report(lineitem: DataFrame[LineItem]) -> DataFrame[PricingSummary]:
    li = lineitem.c
    disc_price = li.l_extendedprice * (1 - li.l_discount)
    return PricingSummary.build(
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


def pipeline(path: str) -> DataFrame[PricingSummary]:
    con = ibis.duckdb.connect()
    return pricing_summary_report(filter_shipped(LineItem.parse(con.read_csv(path))))


if __name__ == "__main__":
    import sys

    print(pipeline(sys.argv[1]).to_pandas())
