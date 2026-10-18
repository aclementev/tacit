"""C. Carrying over parent columns without retyping them.

E-delta: new columns live in their own Frame ("delta"); the output schema
inherits from both. The delta constructor is fully checked; extend() re-checks
coverage at runtime (metadata only).
"""

from collections.abc import Callable
from typing import reveal_type

import ibis

from proto.aliases_facade import Float64, String
from proto.frame import Frame

IRIS_CSV = "../../../../../examples/data/iris.csv"


class Iris(Frame):
    sepal_length: Float64
    sepal_width: Float64
    petal_length: Float64
    petal_width: Float64
    species: String


class Ratios(Frame):  # the delta: only the NEW columns
    sepal_ratio: Float64
    petal_area: Float64


class IrisFeatures(Iris, Ratios):
    pass


def engineer(iris: Iris) -> IrisFeatures:
    return IrisFeatures.extend(
        iris,
        Ratios(
            sepal_ratio=iris.sepal_length / iris.sepal_width,
            petal_area=iris.petal_length * iris.petal_width,
        ),
    )


def engineer_missing(iris: Iris) -> IrisFeatures:
    return IrisFeatures.extend(iris, Ratios(sepal_ratio=iris.sepal_length / iris.sepal_width))


def engineer_wrong_type(iris: Iris) -> IrisFeatures:
    return IrisFeatures.extend(iris, Ratios(sepal_ratio=iris.species, petal_area=iris.petal_width))


def engineer_wrong_delta(iris: Iris) -> IrisFeatures:
    # statically fine (extend takes any Frame) -> only caught at runtime
    return IrisFeatures.extend(iris, Iris.cast(iris.t))


def probe(f: IrisFeatures) -> None:
    reveal_type(IrisFeatures.__init__)  # full projection constructor (7 fields)
    reveal_type(f.sepal_ratio)
    reveal_type(f.species)


def expect_err(label: str, fn: Callable[[], object]) -> None:
    try:
        fn()
        print(f"[runtime] {label}: NO ERROR")
    except Exception as e:
        print(f"[runtime] {label}: {type(e).__name__}: {str(e).splitlines()[0][:90]}")


if __name__ == "__main__":
    iris = Iris.parse(ibis.duckdb.connect().read_csv(IRIS_CSV))
    print(engineer(iris).execute().head(2).to_string())
    expect_err("missing", lambda: engineer_missing(iris))
    expect_err("wrong type", lambda: engineer_wrong_type(iris))
    expect_err("wrong delta", lambda: engineer_wrong_delta(iris))
