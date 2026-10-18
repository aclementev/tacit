"""1. "At least these columns" generics, nominal (mixin) vs structural (Protocol)."""

from datetime import datetime
from typing import TYPE_CHECKING, Protocol, reveal_type

import ibis
import tacit

from tx import DataFrame, Schema, SchemaLike, conforms

# --- schemas ----------------------------------------------------------------


class HasId(Schema):  # nominal mixin
    id: int


class HasEventTs(Schema):  # nominal mixin
    event_ts: datetime


class Orders(HasId, HasEventTs):  # opts in by inheriting the mixins
    amount: float


class Products(Schema):  # no id
    sku: str


class Payments(Schema):  # has `id` but did NOT inherit the mixin
    id: int
    amount: float


class BadId(Schema):  # `id` with the wrong type
    id: str


class HasIdP(SchemaLike, Protocol):  # structural requirement
    id: int


class HasEventTsP(SchemaLike, Protocol):
    event_ts: datetime


class HasIdAndTsP(HasIdP, HasEventTsP, Protocol):  # requirement intersection, no new class needed by users
    pass


# --- nominal: S bound to a mixin Schema class --------------------------------


def dedupe[S: HasId](df: DataFrame[S]) -> DataFrame[S]:
    return df.distinct(on="id")  # case: N body: distinct -> DataFrame[S] (override) expect: ok


def run_nominal(o: DataFrame[Orders], p: DataFrame[Products], pay: DataFrame[Payments]) -> None:
    reveal_type(dedupe(o))  # case: N dedupe(Orders) keeps exact S expect: ok
    dedupe(p)  # case: N dedupe(Products) rejected expect: err
    dedupe(pay)  # case: N dedupe(Payments) has id but no mixin -> rejected expect: err


# --- structural: S bound to a schema Protocol --------------------------------


def dedupe_p[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    if TYPE_CHECKING:  # NB: type[S].id is `int` statically but absent at runtime (bare annotation)
        reveal_type(df.tacit_schema.id)  # case: P body: name-checked access via type[S]
        df.tacit_schema.idd  # case: P body: typo via type[S] rejected expect: err
        df.idd  # case: P body: typo via df.<name> (ibis __getattr__) expect: err
    return df.distinct(on="id")  # case: P body: distinct -> DataFrame[S] expect: ok


def needs_both[S: HasIdAndTsP](df: DataFrame[S]) -> DataFrame[S]:
    return df.order_by("event_ts")  # case: P body: order_by -> DataFrame[S] expect: ok


def run_structural(
    o: DataFrame[Orders], p: DataFrame[Products], pay: DataFrame[Payments], bad: DataFrame[BadId]
) -> None:
    reveal_type(dedupe_p(o))  # case: P dedupe_p(Orders) expect: ok
    reveal_type(dedupe_p(pay))  # case: P dedupe_p(Payments) no mixin needed expect: ok
    dedupe_p(p)  # case: P dedupe_p(Products) rejected expect: err
    dedupe_p(bad)  # case: P dedupe_p(BadId id:str) rejected expect: err
    needs_both(o)  # case: P needs_both(Orders) expect: ok
    needs_both(pay)  # case: P needs_both(Payments) no event_ts rejected expect: err


# --- same-schema-in / same-schema-out bodies ----------------------------------


def drop_negative[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(df.id.notnull())  # case: S filter -> DataFrame[S] expect: ok


def bump_ids[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.mutate(id=df.id.cast("int64"))  # case: S mutate -> Table rejected (good) expect: err


def bump_ids_retag[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.retag(df.mutate(id=df.id.cast("int64")))  # case: S retag(mutate) -> DataFrame[S] expect: ok


def bump_ids_cast[S: HasId](df: DataFrame[S]) -> DataFrame[S]:
    return df.tacit_schema.cast(df.mutate(id=df.id.cast("int64")))  # case: S type[S].cast (nominal bound) expect: ok


def bump_ids_cast_p[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.tacit_schema.cast(df.mutate(id=df.id.cast("int64")))  # case: S type[S].cast (Protocol bound has no cast) expect: err


# --- runtime view of an arbitrary table as "at least HasIdP" ------------------


def from_untyped(t: ibis.Table) -> None:
    reveal_type(conforms(Orders.cast(t), HasIdP))  # case: R conforms(df, HasIdP) Protocol as type[P] arg expect: ok


# --- the same with tacit 0.2.0's DataFrame (bound = Schema class) ------------


class TOrders(tacit.Schema):
    id: int


def t_dedupe_p[S: HasIdP](df: tacit.DataFrame[S]) -> None:  # case: T tacit.DataFrame[S: Protocol] violates bound expect: err
    pass


def t_dedupe[S: TOrders](df: tacit.DataFrame[S]) -> tacit.DataFrame[S]:
    return df.distinct(on="id")  # case: T tacit 0.2 distinct -> Table rejected expect: err
