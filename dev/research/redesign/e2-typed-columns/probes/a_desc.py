"""A/C/D probe. aliases_desc is replaced by gen_a.sh (aliases_ann / aliases_desc)."""

from collections.abc import Callable
from typing import reveal_type

import ibis

from proto.aliases_desc import Float64, String
from proto.frame import Frame

IRIS_CSV = "../../../../../examples/data/iris.csv"


class Iris(Frame):
    sepal_length: Float64
    sepal_width: Float64
    petal_length: Float64
    petal_width: Float64
    species: String


class IrisFeatures(Iris):
    sepal_ratio: Float64
    petal_area: Float64


def expect_err(label: str, fn: Callable[[], object]) -> None:
    try:
        fn()
        print(f"[runtime] {label}: NO ERROR")
    except Exception as e:
        print(f"[runtime] {label}: {type(e).__name__}: {str(e).splitlines()[0][:90]}")


# ---- A: attribute typing ---------------------------------------------------
def engineer(iris: Iris) -> IrisFeatures:
    reveal_type(iris.sepal_length)  # want: FloatingColumn
    reveal_type(iris.species)  # want: StringColumn
    reveal_type(Iris.sepal_length)  # class access
    reveal_type(iris.sepal_length / iris.sepal_width)
    reveal_type(iris.species.upper())
    reveal_type(iris.sepal_length.mean())
    reveal_type(iris.sepal_length > 5.0)  # literal comparison (ibis: Value.__gt__(Value))
    reveal_type(iris.species == "setosa")  # ibis: __eq__(Value) -> falls back to bool
    reveal_type((iris.sepal_length / iris.sepal_width).mean())  # ibis: NumericValue.mean missing
    return IrisFeatures(
        sepal_length=iris.sepal_length,
        sepal_width=iris.sepal_width,
        petal_length=iris.petal_length,
        petal_width=iris.petal_width,
        species=iris.species,
        sepal_ratio=iris.sepal_length / iris.sepal_width,
        petal_area=iris.petal_length * iris.petal_width,
    )


def typos(iris: Iris) -> None:
    expect_err("instance typo", lambda: iris.sepal_lenght)  # want: error
    expect_err("class typo", lambda: Iris.sepal_lenght)  # want: error
    expect_err("str.mean()", lambda: iris.species.mean())  # want: error
    expect_err("float.upper()", lambda: iris.sepal_length.upper())  # want: error


# ---- C: constructor as a checked projection ---------------------------------
def c0_missing_petal_area(iris: Iris) -> IrisFeatures:
    return IrisFeatures(  # want: error
        sepal_length=iris.sepal_length,
        sepal_width=iris.sepal_width,
        petal_length=iris.petal_length,
        petal_width=iris.petal_width,
        species=iris.species,
        sepal_ratio=iris.sepal_length / iris.sepal_width,
    )


def c1_unexpected_col(iris: Iris) -> IrisFeatures:
    return IrisFeatures(  # want: error
        sepal_length=iris.sepal_length,
        sepal_width=iris.sepal_width,
        petal_length=iris.petal_length,
        petal_width=iris.petal_width,
        species=iris.species,
        sepal_ratio=iris.sepal_length / iris.sepal_width,
        petal_area=iris.petal_length * iris.petal_width,
        bogus=iris.species,
    )


def c2_str_expr_into_float_col(iris: Iris) -> IrisFeatures:
    return IrisFeatures(  # want: error
        sepal_length=iris.sepal_length,
        sepal_width=iris.sepal_width,
        petal_length=iris.petal_length,
        petal_width=iris.petal_width,
        species=iris.species,
        sepal_ratio=iris.species.upper(),
        petal_area=iris.petal_length * iris.petal_width,
    )


def c3_float_expr_into_str_col(iris: Iris) -> IrisFeatures:
    return IrisFeatures(  # want: error
        sepal_length=iris.sepal_length,
        sepal_width=iris.sepal_width,
        petal_length=iris.petal_length,
        petal_width=iris.petal_width,
        species=iris.petal_width,
        sepal_ratio=iris.sepal_length / iris.sepal_width,
        petal_area=iris.petal_length * iris.petal_width,
    )


def bad_constructs(iris: Iris) -> None:
    expect_err("missing petal_area", lambda: c0_missing_petal_area(iris))
    expect_err("unexpected col", lambda: c1_unexpected_col(iris))
    expect_err("str expr into float col", lambda: c2_str_expr_into_float_col(iris))
    expect_err("float expr into str col", lambda: c3_float_expr_into_str_col(iris))


# ---- B4/D: typed delegated subset, subtyping ---------------------------------
def takes_iris(df: Iris) -> int:
    return len(df.t.columns)


def b_and_d(iris: Iris, feats: IrisFeatures) -> None:
    reveal_type(iris.filter(iris.sepal_length > iris.petal_length))  # want: Iris
    reveal_type(iris.filter(Iris.sepal_length > 5.0))  # class-access predicate
    reveal_type(iris.t.mutate(x=iris.sepal_length * 2))  # ir.Table
    reveal_type(iris.mutate(x=iris.sepal_length * 2))
    expect_err("typo via .t", lambda: reveal_type(iris.t.zzz))  # back to ibis: no detection
    takes_iris(feats)  # D: IrisFeatures is an Iris (nominal subclass) -> accepted
    expect_err("Iris.cast(feats.t) strict", lambda: Iris.cast(feats.t))


if __name__ == "__main__":
    raw = ibis.duckdb.connect().read_csv(IRIS_CSV)
    iris = Iris.parse(raw)
    feats = engineer(iris)
    print(feats)
    print(feats.execute().head(2).to_string())
    typos(iris)
    bad_constructs(iris)
    b_and_d(iris, feats)
    print("filter via class access:", iris.filter(Iris.sepal_length > 5.0).t.count().execute())
    print("takes_iris(feats) at runtime:", takes_iris(feats), "columns (extra cols flow through)")
