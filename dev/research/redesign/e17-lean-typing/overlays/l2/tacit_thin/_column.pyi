# L2 "ibis's types, cleaned" (E17): hand-written descriptor over the generated `_ibis_cols.pyi` mirror.
"""`amount: Column[float]` is a descriptor; `df.c.amount` is the clean mirror of ibis's class.

Static only. `__get__` maps the value family to the mirror class (`Column[float]` ->
`_ibis_cols.FloatingColumn`, a cleaned copy of `ir.FloatingColumn`); `__set__` (read by
dataclass_transform, so it types the `build(...)` keywords) accepts any mirror value whose
phantom family marker `_Fam[T]` matches, or a Python literal of T. Nullability is not
tracked statically (`Column[float | None]` maps to the same class): validation only.
"""

from datetime import date as _date, datetime as _datetime, time as _time
from decimal import Decimal
from typing import Any, Generic, TypeVar, overload

import ibis.expr.types as ir
from ibis.common.deferred import Deferred

from . import _ibis_cols as c

T_co = TypeVar("T_co", covariant=True)
V = TypeVar("V")

class Column(Generic[T_co]):
    """Declares a column of value type T (`Column[float]`, `Column[str | None]`)."""

    @overload
    def __get__(self, obj: None, owner: Any, /) -> Deferred: ...
    @overload
    def __get__(self: Column[bool | None], obj: object, owner: Any, /) -> c.BooleanColumn: ...
    @overload
    def __get__(self: Column[int | None], obj: object, owner: Any, /) -> c.IntegerColumn: ...
    @overload
    def __get__(self: Column[float | None], obj: object, owner: Any, /) -> c.FloatingColumn: ...
    @overload
    def __get__(self: Column[Decimal | None], obj: object, owner: Any, /) -> c.DecimalColumn: ...
    @overload
    def __get__(self: Column[str | None], obj: object, owner: Any, /) -> c.StringColumn: ...
    @overload
    def __get__(self: Column[_datetime | None], obj: object, owner: Any, /) -> c.TimestampColumn: ...
    @overload
    def __get__(self: Column[_date | None], obj: object, owner: Any, /) -> c.DateColumn: ...
    @overload
    def __get__(self: Column[_time | None], obj: object, owner: Any, /) -> c.TimeColumn: ...
    @overload
    def __get__(self, obj: object, owner: Any, /) -> c.Column: ...
    # one signature, no overloads (pyright/mypy ignore an overloaded __set__): the phantom marker
    # carries the family, so `Net.build(net_amount=o.c.status)` is `_Fam[str]` vs `_Fam[float]`.
    def __set__(self, obj: object, value: c._Fam[T_co] | T_co | Deferred, /) -> None: ...  # type: ignore[misc]

class Scalar(Generic[T_co]):
    """Unused marker kept so the shared Table stub's widened parameters resolve."""

def lit(value: Any, /, type: Any = None) -> ir.Scalar: ...
@overload
def cases(*branches: tuple[ir.BooleanValue, str | ir.StringValue], else_: str | ir.StringValue) -> c.StringColumn: ...
@overload
def cases(*branches: tuple[ir.BooleanValue, int | ir.IntegerValue], else_: int | ir.IntegerValue) -> c.IntegerColumn: ...
@overload
def cases(*branches: tuple[ir.BooleanValue, float | ir.NumericValue], else_: float | ir.NumericValue) -> c.FloatingColumn: ...
@overload
def cases(*branches: tuple[ir.BooleanValue, Any], else_: Any) -> c.Column: ...
def row_number() -> c.IntegerColumn: ...
def as_ibis[X: ir.Value](col: X, /) -> X: ...
def as_column[X: ir.Value](expr: X, /) -> X: ...

# handle-parameter spellings (Column[T] is a declaration, not an expression type, in L2)
AnyCol = c.Column
TsCol = c.TimestampColumn
