"""Runtime side of Column[T] / Scalar[T].

Type checkers read `_column.pyi` (E11's derived facade). At runtime there is no
wrapper: `df.c.amount` is the plain ibis column and `df.c.amount.sum()` the
plain ibis scalar. `Column` / `Scalar` exist so annotations like
`Column[float | None]` can be subscripted and introspected.

The one runtime addition to ibis is `Value.assume_not_null()`: a cast to the
same dtype marked NOT NULL. It compiles to a no-op CAST, and output
construction (`build` / `extend` / `aggregate`) finds these markers and checks
them with one null-count query, so the narrowing is a checked assertion.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

import ibis
import ibis.expr.operations as ops
import ibis.expr.types as ir

T_co = TypeVar("T_co", covariant=True)


class _ExprMeta(type):
    _ibis_cls: type

    def __instancecheck__(cls, obj: object) -> bool:
        return isinstance(obj, cls._ibis_cls)


class Column(Generic[T_co], metaclass=_ExprMeta):
    _ibis_cls = ir.Column

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Column[...] is an annotation; read columns from a frame (df.c.amount)")


class Scalar(Generic[T_co], metaclass=_ExprMeta):
    _ibis_cls = ir.Scalar

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("Scalar[...] is an annotation; reductions such as df.c.amount.sum() produce scalars")


def _assume_not_null(self: ir.Value) -> ir.Value:
    return self.cast(self.type().copy(nullable=False))


ir.Value.assume_not_null = _assume_not_null  # type: ignore[attr-defined]


def assumptions(*exprs: ir.Value) -> list[ir.Value]:
    """The `x.assume_not_null()` markers inside `exprs` (their argument `x`)."""
    found: dict[Any, None] = {}
    for e in exprs:
        for node in e.op().find(ops.Cast, filter=ops.Value):  # stay inside this expression
            if node.to.nullable is False:
                found[node.arg] = None
    return [op.to_expr() for op in found]


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
