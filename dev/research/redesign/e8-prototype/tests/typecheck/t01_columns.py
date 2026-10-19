# ruff: noqa: B015, B018
"""Column[T]: access, hovers, typos, wrong methods, operators, literals."""

from datetime import date, datetime
from decimal import Decimal
from typing import reveal_type

from _schemas import Orders


def access(o: Orders) -> None:
    # @feature column access + readable hover
    reveal_type(o.amount)  # R: Column[float]
    reveal_type(o.order_id)  # R: Column[int]
    reveal_type(o.status)  # R: Column[str]
    reveal_type(o.order_ts)  # R: Column[datetime]
    reveal_type(o.price)  # R: Column[Decimal]
    reveal_type(o.discount)  # R: Column[float | None]
    reveal_type(Orders.amount)  # R: Column[float]
    # @feature typo on frame / class
    o.amout  # E: typo
    Orders.amout  # E: typo on class


def wrong_methods(o: Orders) -> None:
    # @feature wrong method for the column type
    o.amount.upper()  # E: upper on float
    o.status.mean()  # E: mean on str
    o.status.sum()  # E: sum on str
    o.order_ts.upper()  # E: upper on datetime
    o.amount.year()  # E: year on float
    o.day.hour()  # E: hour on date
    o.status.abs()  # E: abs on str
    o.order_ts.mean()  # E: mean on datetime
    o.flag.upper()  # E: upper on bool


def arithmetic(o: Orders) -> None:
    # @feature arithmetic (int vs float vs Decimal)
    reveal_type(o.amount * 2)  # R: Column[float]
    reveal_type(o.order_id + 1)  # R: Column[int]
    reveal_type(o.order_id + 1.5)  # R: Column[float]
    reveal_type(o.order_id / 2)  # R: Column[float]
    reveal_type(o.order_id * o.amount)  # R: Column[float]
    reveal_type(1 - o.amount)  # R: Column[float]
    reveal_type(o.price * 2)  # R: Column[Decimal]
    reveal_type(o.price + Decimal("1.5"))  # R: Column[Decimal]
    reveal_type(o.amount - o.amount.mean())  # R: Column[float]
    reveal_type(-o.amount)  # R: Column[float]
    reveal_type(o.status + "!")  # R: Column[str]
    o.status / o.amount  # E: str / float
    o.amount + "x"  # E: float + str
    o.status * 2  # E: str * int
    o.order_ts + 1  # E: datetime + int
    o.price + 1.5  # E: Decimal + float (needs explicit cast)


def comparisons(o: Orders) -> None:
    # @feature comparisons with literals
    reveal_type(o.amount > 5)  # R: Column[bool]
    reveal_type(o.status == "shipped")  # R: Column[bool]
    reveal_type(o.order_ts >= datetime(2024, 1, 1))  # R: Column[bool]
    reveal_type(o.order_ts >= "2024-01-01")  # R: Column[bool]
    reveal_type(o.day < date(2024, 1, 1))  # R: Column[bool]
    reveal_type(o.price > 0)  # R: Column[bool]
    reveal_type((o.amount > 5) & (o.status != "x"))  # R: Column[bool]
    reveal_type(~o.flag)  # R: Column[bool]
    o.status > 5  # E: str > int
    o.amount > "5"  # E: float > str
    reveal_type(o.status == 5)  # R: bool
    o.filter(o.status == 5)  # E: str == int falls back to object.__eq__ -> bool, rejected by filter
    o.amount & o.flag  # E: float & bool


def methods(o: Orders) -> None:
    # @feature typed methods
    reveal_type(o.status.upper())  # R: Column[str]
    reveal_type(o.status.length())  # R: Column[int]
    reveal_type(o.status.contains("a"))  # R: Column[bool]
    reveal_type(o.order_ts.year())  # R: Column[int]
    reveal_type(o.day.year())  # R: Column[int]
    reveal_type(o.order_ts.date())  # R: Column[date]
    reveal_type(o.order_ts.truncate("M"))  # R: Column[datetime]
    reveal_type(o.amount.round(2))  # R: Column[float]
    reveal_type(o.amount.round())  # R: Column[int]
    reveal_type(o.amount.abs())  # R: Column[float]
    reveal_type(o.flag.ifelse("y", "n"))  # R: Column[str]
    reveal_type(o.status.isin(["a", "b"]))  # R: Column[bool]
    o.amount.isin(["a"])  # E: isin with wrong element type
    reveal_type(o.amount.between(0, 10))  # R: Column[bool]
    o.status.between(0, 10)  # E: between with wrong bound type
    o.order_ts.truncate("M").upper()  # E: truncate keeps datetime


def reductions(o: Orders) -> None:
    # @feature reductions
    reveal_type(o.amount.mean())  # R: Scalar[float]
    reveal_type(o.order_id.mean())  # R: Scalar[float]
    reveal_type(o.order_id.sum())  # R: Scalar[int]
    reveal_type(o.amount.sum())  # R: Scalar[float]
    reveal_type(o.price.sum())  # R: Scalar[Decimal]
    reveal_type(o.status.count())  # R: Scalar[int]
    reveal_type(o.status.nunique())  # R: Scalar[int]
    reveal_type(o.status.max())  # R: Scalar[str]
    reveal_type(o.order_ts.min())  # R: Scalar[datetime]
    reveal_type((o.amount / o.order_id).mean())  # R: Scalar[float]
    reveal_type(o.amount.sum() / o.amount.count())  # R: Scalar[float]
    reveal_type(o.flag.sum())  # R: Scalar[int]
    o.amount.mean().mean()  # E: reduce a reduction


def casts(o: Orders) -> None:
    # @feature cast
    reveal_type(o.amount.cast(int))  # R: Column[int]
    reveal_type(o.status.cast(float))  # R: Column[float]
    reveal_type(o.status.try_cast(datetime))  # R: Column[datetime | None]
    reveal_type(o.amount.cast("float32"))  # R: Column[float]
    reveal_type(o.order_id.count().cast("float64"))  # R: Scalar[float]
    reveal_type(o.amount.cast("decimal(12, 2)"))  # R: Column[Any]
