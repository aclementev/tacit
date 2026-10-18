"""Descriptor Column[T] (SQLAlchemy Mapped[T] style) + dataclass_transform, across all four checkers."""
from __future__ import annotations
from typing import Any, Generic, TypeVar, overload, reveal_type, dataclass_transform

T = TypeVar("T")

class Deferred:
    def __gt__(self, other: object) -> Deferred: ...
    def __mul__(self, other: object) -> Deferred: ...

class Column(Generic[T]):
    @overload
    def __get__(self, obj: None, owner: type) -> Deferred: ...
    @overload
    def __get__(self, obj: object, owner: type) -> T: ...
    def __get__(self, obj: object | None, owner: type) -> Any: ...

@dataclass_transform(field_specifiers=(Column,))
class Schema:
    pass

class Order(Schema):
    amount: Column[float] = Column()
    status: Column[str] = Column()

reveal_type(Order.amount)          # want Deferred
reveal_type(Order().amount)        # want float
x = Order.amount > 0               # want OK (Deferred.__gt__)
y = Order.status.upper()           # want ERROR: Deferred has no upper
