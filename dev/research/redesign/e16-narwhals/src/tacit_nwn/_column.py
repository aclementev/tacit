"""Runtime side of the typed column facade: at runtime a column *is* a narwhals expression.

`Column[T]` only exists for annotations (`amount: Column[float]`); the static facade is
`_column.pyi`. `when(...)` is a typed spelling of `nw.when` (narwhals' own returns an untyped Expr).
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

import narwhals.stable.v2 as nw

T = TypeVar("T")


class Column(Generic[T]):
    """Annotation-only marker. Values are plain `nw.Expr` at runtime."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("Column[T] is an annotation; columns are narwhals expressions at runtime")


def lit(value: Any) -> nw.Expr:
    return nw.lit(value)


def expr(e: nw.Expr) -> nw.Expr:
    """Escape hatch: treat an untyped narwhals expression as `Column[Any]`."""
    return e


class _When:
    def __init__(self, chain: Any) -> None:
        self._chain = chain

    def then(self, value: Any) -> _Then:
        v = value if isinstance(value, nw.Expr) else nw.lit(value)
        return _Then(self._chain.then(v))


class _Then:
    def __init__(self, chain: Any) -> None:
        self._chain = chain

    def when(self, cond: Any) -> _When:
        return _When(self._chain.when(cond))

    def otherwise(self, value: Any) -> nw.Expr:
        v = value if isinstance(value, nw.Expr) else nw.lit(value)
        return self._chain.otherwise(v)


def when(cond: Any) -> _When:
    return _When(nw.when(cond))
