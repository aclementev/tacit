"""Prototype: annotation-only column refs (typedspark/SQLAlchemy Mapped style) without a metaclass.

Col[T] is a str subclass so it can be passed wherever a column *name* is accepted
(ibis Table.__getitem__/select/group_by), and carries the dtype T statically.
"""
from __future__ import annotations

from typing import Self, get_type_hints, get_origin, get_args, reveal_type

import ibis


class Col[T](str):
    __slots__ = ()


class Schema:
    def __init_subclass__(cls) -> None:
        for name, hint in get_type_hints(cls).items():
            if get_origin(hint) is Col:
                setattr(cls, name, Col(name))   # class-level value is the name


class Raw(Schema):
    id: Col[int]
    amount: Col[float]
    status: Col[str]


class Enriched(Raw):
    amount_tax: Col[float]


def f(t: ibis.Table) -> None:
    reveal_type(Raw.amount)           # Col[float]
    reveal_type(Enriched.amount)      # inherited
    reveal_type(Raw.amnt)             # typo -> error
    t.select(Raw.amount)              # str accepted
    t[Raw.amount]
    t.group_by(Raw.status).agg(total=t[Raw.amount].sum())


def takes_float_col(c: Col[float]) -> None: ...

takes_float_col(Raw.amount)   # ok
takes_float_col(Raw.status)   # wrong column type -> error

t = ibis.memtable({"id": [1], "amount": [1.0], "status": ["a"]})
print(t.select(Raw.amount).execute(), repr(Raw.amount), type(Raw.amount))
print(t.group_by(Raw.status).agg(total=t[Raw.amount].sum()).execute())
