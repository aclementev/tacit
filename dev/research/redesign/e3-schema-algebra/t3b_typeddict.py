"""3e. TypedDict-based column specs, Unpack[TD] kwargs, PEP 728 / 764 / 767 probes."""

from typing import Any, Protocol, ReadOnly, TypedDict, Unpack, reveal_type

import ibis
import ibis.expr.types as ir

from tx import DataFrame, Schema, SchemaLike


class Orders(Schema):
    id: int
    amount: float


class Scored(Schema):
    score: float


class ScoredOrders(Orders, Scored):
    pass


# A TypedDict mirroring the schema, valued by ibis expressions (could be codegen'd).
class OrdersCols(TypedDict):
    id: ir.IntegerValue
    amount: ir.FloatingValue


class ScoredCols(TypedDict):
    score: ir.FloatingValue


class ScoredOrdersCols(OrdersCols, ScoredCols):  # TypedDict inheritance = extend only
    pass


def build_orders(t: ibis.Table, **cols: Unpack[OrdersCols]) -> DataFrame[Orders]:
    return Orders.cast(t.select(**cols))


def add_score(df: DataFrame[Orders], **cols: Unpack[ScoredCols]) -> DataFrame[ScoredOrders]:
    return ScoredOrders.cast(df.mutate(**cols))


def use_unpack(t: ibis.Table, o: DataFrame[Orders], i: ir.IntegerValue, f: ir.FloatingValue, s: ir.StringValue) -> None:
    build_orders(t, id=i, amount=f)  # case: U all columns, right types expect: ok
    build_orders(t, id=i)  # case: U missing column expect: err
    build_orders(t, id=i, amount=f, extra=f)  # case: U extra column expect: err
    build_orders(t, id=i, amonut=f)  # case: U typo column expect: err
    build_orders(t, id=i, amount=s)  # case: U wrong expr type (str expr for float) expect: err
    add_score(o, score=f)  # case: U add_score(score=...) expect: ok
    add_score(o, scroe=f)  # case: U add_score typo expect: err


# Generic over the TypedDict: what a "typed mutate for any schema" would need.
def build[TD: TypedDict](schema: type[TD], t: ibis.Table, **cols: Unpack[TD]) -> None: ...  # case: G Unpack[TypeVar bound TypedDict] expect: ok


# Can a Schema itself be a TypedDict (to reuse it for Unpack)?
class OrdersTD(Schema, TypedDict):  # case: X Schema + TypedDict as bases expect: ok
    id: int


# PEP 728: closed / extra_items
class Closed(TypedDict, closed=True):  # case: 728 closed=True accepted expect: ok
    id: int


def use_closed(d: Closed) -> None:
    x: dict[str, Any] = {"id": 1, "x": 2}
    y: Closed = {"id": 1, "x": 2}  # case: 728 extra key on closed TD expect: err


class Extra(TypedDict, extra_items=ir.Value):  # case: 728 extra_items= accepted expect: ok
    id: ir.IntegerValue


def mutate_some(t: ibis.Table, **cols: Unpack[Extra]) -> None: ...


def use_extra(t: ibis.Table, i: ir.IntegerValue, f: ir.FloatingValue) -> None:
    mutate_some(t, id=i, whatever=f)  # case: 728 Unpack[extra_items] accepts any extra Value expect: ok
    mutate_some(t, id=i, whatever=1)  # case: 728 Unpack[extra_items] rejects non-Value extra expect: err


# PEP 764: inline TypedDict
def inline(x: TypedDict[{"score": float}]) -> None: ...  # case: 764 TypedDict[{...}] inline expect: ok


# PEP 767: ReadOnly on Protocol attributes (covariant field types)
class HasAmountRO(SchemaLike, Protocol):
    amount: ReadOnly[float]  # case: 767 ReadOnly in Protocol accepted expect: ok


class HasAmountProp(SchemaLike, Protocol):
    @property
    def amount(self) -> float: ...


class IntAmount(Schema):
    amount: int


def needs_amount_ro[S: HasAmountRO](df: DataFrame[S]) -> None: ...


def needs_amount_prop[S: HasAmountProp](df: DataFrame[S]) -> None: ...


def needs_amount_mut[S: HasAmountMut](df: DataFrame[S]) -> None: ...


class HasAmountMut(SchemaLike, Protocol):
    amount: float


def use_ro(df: DataFrame[IntAmount]) -> None:
    needs_amount_ro(df)  # case: 767 int column satisfies ReadOnly[float] expect: ok
    needs_amount_prop(df)  # case: P int column satisfies @property float expect: ok
    needs_amount_mut(df)  # case: P int column vs mutable float attr (invariant) expect: err
    reveal_type(df)
