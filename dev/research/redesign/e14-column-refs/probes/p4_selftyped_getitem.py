# ruff: noqa
"""df["x"] typed by SELF-TYPED overloads on the frame class itself (would have to be generated into
tacit's own DataFrame stub, per project). Covariance makes parent keys work on child frames."""
from typing import Generic, Literal, TypeVar, overload, reveal_type
from datetime import datetime

S_co = TypeVar("S_co", covariant=True)

class Col[T]:
    def __gt__(self, o: object) -> "Col[bool]": ...

class Orders: ...
class Net: ...
class NetOrders(Orders, Net): ...
class HasTs: ...
class Clicks(HasTs): ...

class DF(Generic[S_co]):
    @overload
    def __getitem__(self: "DF[Orders]", key: Literal["amount"], /) -> Col[float]: ...
    @overload
    def __getitem__(self: "DF[Orders]", key: Literal["status"], /) -> Col[str]: ...
    @overload
    def __getitem__(self: "DF[Net]", key: Literal["net_amount"], /) -> Col[float]: ...
    @overload
    def __getitem__(self: "DF[HasTs]", key: Literal["ts"], /) -> Col[datetime]: ...
    @overload
    def __getitem__(self: "DF[Clicks]", key: Literal["url"], /) -> Col[str]: ...
    def __getitem__(self, key: str) -> object: ...

def f(o: DF[Orders], n: DF[NetOrders], k: DF[Clicks]) -> None:
    reveal_type(o["amount"])  # Col[float]
    o["amout"]  # error
    o["net_amount"]  # error
    reveal_type(n["amount"])  # Col[float] via covariance
    reveal_type(n["net_amount"])  # Col[float]
    reveal_type(k["ts"])

def g[S: HasTs](df: DF[S]) -> None:
    reveal_type(df["ts"])
    df["url"]  # error
