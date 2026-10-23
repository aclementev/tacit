"""Runtime side of Column[T] / Scalar[T].

Type checkers read `_column.pyi` (the generated facade). At runtime there is
no wrapper: `orders.amount` is the plain ibis column and `orders.amount.sum()`
the plain ibis scalar. `Column` / `Scalar` exist only so annotations like
`Column[float | None]` can be subscripted and introspected, and so that
`isinstance(x, Column)` means "is an ibis column".
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

import ibis
import ibis.expr.types as ir

T_co = TypeVar("T_co", covariant=True)


class _ExprMeta(type):
    _ibis_cls: type

    def __instancecheck__(cls, obj: object) -> bool:
        return isinstance(obj, cls._ibis_cls)


class Column(Generic[T_co], metaclass=_ExprMeta):
    _ibis_cls = ir.Column

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Column[...] is an annotation; read columns from a frame instance (orders.amount)")


class Scalar(Generic[T_co], metaclass=_ExprMeta):
    _ibis_cls = ir.Scalar

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Scalar[...] is an annotation; reductions such as orders.amount.sum() produce scalars")


def lit(value: Any, /, type: Any = None) -> Any:
    return ibis.literal(value, type=type)


def cases(*branches: Any, else_: Any) -> Any:
    return ibis.cases(*branches, else_=else_)


def row_number() -> Any:
    return ibis.row_number()


def as_ibis(col: Any, /) -> Any:
    return col


def as_column(expr: Any, /) -> Any:
    return expr
