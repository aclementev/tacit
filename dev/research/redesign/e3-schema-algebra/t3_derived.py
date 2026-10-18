"""3. Derived schemas: pick / drop / rename / extend."""

from typing import Protocol, Self, reveal_type

from derive import VerifiedSchema, drop, pick
from tx import DataFrame, Schema, SchemaLike


class Iris(Schema):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    species: str


class HasPetalP(SchemaLike, Protocol):
    petal_length: float


def needs_petal[S: HasPetalP](df: DataFrame[S]) -> DataFrame[S]:
    return df


# --- (a) explicit subclassing: extend is free, pick/drop are not expressible ---


class IrisFeatures(Iris):  # extend
    sepal_ratio: float


# Bottom-up composition gives "pick" by construction (if you own the base):
class Sepal(Schema):
    sepal_length: float
    sepal_width: float


class Petal(Schema):
    petal_length: float
    petal_width: float


class Iris2(Sepal, Petal):
    species: str


def use_a(f: DataFrame[IrisFeatures], s: DataFrame[Sepal]) -> None:
    needs_petal(f)  # case: a IrisFeatures has petal_length expect: ok
    needs_petal(s)  # case: a Sepal (bottom-up pick) has no petal expect: err


# --- (b1) runtime helper used as a base class ------------------------------------


class _Pickable(Schema):
    @classmethod
    def pick(cls, *names: str) -> type[Self]:  # lie: claims "same class"
        return pick(cls, *names).build(f"{cls.__name__}Picked")  # type: ignore[return-value]

    @classmethod
    def pick_opaque(cls, *names: str) -> type[Schema]:  # honest: "some schema"
        return pick(cls, *names).build(f"{cls.__name__}Picked")


class IrisP(_Pickable):
    sepal_length: float
    sepal_width: float
    petal_length: float


class SepalOnly(IrisP.pick("sepal_length", "sepal_width")):  # case: b1 class X(Iris.pick(...)) as base expect: ok
    pass


class SepalOnly2(IrisP.pick_opaque("sepal_length", "sepal_width")):  # case: b1 class X(pick_opaque(...)) as base expect: ok
    pass


def use_b1(s: DataFrame[SepalOnly], s2: DataFrame[SepalOnly2]) -> None:
    needs_petal(s)  # case: b1 type[Self] lie: dropped column still visible (want err) expect: err
    needs_petal(s2)  # case: b1 opaque base: petal unknown (want err) expect: err
    reveal_type(SepalOnly2.sepal_length)  # case: b1 opaque base: kept column visible?


SepalAlias = IrisP.pick("sepal_length")  # case: b1 alias = Iris.pick(...) usable as type? expect: ok


def use_alias(s: DataFrame[SepalAlias]) -> None:  # case: b1 DataFrame[alias] annotation expect: ok
    pass


# --- (b2) fields written out + verified against the derivation at import time ---


class SepalV(VerifiedSchema, derive=pick(Iris, "sepal_length", "sepal_width")):  # case: b2 class kwarg derive= expect: ok
    sepal_length: float
    sepal_width: float


class NoSpecies(VerifiedSchema, derive=drop(Iris, "species")):
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float


def use_b2(s: DataFrame[SepalV], n: DataFrame[NoSpecies]) -> None:
    needs_petal(s)  # case: b2 SepalV has no petal expect: err
    needs_petal(n)  # case: b2 NoSpecies has petal expect: ok
