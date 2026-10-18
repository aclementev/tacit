"""D. Subtyping semantics with nominal frame classes, and structural "has columns" protocols."""

from typing import Protocol, reveal_type

import ibis

from proto.aliases_facade import Float64, NumCol, String
from proto.frame import Frame

IRIS_CSV = "../../../../../examples/data/iris.csv"


# Shape 1: inheritance => IrisFeatures IS-A Iris (covariant "at least these columns")
class Iris(Frame):
    sepal_length: Float64
    sepal_width: Float64
    species: String


class IrisFeatures(Iris):
    sepal_ratio: Float64


# Shape 2: shared abstract column set => siblings, so Iris2 and Features2 are NOT
# assignable to each other (today's invariance), while IrisCols means "at least".
class IrisCols(Frame):
    sepal_length: Float64
    sepal_width: Float64
    species: String


class Iris2(IrisCols):
    pass


class Features2(IrisCols):
    sepal_ratio: Float64


def takes_iris(df: Iris) -> None: ...
def takes_iris2(df: Iris2) -> None: ...
def takes_cols(df: IrisCols) -> None: ...


# Shape 3: structural protocol over column attributes => generic, schema-agnostic code
class HasSepal(Protocol):
    @property
    def sepal_length(self) -> NumCol: ...


def long_sepals[F: Frame](df: F, col: NumCol) -> F:
    return df.filter(col > 5.0)


def long_sepals_proto[F: HasSepal](df: F) -> F:
    reveal_type(df.sepal_length)
    return df


def probe(i: Iris, f: IrisFeatures, i2: Iris2, f2: Features2) -> None:
    takes_iris(f)  # shape 1: accepted (subclass)
    takes_iris2(f2)  # shape 2: error wanted (siblings)
    takes_cols(f2)  # shape 2: accepted
    takes_iris(i2)  # error wanted (unrelated)
    reveal_type(long_sepals_proto(f))  # IrisFeatures via protocol
    reveal_type(long_sepals_proto(f2))
    reveal_type(long_sepals(f, f.sepal_length))


if __name__ == "__main__":
    raw = ibis.duckdb.connect().read_csv(IRIS_CSV).select("sepal_length", "sepal_width", "species")
    f = IrisFeatures.cast(raw.mutate(sepal_ratio=raw.sepal_length / raw.sepal_width))
    print(type(long_sepals(f, f.sepal_length)).__name__, long_sepals(f, f.sepal_length).t.count().execute())
    try:
        Iris.cast(f.t)  # runtime strict check disagrees with static subtyping
    except TypeError as e:
        print("[runtime] strict Iris.cast(features):", e)
