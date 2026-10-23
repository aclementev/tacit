# ruff: noqa: B015, B018
"""E13: column names that collide with ibis Table members (runtime raises at class creation)."""

from typing import reveal_type

import tacit_thin as tc
from tacit_thin import Column


class BadCount(tc.Frame):
    # @feature collision with an ibis method is flagged statically
    count: Column[int]  # E: shadows Table.count (runtime TypeError too)


class BadSchema(tc.Frame):
    schema: Column[str]  # E: shadows Table.schema


class BadColumns(tc.Frame):
    columns: Column[str]  # E: shadows Table.columns (property)


class Fine(tc.Frame):
    # @feature the escape: rename the attribute, keep the physical name
    count_: Column[int] = tc.field(name="count")
    view_: Column[str] = tc.field(name="view")


def use(f: Fine) -> None:
    reveal_type(f.count_)  # R: Column[int]
    reveal_type(f["count"])  # R: Column
    reveal_type(f.count())  # R: IntegerScalar
