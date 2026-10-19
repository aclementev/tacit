# ruff: noqa: B015, B018
"""Nullability in the type: Column[T | None]."""

from typing import reveal_type

from _schemas import NetAmount, Orders

from tacit_next import Column


def takes_float(c: Column[float]) -> None: ...


def solve(o: Orders) -> None:
    # @feature (a) fill_null solves T from Column[T | None]
    reveal_type(o.discount.fill_null(0.0))  # R: Column[float]
    reveal_type(o.discount.fill_null(0))  # R: Column[float]
    reveal_type(o.note.fill_null("-"))  # R: Column[str]
    reveal_type(o.amount.fill_null(0.0))  # R: Column[float]
    reveal_type(o.discount.fill_null(o.amount))  # R: Column[float]
    o.note.fill_null(0)  # E: fill a str column with an int


def null_safety(o: Orders) -> None:
    # @feature (b) nullable expression into a non-null output column
    NetAmount(net_amount=o.discount)  # E: nullable into non-null
    NetAmount(net_amount=o.amount - o.discount)  # E: nullable arithmetic into non-null
    NetAmount(net_amount=o.amount - o.discount.fill_null(0))  # ok
    takes_float(o.discount)  # E: nullable into Column[float] parameter
    takes_float(o.amount)  # ok


def propagation(o: Orders) -> None:
    # @feature (c) nullability propagates through operators and methods
    reveal_type(o.amount + o.discount)  # R: Column[float | None]
    reveal_type(o.discount * 2)  # R: Column[float | None]
    reveal_type(o.discount / o.amount)  # R: Column[float | None]
    reveal_type(o.note.upper())  # R: Column[str | None]
    reveal_type(o.note.length())  # R: Column[int | None]
    reveal_type(o.discount.abs())  # R: Column[float | None]
    reveal_type(o.discount.sum())  # R: Scalar[float]
    reveal_type(o.discount > 0)  # R: Column[bool]
    reveal_type(o.discount.isnull())  # R: Column[bool]
