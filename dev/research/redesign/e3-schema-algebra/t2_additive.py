"""2. Additive generics: S -> S + {score: float}. Best approximations."""

from typing import Any, Protocol, reveal_type

import ibis

from tx import DataFrame, Into, Schema, SchemaLike


class Orders(Schema):
    id: int
    amount: float


class Customers(Schema):
    id: int
    name: str


class Scored(Schema):  # the "+ {score: float}" part, as a mixin
    score: float


class ScoredP(SchemaLike, Protocol):
    score: float


class HasIdP(SchemaLike, Protocol):
    id: int


class ScoredOrders(Orders, Scored):  # caller-named output: Orders + Scored
    pass


class ScoredCustomers(Customers, Scored):
    pass


class OrdersPlusScoreNoMixin(Orders):  # has score but does not inherit Scored
    score: float


def score_expr(t: ibis.Table) -> ibis.Value:
    return ibis.literal(1.0)


# --- A. generic wrapper schema WithScore[S] -----------------------------------


class WithScore[S: SchemaLike](Scored):  # cannot inherit from S: a TypeVar is not a valid base
    pass


def add_score_a[S: SchemaLike](df: DataFrame[S]) -> DataFrame[WithScore[S]]:
    return DataFrame._wrap(df.mutate(score=score_expr(df)), WithScore)  # case: A body needs unchecked wrap expect: ok


def dedupe_p[S: HasIdP](df: DataFrame[S]) -> DataFrame[S]:
    return df.distinct(on="id")


def needs_score[S: ScoredP](df: DataFrame[S]) -> DataFrame[S]:
    return df


def use_a(o: DataFrame[Orders]) -> None:
    r = add_score_a(o)
    reveal_type(r)  # case: A add_score_a(Orders)
    needs_score(r)  # case: A result satisfies ScoredP expect: ok
    dedupe_p(r)  # case: A result lost Orders.id (want ok) expect: ok
    x: DataFrame[Orders] = r  # case: A result usable as DataFrame[Orders] (want ok) expect: ok


# --- B1. caller names output, two independent TypeVars -------------------------


def add_score_b1[S: SchemaLike, O: Scored](df: DataFrame[S], out: type[O]) -> DataFrame[O]:
    return out.cast(df.mutate(score=score_expr(df)))  # case: B1 body expect: ok


def use_b1(o: DataFrame[Orders]) -> None:
    reveal_type(add_score_b1(o, ScoredOrders))  # case: B1 out=ScoredOrders expect: ok
    add_score_b1(o, ScoredCustomers)  # case: B1 out=ScoredCustomers for Orders input (want err) expect: err
    add_score_b1(o, Orders)  # case: B1 out without score rejected expect: err


# --- B2. caller names output, O <: S via a contravariant input view -------------


def add_score_b2[O: Scored](df: Into[O], out: type[O]) -> DataFrame[O]:
    t = df.to_table()
    return out.cast(t.mutate(score=score_expr(t)))  # case: B2 body expect: ok


def use_b2(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    reveal_type(add_score_b2(o, ScoredOrders))  # case: B2 out=ScoredOrders expect: ok
    add_score_b2(o, ScoredCustomers)  # case: B2 out=ScoredCustomers for Orders input expect: err
    add_score_b2(o, Orders)  # case: B2 out without Scored mixin expect: err
    add_score_b2(o, OrdersPlusScoreNoMixin)  # case: B2 out has score but not the mixin expect: err
    add_score_b2(c, ScoredCustomers)  # case: B2 same fn, other schema expect: ok
    r = add_score_b2(o, ScoredOrders)
    dedupe_p(r)  # case: B2 result still has id expect: ok
    needs_score(r)  # case: B2 result has score expect: ok
    y: DataFrame[Orders] = r  # case: B2 result as DataFrame[Orders] (invariant: want? see notes) expect: err


# B2 with a structural score requirement instead of the nominal mixin
def add_score_b2p[O: ScoredP](df: Into[O], out: type[O]) -> DataFrame[O]:
    return DataFrame._wrap(df.to_table().mutate(score=ibis.literal(1.0)), out)


def use_b2p(o: DataFrame[Orders]) -> None:
    reveal_type(add_score_b2p(o, OrdersPlusScoreNoMixin))  # case: B2p structural Scored, nominal O <: Orders expect: ok


# B2m. the same trick as a method: df.extend_to(Out, **exprs) requires Out <: S


def use_b2m(o: DataFrame[Orders]) -> None:
    reveal_type(o.extend_to(ScoredOrders, score=ibis.literal(1.0)))  # case: B2m o.extend_to(ScoredOrders) (want DataFrame[ScoredOrders]) expect: ok
    o.extend_to(ScoredCustomers, score=ibis.literal(1.0))  # case: B2m o.extend_to(ScoredCustomers) expect: err


def use_b2c(o: DataFrame[Orders]) -> None:
    reveal_type(ScoredOrders.from_mutate(o, score=ibis.literal(1.0)))  # case: B2c ScoredOrders.from_mutate(o) expect: ok
    ScoredCustomers.from_mutate(o, score=ibis.literal(1.0))  # case: B2c ScoredCustomers.from_mutate(o) expect: err


def generic_caller[S: HasIdP](df: DataFrame[S]) -> None:
    add_score_b2(df, ScoredOrders)  # case: B2g generic caller cannot name S+Scored expect: err


# --- C. Ext[S, E]: subclass of DataFrame[S] carrying the extension E ------------


class Ext[S: SchemaLike, E: SchemaLike](DataFrame[S]):
    pass


def add_score_c[S: SchemaLike](df: DataFrame[S]) -> Ext[S, Scored]:
    raise NotImplementedError


def needs_score_c[S: SchemaLike](df: Ext[S, Scored]) -> None: ...


def use_c(o: DataFrame[Orders]) -> None:
    r = add_score_c(o)
    reveal_type(r)  # case: C add_score_c(Orders)
    needs_score_c(r)  # case: C consumer requiring Scored extension expect: ok
    reveal_type(dedupe_p(r))  # case: C pass through generic step: Ext info lost
    z: DataFrame[Orders] = r  # case: C usable as DataFrame[Orders] (subclass) expect: ok
    reveal_type(add_score_c(add_score_c(o)))  # case: C two extensions: first lost


# --- D. variadic "frame of parts": Frame[*Parts] -------------------------------


class Frame[*P](ibis.Table):
    pass


def add_score_d[*P](df: Frame[*P]) -> Frame[*P, Scored]:
    raise NotImplementedError


class Audited(Schema):
    loaded_at: str


def add_audit_d[*P](df: Frame[*P]) -> Frame[*P, Audited]:
    raise NotImplementedError


def needs_score_last[*P](df: Frame[*P, Scored]) -> None: ...


def needs_orders_first[*P](df: Frame[Orders, *P]) -> None: ...


def use_d(o: Frame[Orders]) -> None:
    r = add_audit_d(add_score_d(o))
    reveal_type(r)  # case: D add_audit(add_score(Orders))
    needs_orders_first(r)  # case: D consumer: Orders at head expect: ok
    needs_score_last(r)  # case: D consumer: Scored anywhere (not last) (want ok) expect: ok
    needs_score_last(add_score_d(o))  # case: D consumer: Scored last expect: ok


def _unused(x: Any) -> None: ...
