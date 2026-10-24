# ruff: noqa: B015, B018
"""E8/E11 column-level cases in the T2 spelling (`o.c.x`). `# E: [cat]` = a bug; unmarked = correct code."""

from datetime import date, datetime
from decimal import Decimal
from typing import reveal_type

import ibis

import tacit_t2 as tc2
from tacit_t2 import Column, DataFrame


class Orders(tc2.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    day: Column[date]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]
    price: Column[Decimal]
    flag: Column[bool]
    note: Column[str | None]


class Proj(tc2.Schema):
    order_id: Column[int]
    amount: Column[float]
    label: Column[str]


class Net(tc2.Schema):
    net_amount: Column[float]


class Stats(tc2.Schema):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class Day(tc2.Schema):
    day: Column[date]


def access(o: DataFrame[Orders]) -> None:
    # @feature typed access (precision of the revealed type)
    reveal_type(o.c.amount)  # R: Column[float] ;; l1,l2=FloatingColumn
    reveal_type(o.c.order_id)  # R: Column[int] ;; l1,l2=IntegerColumn
    reveal_type(o.c.status)  # R: Column[str] ;; l1,l2=StringColumn
    reveal_type(o.c.order_ts)  # R: Column[datetime] ;; l1,l2=TimestampColumn
    reveal_type(o.c.price)  # R: Column[Decimal] ;; l1,l2=DecimalColumn
    reveal_type(o.c.discount)  # R: Column[float | None] ;; l1,l2=FloatingColumn
    # @feature typos
    o.c.amout  # E: [typo-c] typo in namespace
    o.c.discont.fill_null(0)  # E: [typo-c] typo in namespace
    o.amout  # E: [typo-df] attribute typo on the frame
    o.status  # E: [typo-df] column read as a table attribute


def wrong_methods(o: DataFrame[Orders]) -> None:
    # @feature wrong method for the column's family
    o.c.amount.upper()  # E: [wrong-method] upper on float
    o.c.status.mean()  # E: [wrong-method] mean on str
    o.c.status.sum()  # E: [wrong-method] sum on str
    o.c.order_ts.upper()  # E: [wrong-method] upper on datetime
    o.c.amount.year()  # E: [wrong-method] year on float
    o.c.day.hour()  # E: [wrong-method] hour on date
    o.c.status.abs()  # E: [wrong-method] abs on str
    o.c.order_ts.mean()  # E: [wrong-method] mean on datetime
    o.c.flag.upper()  # E: [wrong-method] upper on bool
    o.c.order_ts.truncate("M").upper()  # E: [wrong-method] truncate keeps datetime
    o.c.amount.mean().mean()  # E: [wrong-method] reduce a reduction


def bad_operators(o: DataFrame[Orders]) -> None:
    # @feature operators between incompatible families
    o.c.status / o.c.amount  # E: [bad-operator] str / float
    o.c.amount + "x"  # E: [bad-operator] float + str
    o.c.order_ts + 1  # E: [bad-operator] datetime + int
    o.c.status > 5  # E: [bad-operator] str > int
    o.c.amount > "5"  # E: [bad-operator] float > str
    o.c.amount & o.c.flag  # E: [bad-operator] float & bool


def comparisons(o: DataFrame[Orders]) -> None:
    # @feature comparisons with Python literals (correct code)
    o.filter(o.c.amount > 5)
    o.filter(o.c.status == "shipped")
    o.filter(o.c.order_ts >= datetime(2024, 1, 1))
    o.filter(o.c.day < date(2024, 1, 1))
    o.filter(o.c.price > 0)
    o.filter((o.c.amount > 5) & (o.c.status != "x"))
    o.filter(~o.c.flag)
    o.filter(o.c.status.isin(["a", "b"]))
    o.filter(o.c.amount.between(0, 10))
    o.filter(o.c.discount.isnull())


def arithmetic(o: DataFrame[Orders]) -> None:
    # @feature arithmetic and reductions (correct code)
    reveal_type((o.c.amount / o.c.order_id).mean())  # R: Scalar[float] ;; l1=NumericScalar ;; l2=NumericScalar
    reveal_type(o.c.amount.sum() / o.c.amount.count())  # R: Scalar[float] ;; l1,l2=NumericValue
    reveal_type(o.c.amount - o.c.amount.mean())  # R: Column[float] ;; l1=NumericValue ;; l2=NumericColumn
    reveal_type(1 - o.c.amount)  # R: Column[float] ;; l1=NumericValue ;; l2=NumericColumn
    reveal_type(o.c.order_id + 1)  # R: Column[int] ;; l1=NumericValue ;; l2=IntegerColumn
    reveal_type(o.c.amount.max())  # R: Scalar[float] ;; l1=Scalar ;; l2=FloatingScalar
    reveal_type(o.c.order_id.sum())  # R: Scalar[int] ;; l1=NumericScalar ;; l2=IntegerScalar
    reveal_type(o.c.discount.fill_null(0))  # R: Column[float] ;; l1,l2=FloatingColumn
    reveal_type(o.c.status.upper())  # R: Column[str] ;; l1,l2=StringColumn
    reveal_type(o.c.status.length())  # R: Column[int] ;; l1=IntegerValue ;; l2=IntegerColumn
    reveal_type(o.c.order_ts.truncate("M").date())  # R: Column[date] ;; l1=DateValue ;; l2=DateColumn
    reveal_type(o.c.amount.round(2))  # R: Column[float] ;; l1=NumericValue ;; l2=NumericColumn
    reveal_type(o.c.flag.ifelse("y", "n"))  # R: Column[str] ;; l1=Value ;; l2=StringColumn
    reveal_type(o.c.order_ts.year())  # R: Column[int] ;; l1=IntegerValue ;; l2=IntegerColumn
    o.c.amount.log()
    o.c.amount.cumsum()
    o.c.status.split(",")
    o.c.amount.mean(where=o.c.flag)


def construction(o: DataFrame[Orders]) -> None:
    # @feature build(): names
    Proj.build(order_id=o.c.order_id, amount=o.c.amount)  # E: [build-missing] missing label
    Proj.build(order_id=o.c.order_id, amount=o.c.amount, label=o.c.status, bogus=o.c.amount)  # E: [build-extra] extra
    Proj.build(o.c.order_id, o.c.amount, o.c.status)  # E: [build-missing] positional arguments
    # @feature build(): value family
    Proj.build(order_id=o.c.order_id, amount=o.c.status, label=o.c.status)  # E: [build-family] str into float
    Proj.build(order_id=o.c.order_id, amount=o.c.amount, label=o.c.amount)  # E: [build-family] float into str
    Day.build(day=o.c.order_ts.year())  # E: [build-family] int into date
    Proj.build(order_id=o.c.order_id, amount=o.c.amount, label=3)  # E: [build-family] int literal into str
    Stats.build(status=o.c.status, n=o.c.order_id.count(), total=o.c.status.max())  # E: [build-family] str max into float
    # @feature build(): int vs float output
    Proj.build(order_id=o.c.amount, amount=o.c.amount, label=o.c.status)  # E: [int-float] float into int
    Stats.build(status=o.c.status, n=o.c.amount.sum(), total=o.c.amount.sum())  # E: [int-float] float sum into int
    Stats.build(status=o.c.status, n=o.c.order_id.mean(), total=o.c.amount.sum())  # E: [int-float] mean into int
    # @feature build(): nullable into non-null
    Net.build(net_amount=o.c.discount)  # E: [nullable] nullable into non-null
    Net.build(net_amount=o.c.amount - o.c.discount)  # E: [nullable] nullable arithmetic into non-null
    # @feature build(): correct code
    Proj.build(order_id=o.c.order_id, amount=o.c.order_id, label=o.c.status)
    Proj.build(order_id=o.c.order_id, amount=o.c.amount, label="web")
    Proj.build(order_id=o.c.order_id, amount=o.c.amount * 2, label=o.c.status.upper())
    Net.build(net_amount=o.c.amount * (1 - o.c.discount.fill_null(0)))
    Net.build(net_amount=o.c.amount - o.c.discount.fill_null(0.0))
    Stats.build(status=o.c.status, n=o.c.order_id.count(), total=o.c.amount.mean())
    Stats.build(status=o.c.status, n=o.c.order_id.sum(), total=o.c.amount.max())
    Stats.build(status=o.c.status, n=o.c.order_id.nunique(), total=(o.c.amount / o.c.order_id).mean())
    Stats.build(status=o.c.status.upper(), n=o.c.order_id.count(where=o.c.flag), total=o.c.amount.sum())
    Day.build(day=o.c.order_ts.date())
    Proj.build(order_id=o.c.order_id + 1, amount=o.c.amount.round(2), label=tc2.cases((o.c.flag, "y"), else_="n"))
    Proj.build(order_id=o.c.order_id, amount=o.c.amount, label=ibis.cases((o.c.flag, "y"), else_="n"))
