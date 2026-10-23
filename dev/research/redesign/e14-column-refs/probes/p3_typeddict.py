# ruff: noqa: B018
"""P3: can a TypedDict give generic, generation-free string-keyed column access?

Checkers special-case `td["k"]` for TypedDict types: the key must be a Literal naming a
declared key, and the result is that key's declared value type. That is exactly a typed
`df.c["amount"]` -- if the frame's namespace IS (or maps to) a TypedDict.

B1  schema-as-TypedDict:   DataFrame[OrdersTD].c : OrdersTD
B2  schema class linked to a TypedDict:  class Orders(Schema[OrdersCols]); df.cols solved via self-type
B3  PEP 692 `**kwargs: Unpack[TD]` for build(); B4 PEP 764 inline TypedDict; B5 PEP 728 closed
"""

from datetime import datetime
from typing import Any, Generic, NotRequired, Protocol, TypedDict, TypeVar, Unpack, reveal_type

S_co = TypeVar("S_co", covariant=True)
TD_co = TypeVar("TD_co", covariant=True)


class Column[T]:
    def __gt__(self, o: object) -> "Column[bool]": ...
    def sum(self) -> T: ...


# ---------------------------------------------------------------- B1: the schema IS a TypedDict
class OrdersTD(TypedDict):
    order_id: Column[int]
    amount: Column[float]
    discount: Column[float | None]


class NetTD(TypedDict):
    net_amount: Column[float]


class NetOrdersTD(OrdersTD, NetTD):
    pass


class HasTsTD(TypedDict):
    event_ts: Column[datetime]


class ClicksTD(HasTsTD):
    url: Column[str]


class LookalikeTD(TypedDict):  # unrelated schema that happens to have Orders' keys
    order_id: Column[int]
    amount: Column[float]
    discount: Column[float | None]
    other: Column[str]


class Frame1(Generic[S_co]):
    @property
    def c(self) -> S_co: ...
    def filter(self, *p: Column[bool]) -> "Frame1[S_co]": ...


def takes_orders(df: Frame1[OrdersTD]) -> None: ...


def b1(o: Frame1[OrdersTD], n: Frame1[NetOrdersTD], k: Frame1[LookalikeTD], key: str) -> None:
    reveal_type(o.c["amount"])  # Column[float]
    reveal_type(o.c["discount"])  # Column[float | None]
    o.c["amout"]  # error: typo
    o.c[key]  # error: non-literal key
    reveal_type(n.c["net_amount"])  # Column[float]
    takes_orders(n)  # ok: NetOrdersTD is structurally an OrdersTD
    takes_orders(k)  # accepted (structural): an unrelated schema with a superset of keys
    OrdersTD.amount  # error: no class-level access on a TypedDict (no refs, no classmethods)


def b1_generic[S: HasTsTD](df: Frame1[S]) -> Frame1[S]:
    reveal_type(df.c["event_ts"])  # Column[datetime]
    df.c["url"]  # error
    return df.filter(df.c["event_ts"] > datetime(2024, 1, 1))


def b1_use(k: Frame1[ClicksTD]) -> None:
    reveal_type(b1_generic(k))  # Frame1[ClicksTD]


# ---------------------------------------------------------------- B2: schema class -> TypedDict link
class Schema(Generic[TD_co]):
    pass


class OrdersCols(TypedDict):
    order_id: Column[int]
    amount: Column[float]


class NetCols(TypedDict):
    net_amount: Column[float]


class NetOrdersCols(OrdersCols, NetCols):
    pass


class Orders(Schema[OrdersCols]):
    pass


class NetOrders(Orders, Schema[NetOrdersCols]):  # re-parameterized base: is this accepted?
    pass


class Frame2(Generic[S_co]):
    def cols[TD](self: "Frame2[Schema[TD]]") -> TD: ...


def b2(o: Frame2[Orders], n: Frame2[NetOrders]) -> None:
    reveal_type(o.cols())  # OrdersCols
    reveal_type(o.cols()["amount"])  # Column[float]
    o.cols()["amout"]  # error
    reveal_type(n.cols()["net_amount"])  # Column[float]


# ---------------------------------------------------------------- B3: PEP 692 Unpack for build kwargs
def build_orders(**kw: Unpack[OrdersTD]) -> Frame1[OrdersTD]: ...


def build_any[TD: TypedDict](schema: type[TD], **kw: Unpack[TD]) -> Frame1[TD]: ...  # not allowed by PEP 692


def b3(o: Frame1[OrdersTD]) -> None:
    build_orders(order_id=o.c["order_id"], amount=o.c["amount"], discount=o.c["discount"])
    build_orders(order_id=o.c["order_id"], amount=o.c["order_id"], discount=o.c["discount"])  # error: int into float
    build_orders(order_id=o.c["order_id"])  # error: missing keys


# ---------------------------------------------------------------- B4: PEP 764 inline TypedDict
def b4(x: Frame1[TypedDict[{"amount": Column[float]}]]) -> None:  # type: ignore[valid-type]
    reveal_type(x.c["amount"])
