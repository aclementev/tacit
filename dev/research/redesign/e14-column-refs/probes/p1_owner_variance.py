# ruff: noqa
"""P1: can a class-level column reference carry its OWNER schema, and can a frame check it?

Ref[O, T]: O contravariant (a parent-schema ref is usable on a child frame), T covariant.
Owner captured from the descriptor's `owner: type[O]` on class access.
"""
from __future__ import annotations

from typing import Any, Generic, Self, TypeVar, dataclass_transform, overload, reveal_type

O_contra = TypeVar("O_contra", contravariant=True)
T_co = TypeVar("T_co", covariant=True)
S_co = TypeVar("S_co", covariant=True)
S = TypeVar("S")


class Ref(Generic[O_contra, T_co]):
    # class-level owner: `other` must have (a supertype-ref of) the receiver's owner
    def __gt__(self: Ref[O_contra, float], other: float | Ref[O_contra, float], /) -> Ref[O_contra, bool]: ...  # type: ignore
    def __add__(self: Ref[O_contra, float], other: float | Ref[O_contra, float], /) -> Ref[O_contra, float]: ...  # type: ignore
    def desc(self) -> Ref[O_contra, T_co]: ...


class Ref2(Generic[O_contra, T_co]):
    # method-level owner: solved from both operands
    def __add__[O](self: Ref2[O, float], other: float | Ref2[O, float], /) -> Ref2[O, float]: ...  # type: ignore


class Column(Generic[T_co]):
    @overload
    def __get__(self, obj: None, owner: type[S], /) -> Ref[S, T_co]: ...
    @overload
    def __get__(self, obj: object, owner: Any, /) -> Column[T_co]: ...
    def __get__(self, obj: Any, owner: Any, /) -> Any: ...
    def __gt__(self, other: float, /) -> Column[bool]: ...


class Column2(Generic[T_co]):
    @overload
    def __get__(self, obj: None, owner: type[S], /) -> Ref2[S, T_co]: ...
    @overload
    def __get__(self, obj: object, owner: Any, /) -> Column2[T_co]: ...
    def __get__(self, obj: Any, owner: Any, /) -> Any: ...


@dataclass_transform(kw_only_default=True)
class Schema: ...


class Orders(Schema):
    amount: Column[float]
    a2: Column2[float]


class Big(Orders):
    extra: Column[float]
    e2: Column2[float]


class Customers(Schema):
    score: Column[float]
    s2: Column2[float]


class DataFrame(Generic[S_co]):
    def filter(self, *p: Ref[S_co, bool | None]) -> Self: ...
    def order_by(self, *k: Ref[S_co, Any]) -> Self: ...
    def mutate2(self, **k: Ref2[S_co, Any]) -> Self: ...
    @property
    def c(self) -> S_co: ...


def f(o: DataFrame[Orders], b: DataFrame[Big], c: DataFrame[Customers]) -> None:
    reveal_type(Orders.amount)  # want Ref[Orders, float]
    reveal_type(Big.amount)  # want Ref[Big, float]  (owner captured from the accessed class)
    reveal_type(o.c.amount)  # want Column[float]   (instance access)
    Orders.amout  # want error: typo
    o.filter(Orders.amount > 0)  # ok
    o.filter(Customers.score > 0)  # want error: wrong owner
    b.filter(Orders.amount > 0)  # ok: parent ref on child frame
    o.filter(Big.extra > 0)  # want error: child ref on parent frame
    o.filter(Big.amount > 0)  # want error?: Big.amount is Ref[Big]; strict
    o.order_by(Orders.amount.desc())  # ok
    o.order_by(Customers.score.desc())  # want error
    o.filter(o.c.amount > 0)  # want error: Column is not a Ref here (no Column overload in this probe)
    # mixing, class-level owner
    reveal_type(Orders.amount + Orders.amount)  # Ref[Orders, float]
    Orders.amount + Customers.score  # want error
    reveal_type(Big.extra + Orders.amount)  # ok: Ref[Big]
    reveal_type(Orders.amount + Big.extra)  # asymmetric: error with class-level owner?
    # mixing, method-level owner
    reveal_type(Orders.a2 + Orders.a2)
    reveal_type(Orders.a2 + Customers.s2)  # error or Ref2[Never]/intersection?
    reveal_type(Orders.a2 + Big.e2)  # want Ref2[Big, float]
    b.mutate2(x=Orders.a2 + Big.e2)  # ok
    o.mutate2(x=Orders.a2 + Customers.s2)  # want error (here or above)


def generic[X: Orders](df: DataFrame[X]) -> DataFrame[X]:
    return df.filter(Orders.amount > 0)  # ok: Ref[Orders] <: Ref[X] since X <: Orders
