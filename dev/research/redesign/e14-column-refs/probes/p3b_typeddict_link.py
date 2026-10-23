# ruff: noqa: B018
"""P3b: link a schema CLASS to a mirror TypedDict through a protocol attribute (inheritance-safe)."""
from datetime import datetime
from typing import Generic, Protocol, TypedDict, TypeVar, reveal_type

S_co = TypeVar("S_co", covariant=True)
TD_co = TypeVar("TD_co", covariant=True)


class Column[T]:
    def __gt__(self, o: object) -> "Column[bool]": ...


class _HasCols(Protocol[TD_co]):
    @property
    def __tacit_cols__(self) -> TD_co: ...


class OrdersCols(TypedDict):
    order_id: Column[int]
    amount: Column[float]


class NetCols(TypedDict):
    net_amount: Column[float]


class NetOrdersCols(OrdersCols, NetCols):
    pass


class HasTsCols(TypedDict):
    event_ts: Column[datetime]


class Orders:
    order_id: Column[int]
    amount: Column[float]
    @property
    def __tacit_cols__(self) -> OrdersCols: ...  # the mirror (hand-written or generated)


class Net:
    net_amount: Column[float]
    @property
    def __tacit_cols__(self) -> NetCols: ...


class NetOrders(Orders, Net):
    @property
    def __tacit_cols__(self) -> NetOrdersCols: ...  # must be re-declared (narrowed) in every subclass


class HasTs:
    event_ts: Column[datetime]
    @property
    def __tacit_cols__(self) -> HasTsCols: ...


class Frame(Generic[S_co]):
    @property
    def c(self) -> S_co: ...
    def cols[TD](self: "Frame[_HasCols[TD]]") -> TD: ...


def f(o: Frame[Orders], n: Frame[NetOrders], key: str) -> None:
    reveal_type(o.cols()["amount"])  # Column[float]
    o.cols()["amout"]  # error
    reveal_type(n.cols()["net_amount"])  # Column[float]
    reveal_type(n.cols()["amount"])  # Column[float]


def g[S: HasTs](df: Frame[S]) -> None:
    reveal_type(df.cols()["event_ts"])  # Column[datetime]
    df.cols()["url"]  # error
