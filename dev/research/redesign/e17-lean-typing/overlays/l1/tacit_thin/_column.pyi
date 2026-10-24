# L1 "names only" (E17): hand-written, no codegen.
"""`amount: Column[float]` is a descriptor; `df.c.amount` is ibis's OWN column class.

Static only. `__get__` maps the value family to ibis's class (`Column[float]` ->
`ir.FloatingColumn`); `__set__` (read by dataclass_transform, so it types the
`build(...)` keywords) accepts any ibis expression or a Python literal of T. Nullability (`Column[float | None]`) is not tracked statically: it maps to
the same ibis class and is enforced by validation at runtime only.
"""

from datetime import date as _date, datetime as _datetime, time as _time
from decimal import Decimal
from typing import Any, Generic, TypeVar, overload

import ibis.expr.types as ir
from ibis.common.deferred import Deferred

T_co = TypeVar("T_co", covariant=True)

class Column(Generic[T_co]):
    """Declares a column of value type T (`Column[float]`, `Column[str | None]`)."""

    @overload
    def __get__(self, obj: None, owner: Any, /) -> Deferred: ...
    @overload
    def __get__(self: Column[bool | None], obj: object, owner: Any, /) -> ir.BooleanColumn: ...
    @overload
    def __get__(self: Column[int | None], obj: object, owner: Any, /) -> ir.IntegerColumn: ...
    @overload
    def __get__(self: Column[float | None], obj: object, owner: Any, /) -> ir.FloatingColumn: ...
    @overload
    def __get__(self: Column[Decimal | None], obj: object, owner: Any, /) -> ir.DecimalColumn: ...
    @overload
    def __get__(self: Column[str | None], obj: object, owner: Any, /) -> ir.StringColumn: ...
    @overload
    def __get__(self: Column[_datetime | None], obj: object, owner: Any, /) -> ir.TimestampColumn: ...
    @overload
    def __get__(self: Column[_date | None], obj: object, owner: Any, /) -> ir.DateColumn: ...
    @overload
    def __get__(self: Column[_time | None], obj: object, owner: Any, /) -> ir.TimeColumn: ...
    @overload
    def __get__(self, obj: object, owner: Any, /) -> ir.Column: ...

    # Not per family: pyright and mypy ignore an OVERLOADED __set__ when synthesizing the
    # dataclass_transform __init__ (mypy: "Unsupported __set__"), see scratch/q1.py. So
    # build(...) accepts any ibis expression or a literal of T; families are checked at runtime.
    def __set__(self, obj: object, value: ir.Value | T_co | Deferred, /) -> None: ...  # type: ignore[misc]

class Scalar(Generic[T_co]):
    """Unused marker kept so the shared Table stub's widened parameters resolve."""

def lit(value: Any, /, type: Any = None) -> ir.Scalar: ...
def cases(*branches: tuple[ir.BooleanValue, Any], else_: Any) -> ir.Value: ...
def row_number() -> ir.IntegerColumn: ...
def as_ibis[V: ir.Value](col: V, /) -> V: ...
def as_column[V: ir.Value](expr: V, /) -> V: ...

# handle-parameter spellings (Column[T] is a declaration, not an expression type, in L1)
AnyCol = ir.Column
TsCol = ir.TimestampColumn
