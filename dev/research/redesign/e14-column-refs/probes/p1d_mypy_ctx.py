# ruff: noqa
"""mypy: return-type context leaks into descriptor __get__ inference. Try variants."""
from __future__ import annotations
from typing import Any, Generic, Self, TypeVar, overload, reveal_type

O_contra = TypeVar("O_contra", contravariant=True)
T_co = TypeVar("T_co", covariant=True)
S_co = TypeVar("S_co", covariant=True)
S = TypeVar("S")


class Schema: ...


class Ref(Generic[O_contra, T_co]):
    def desc(self) -> Ref[O_contra, T_co]: ...


class ColA(Generic[T_co]):  # baseline
    @overload
    def __get__(self, obj: None, owner: type[S], /) -> Ref[S, T_co]: ...
    @overload
    def __get__(self, obj: Schema, owner: Any, /) -> ColA[T_co]: ...
    def __get__(self, obj: Any, owner: Any, /) -> Any: ...


class ColB(Generic[T_co]):  # non-overloaded class-only descriptor
    def __get__(self, obj: None, owner: type[S], /) -> Ref[S, T_co]: ...


class ColC(Generic[T_co]):  # Self-typed owner via a generic "owner" protocol param name
    @overload
    def __get__[X](self, obj: None, owner: type[X], /) -> Ref[X, T_co]: ...
    @overload
    def __get__(self, obj: Schema, owner: Any, /) -> ColC[T_co]: ...
    def __get__(self, obj: Any, owner: Any, /) -> Any: ...


class Orders(Schema):
    a: ColA[float]
    b: ColB[float]
    c: ColC[float]


class Big(Orders):
    pass


class DataFrame(Generic[S_co]):
    def order_by(self, *k: Ref[S_co, Any]) -> Self: ...


def f(big: DataFrame[Big]) -> None:
    big.order_by(Orders.a)  # parent ref, bare, in child-frame context: should be OK
    big.order_by(Orders.b)
    big.order_by(Orders.c)
    big.order_by(Orders.a.desc())  # not bare: no context on the attribute


def g[X: Orders](df: DataFrame[X]) -> None:
    df.order_by(Orders.a)  # generic step, bare: should be OK
    df.order_by(Orders.b)
    r = Orders.a
    df.order_by(r)  # via a variable
