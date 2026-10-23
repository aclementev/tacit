# ruff: noqa
"""FAMILY_LIE severity: statically Column[Decimal]/Column[int], runtime float64. Caught where?"""
from decimal import Decimal

import ibis
import tacit_next as tc
from tacit_next import Column


class P(tc.Frame):
    price: Column[Decimal] = tc.field(dtype="decimal(12, 2)")
    qty: Column[int]


class Unit(tc.Frame):
    unit_price: Column[Decimal]   # E8 facade: price / price is Column[Decimal]; ibis: float64
    rounded: Column[int]          # E8 facade: qty.round(1) is Column[int]; ibis: float64


def unit(p: P) -> Unit:
    return Unit(unit_price=p.price / p.price, rounded=p.qty.round(1))  # L1 type-checks clean under E8


if __name__ == "__main__":
    raw = ibis.memtable({"price": [Decimal("2.50")], "qty": [3]}, schema={"price": "decimal(12, 2)", "qty": "int64"})
    try:
        print(unit(P.parse(raw)).to_pyarrow())
    except Exception as e:
        print(type(e).__name__, str(e)[:300])
