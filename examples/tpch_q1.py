"""
TPC-H Query 1: Pricing Summary Report

Demonstrates tacit with an analytics workload.
Schemas define the contract for a well-known benchmark query.
"""
import ibis
import tacit


class LineItem(tacit.Schema):
    """TPC-H lineitem table."""
    l_orderkey: int
    l_partkey: int
    l_suppkey: int
    l_linenumber: int
    l_quantity: float
    l_extendedprice: float
    l_discount: float
    l_tax: float
    l_returnflag: str
    l_linestatus: str
    l_shipdate: str
    l_commitdate: str
    l_receiptdate: str


class PricingSummary(tacit.Schema):
    """Output of TPC-H Q1: pricing summary report."""
    l_returnflag: str
    l_linestatus: str
    sum_qty: float
    sum_base_price: float
    sum_disc_price: float
    sum_charge: float
    avg_qty: float
    avg_price: float
    avg_disc: float
    count_order: int


@tacit.contract
def pricing_summary_report(
    lineitem: tacit.DataFrame[LineItem],
) -> tacit.DataFrame[PricingSummary]:
    """TPC-H Q1 — pricing summary report.

    The @tacit.contract decorator enforces input and output
    schema contracts automatically.
    """
    return (
        lineitem
        .filter(lineitem.l_shipdate <= "1998-09-02")
        .group_by("l_returnflag", "l_linestatus")
        .agg(
            sum_qty=lineitem.l_quantity.sum(),
            sum_base_price=lineitem.l_extendedprice.sum(),
            sum_disc_price=(
                lineitem.l_extendedprice * (1 - lineitem.l_discount)
            ).sum(),
            sum_charge=(
                lineitem.l_extendedprice
                * (1 - lineitem.l_discount)
                * (1 + lineitem.l_tax)
            ).sum(),
            avg_qty=lineitem.l_quantity.mean(),
            avg_price=lineitem.l_extendedprice.mean(),
            avg_disc=lineitem.l_discount.mean(),
            count_order=lineitem.l_orderkey.count(),
        )
        .order_by("l_returnflag", "l_linestatus")
    )


def pipeline(path: str) -> tacit.DataFrame[PricingSummary]:
    con = ibis.duckdb.connect()
    raw = con.read_csv(path)
    lineitem = LineItem.parse(raw)
    return pricing_summary_report(lineitem)
