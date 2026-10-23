# ruff: noqa
"""mypy context leak: does a Protocol-typed frame parameter avoid it?"""
from __future__ import annotations
from typing import Any, Generic, Protocol, Self, TypeVar, overload, reveal_type

O_contra = TypeVar("O_contra", contravariant=True)
T_co = TypeVar("T_co", covariant=True)
S_co = TypeVar("S_co", covariant=True)
S_contra = TypeVar("S_contra", contravariant=True)
_O = TypeVar("_O")


class Schema: ...


class Ref(Generic[O_contra, T_co]):
    def __tacit_on__(self, frame: O_contra, /) -> None: ...
    def desc(self) -> Ref[O_contra, T_co]: ...


class On(Protocol[S_contra]):
    def __tacit_on__(self, frame: S_contra, /) -> None: ...


class Col(Generic[T_co]):
    @overload
    def __get__(self, obj: None, owner: type[_O], /) -> Ref[_O, T_co]: ...
    @overload
    def __get__(self, obj: Schema, owner: Any, /) -> Col[T_co]: ...
    def __get__(self, obj: Any, owner: Any, /) -> Any: ...


class Orders(Schema):
    a: Col[float]


class Big(Orders):
    b: Col[float]


class Cust(Schema):
    z: Col[float]


class DataFrame(Generic[S_co]):
    def order_by(self, *k: On[S_co]) -> Self: ...


def f(big: DataFrame[Big], o: DataFrame[Orders]) -> None:
    big.order_by(Orders.a)  # ok wanted
    big.order_by(Big.b)  # ok
    o.order_by(Big.b)  # error wanted
    o.order_by(Cust.z)  # error wanted


def g[X: Orders](df: DataFrame[X]) -> None:
    df.order_by(Orders.a)  # ok wanted
