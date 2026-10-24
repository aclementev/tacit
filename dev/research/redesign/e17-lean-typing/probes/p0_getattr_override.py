"""Can a subclass of ir.Table hide ibis's catch-all __getattr__ from checkers without a generated stub?"""
from typing import TYPE_CHECKING, Generic, Never, TypeVar, reveal_type

import ibis
import ibis.expr.types as ir

S = TypeVar("S")


class A(ir.Table, Generic[S]):
    """Variant A: __getattr__ whose parameter type no name satisfies."""
    if TYPE_CHECKING:
        def __getattr__(self, name: Never) -> Never: ...


class B(ir.Table, Generic[S]):
    """Variant B: __getattr__ declared as None."""
    if TYPE_CHECKING:
        __getattr__: None  # type: ignore[assignment]


def probe(a: A[int], b: B[int], t: ir.Table) -> None:
    reveal_type(a.typo)     # want: error
    reveal_type(b.typo)     # want: error
    reveal_type(a.mutate)   # want: ibis method still visible
    reveal_type(a.filter)
    x: A[int] = t           # want: error (forgot cast) -- depends on ir.Table base quality
    y: A[int] = a.mutate(z=ibis.literal(1))  # want: error
