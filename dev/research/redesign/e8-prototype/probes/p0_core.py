"""De-risk probe: one generic covariant Column[T] as descriptor + facade, frames via dataclass_transform."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Generic, Protocol, Self, TypeVar, dataclass_transform, overload, reveal_type

import ibis.expr.types as ir

T_co = TypeVar("T_co", covariant=True)


class Scalar(ir.Value, Generic[T_co]):
    pass


class Column(ir.Value, Generic[T_co]):
    def __get__(self, obj: object, owner: Any) -> Self: ...
    def __set__(self, obj: object, value: Column[T_co] | Scalar[T_co] | T_co) -> None: ...  # type: ignore[misc]

    @overload
    def __add__(self: Column[int], other: int | Column[int]) -> Column[int]: ...
    @overload
    def __add__(self: Column[float], other: float | Column[float]) -> Column[float]: ...
    @overload
    def __add__(self: Column[float | None], other: float | None | Column[float | None]) -> Column[float | None]: ...
    def __add__(self, other: Any) -> Any: ...  # type: ignore[override]

    def __gt__(self: Column[float | None], other: float | Column[float | None]) -> Column[bool]: ...
    def mean(self: Column[float | None]) -> Scalar[float]: ...
    def upper(self: Column[str | None]) -> Column[str]: ...
    def year(self: Column[date | None]) -> Column[int]: ...
    def fill_null[V](self: Column[V | None], value: V) -> Column[V]: ...  # type: ignore[override]
    def isin(self: Column[T], values: list[T]) -> Column[bool]: ...  # type: ignore[override]


T = TypeVar("T")


def field(*, ge: float | None = None, description: str = "") -> Any: ...


@dataclass_transform(kw_only_default=True, field_specifiers=(field,))
class Frame:
    def __init__(self, **kw: Any) -> None: ...
    def __tacit_into__(self, x: Self, /) -> object: ...

    @classmethod
    def extend(cls, base: Into[Self], *deltas: Into[Self]) -> Self: ...

    @classmethod
    def aggregate[**P, R](cls: Callable[P, R], *, by: list[Column[Any]]) -> Callable[P, R]: ...


class Into[S](Protocol):
    def __tacit_into__(self, x: S, /) -> object: ...


class Orders(Frame):
    order_id: Column[int]
    amount: Column[float] = field(ge=0, description="gross")
    discount: Column[float | None]
    status: Column[str]
    ts: Column[datetime]


class Net(Frame):
    net: Column[float]


class NetOrders(Orders, Net):
    pass


class Customers(Frame):
    customer_id: Column[int]


class Stats(Frame):
    status: Column[str]
    total: Column[float]


def probe(o: Orders, c: Customers) -> None:
    reveal_type(o.amount)  # Column[float]
    reveal_type(Orders.amount)  # Column[float]
    reveal_type(o.discount)  # Column[float | None]
    reveal_type(o.amount + 1)  # Column[float]
    reveal_type(o.order_id + 1)  # Column[int]
    reveal_type(o.order_id + 1.5)  # Column[float]
    reveal_type(o.amount + o.discount)  # Column[float | None]
    reveal_type(o.discount.fill_null(0.0))  # Column[float]
    reveal_type(o.amount.fill_null(0.0))  # Column[float]
    reveal_type(o.amount > 5)  # Column[bool]
    reveal_type(o.amount.mean())  # Scalar[float]
    reveal_type(o.ts.year())  # Column[int]
    reveal_type(o.status.isin(["a", "b"]))  # Column[bool]
    o.amount.upper()  # E: upper on float
    o.status.mean()  # E: mean on str
    o.status > 5  # E: compare str with int
    o.amout  # E: typo
    Net(net=o.amount)  # ok
    Net(net=o.discount)  # E: nullable into non-null
    Net(net=o.discount.fill_null(0.0))  # ok
    Net(net=o.status)  # E: str into float
    Net(net=o.order_id)  # ok? int into float (promotion)
    Net()  # E: missing
    Net(net=o.amount, x=o.amount)  # E: extra
    Orders(order_id=o.order_id, amount=o.amount, discount=o.amount, status=o.status, ts=o.ts)  # ok: non-null into nullable
    Stats(status=o.status, total=o.amount.mean())  # ok scalar
    NetOrders.extend(o, Net(net=o.amount))  # ok
    Stats.extend(o, Net(net=o.amount))  # E: Stats is not an Orders subclass
    NetOrders.extend(c, Net(net=o.amount))  # E: customers is not a base of NetOrders
    reveal_type(NetOrders.extend(o, Net(net=o.amount)))  # NetOrders
    agg = Stats.aggregate(by=[o.status])
    reveal_type(agg)
    agg(status=o.status, total=o.amount.mean())  # ok
    agg(status=o.status)  # E: missing total
