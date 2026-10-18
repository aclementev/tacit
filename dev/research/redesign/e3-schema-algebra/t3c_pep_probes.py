"""PEP 728 via typing_extensions; PEP 764 with pyright experimental features."""

from typing import Unpack

import ibis
import ibis.expr.types as ir
from typing_extensions import TypedDict


class Closed(TypedDict, closed=True):  # case: 728te closed=True (typing_extensions) expect: ok
    id: int


class Extra(TypedDict, extra_items=ir.Value):  # case: 728te extra_items= (typing_extensions) expect: ok
    id: ir.IntegerValue


def mutate_some(t: ibis.Table, **cols: Unpack[Extra]) -> None: ...


def use_extra(t: ibis.Table, i: ir.IntegerValue, f: ir.FloatingValue) -> None:
    y: Closed = {"id": 1, "x": 2}  # case: 728te extra key on closed TD expect: err
    mutate_some(t, id=i, whatever=f)  # case: 728te Unpack[extra_items] any extra Value expect: ok
    mutate_some(t, id=i, whatever=1)  # case: 728te Unpack[extra_items] non-Value extra expect: err
    mutate_some(t, whatever=f)  # case: 728te Unpack[extra_items] missing required id expect: err


def inline(x: TypedDict[{"score": float}]) -> None: ...  # case: 764te inline TypedDict[{...}] expect: ok
