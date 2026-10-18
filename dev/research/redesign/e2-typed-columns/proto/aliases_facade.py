"""A4: A1 descriptors whose Get type is a tacit-owned *static facade*.

The facade classes exist only for type checkers (overrides deliberately
narrow ibis' signatures, hence the per-line ignores in this tacit-internal file). They subclass ibis' *Value*
classes (clean MRO: no `FixedTextJupyterMixin` Unknown base, see E) and
re-declare the handful of operators/methods whose ibis annotations are wrong or
too weak (literal comparisons, arithmetic losing Column-ness, Column-only
reductions). At runtime the facade names are plain ibis classes, so nothing
wraps or proxies real expressions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import ibis.expr.datatypes as dt
import ibis.expr.types as ir

from .frame import Col

if TYPE_CHECKING:
    type NumLike = int | float | ir.NumericValue

    class BoolCol(ir.BooleanValue):
        def __and__(self, other: bool | ir.BooleanValue) -> BoolCol: ...  # type: ignore
        def __or__(self, other: bool | ir.BooleanValue) -> BoolCol: ...  # type: ignore
        def __invert__(self) -> BoolCol: ...  # type: ignore

    class NumCol(ir.NumericValue):
        def __add__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __radd__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __sub__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __rsub__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __mul__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __rmul__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __truediv__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __rtruediv__(self, other: NumLike) -> NumCol: ...  # type: ignore
        def __lt__(self, other: NumLike) -> BoolCol: ...  # type: ignore
        def __le__(self, other: NumLike) -> BoolCol: ...  # type: ignore
        def __gt__(self, other: NumLike) -> BoolCol: ...  # type: ignore
        def __ge__(self, other: NumLike) -> BoolCol: ...  # type: ignore
        def __eq__(self, other: object) -> BoolCol: ...  # type: ignore
        def mean(self) -> ir.FloatingScalar: ...
        def sum(self) -> ir.NumericScalar: ...
        def min(self) -> ir.NumericScalar: ...
        def max(self) -> ir.NumericScalar: ...
        def count(self) -> ir.IntegerScalar: ...

    class StrCol(ir.StringValue):
        def __lt__(self, other: str | ir.StringValue) -> BoolCol: ...  # type: ignore
        def __le__(self, other: str | ir.StringValue) -> BoolCol: ...  # type: ignore
        def __gt__(self, other: str | ir.StringValue) -> BoolCol: ...  # type: ignore
        def __ge__(self, other: str | ir.StringValue) -> BoolCol: ...  # type: ignore
        def __eq__(self, other: object) -> BoolCol: ...  # type: ignore
        def upper(self) -> StrCol: ...
        def lower(self) -> StrCol: ...
        def count(self) -> ir.IntegerScalar: ...
else:
    BoolCol = ir.BooleanColumn
    NumCol = ir.NumericColumn
    StrCol = ir.StringColumn

Float64 = Annotated[Col[NumCol, ir.NumericValue], dt.float64]
Int64 = Annotated[Col[NumCol, ir.NumericValue], dt.int64]
String = Annotated[Col[StrCol, ir.StringValue], dt.string]
