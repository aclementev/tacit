"""
TPC-H Query 1: Pricing Summary Report, ported to tacit-next (examples/tpch_q1.py).

The output is built with the frame constructor: column-valued arguments are the
GROUP BY keys, reductions are the aggregates, and every output column is checked.
"""

from datetime import date

import ibis

import tacit_next as tc
from tacit_next import Column


class LineItem(tc.Frame):
    """TPC-H lineitem table."""

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


class PricingSummary(tc.Frame):
    """Output of TPC-H Q1: pricing summary report."""

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


def filter_shipped(lineitem: LineItem) -> LineItem:
    """Filter to line items shipped before the cutoff date."""
    return lineitem.filter(lineitem.l_shipdate <= date(1998, 9, 2))


def pricing_summary_report(lineitem: LineItem) -> PricingSummary:
    """TPC-H Q1 -- pricing summary report."""
    disc_price = lineitem.l_extendedprice * (1 - lineitem.l_discount)
    return PricingSummary(
        l_returnflag=lineitem.l_returnflag,
        l_linestatus=lineitem.l_linestatus,
        sum_qty=lineitem.l_quantity.sum(),
        sum_base_price=lineitem.l_extendedprice.sum(),
        sum_disc_price=disc_price.sum(),
        sum_charge=(disc_price * (1 + lineitem.l_tax)).sum(),
        avg_qty=lineitem.l_quantity.mean(),
        avg_price=lineitem.l_extendedprice.mean(),
        avg_disc=lineitem.l_discount.mean(),
        count_order=lineitem.l_orderkey.count(),
    ).order_by(PricingSummary.l_returnflag, PricingSummary.l_linestatus)


def pipeline(path: str) -> PricingSummary:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)
    lineitem = LineItem.parse(raw)
    shipped = filter_shipped(lineitem)
    return pricing_summary_report(shipped)
