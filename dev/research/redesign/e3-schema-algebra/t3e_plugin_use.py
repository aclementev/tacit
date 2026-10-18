"""3d. Derived schemas via runtime classmethods; typed only by the mypy plugin."""

from typing import Protocol, reveal_type

from cg_models import Iris
from tx import DataFrame, Into, SchemaLike

IrisSepal = Iris.pick("sepal_length", "sepal_width")  # case: d pick() assignment expect: ok
IrisNoSpecies = Iris.drop("species")  # case: d drop() assignment expect: ok
IrisLabelled = Iris.rename(species="label")  # case: d rename() assignment expect: ok
IrisScored = Iris.extend(score=float)  # case: d extend() assignment expect: ok
Bad = Iris.pick("sepal_lenght")  # case: d pick() unknown column expect: err


class HasPetalP(SchemaLike, Protocol):
    petal_length: float


class HasLabelP(SchemaLike, Protocol):
    label: str


def needs_petal[S: HasPetalP](df: DataFrame[S]) -> None: ...
def needs_label[S: HasLabelP](df: DataFrame[S]) -> None: ...
def to_scored[O: Iris](df: Into[O], out: type[O]) -> DataFrame[O]: ...


def use(s: DataFrame[IrisSepal], n: DataFrame[IrisNoSpecies], l: DataFrame[IrisLabelled], i: DataFrame[Iris]) -> None:  # case: d DataFrame[Derived] annotations expect: ok
    reveal_type(IrisSepal.sepal_length)  # case: d picked column type
    needs_petal(s)  # case: d pick() result has no petal expect: err
    needs_petal(n)  # case: d drop() result keeps petal expect: ok
    needs_label(l)  # case: d rename() result has label expect: ok
    reveal_type(to_scored(i, IrisScored))  # case: d extend() result <: Iris (B2) expect: ok
