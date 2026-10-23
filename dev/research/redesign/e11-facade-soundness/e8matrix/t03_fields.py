# ruff: noqa: B015, B018
"""tc.field(...) specifier vs Annotated[...] metadata: neither may break typing."""

from typing import Annotated, reveal_type

from _schemas import AnnOrders, Orders

import tacit_next as tc
from tacit_next import Column


class F1(tc.Frame):
    a: Column[float] = tc.field(ge=0, description="x")
    b: Column[int]
    c: Column[str | None] = tc.field(isin=["x"])


class F2(tc.Frame):
    a: Annotated[Column[float], tc.ge(0)]
    b: Column[int]
    c: Annotated[Column[str | None], tc.isin(["x"])]


def field_form(o: Orders, f1: F1) -> None:
    # @feature field specifier: descriptor typing
    reveal_type(o.amount)  # R: Column[float]
    reveal_type(Orders.amount)  # R: Column[float]
    reveal_type(f1.c)  # R: Column[str | None]
    # @feature field specifier: constructor
    F1(a=o.amount, b=o.order_id, c=o.note)  # ok
    F1(b=o.order_id, c=o.note)  # E: missing a (field() is not a default)
    F1(a=o.status, b=o.order_id, c=o.note)  # E: str into float
    F1(a=o.amount, c=o.note)  # E: missing b after a field() column


def annotated_form(o: Orders, a: AnnOrders, f2: F2) -> None:
    # @feature Annotated metadata: descriptor typing
    reveal_type(a.amount)  # R: Column[float]
    reveal_type(AnnOrders.discount)  # R: Column[float | None]
    reveal_type(f2.c)  # R: Column[str | None]
    # @feature Annotated metadata: constructor
    F2(a=o.amount, b=o.order_id, c=o.note)  # ok
    F2(b=o.order_id, c=o.note)  # E: missing a
    F2(a=o.status, b=o.order_id, c=o.note)  # E: str into float


def positive(c: Column[float]) -> Column[bool]:
    return c > 0


def shout(c: Column[str]) -> Column[str]:
    return c.upper()


def custom_checks() -> None:
    # @feature custom checks typed Callable[[Column[T]], Column[bool]]
    tc.field(checks=[tc.check(positive), tc.ge(0)])  # ok
    tc.check(lambda c: c > 0)  # ok: lambda
    tc.check(shout)  # E: check must return Column[bool]
    tc.field(checks=[positive])  # E: raw function, not a Constraint
