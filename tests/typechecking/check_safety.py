"""Can't forget cast/parse: ir.Table is not assignable to DataFrame[S]."""

import ibis.expr.types as ir

from tacit import DataFrame, Schema


class Iris(Schema):
    sepal_length: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


# --- Positive: these should type-check clean ---


def correct_cast(raw: ir.Table) -> DataFrame[Iris]:
    return Iris.cast(raw)


def correct_cast_child(raw: ir.Table) -> DataFrame[IrisFeatures]:
    return IrisFeatures.cast(raw)


# --- Negative: these SHOULD produce type errors ---


def forgot_cast(raw: ir.Table) -> DataFrame[Iris]:
    return raw  # pyright: ignore[reportReturnType]


def forgot_cast_after_mutate(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    result = df.mutate(sepal_ratio=df.sepal_length / 2.0)
    return result  # pyright: ignore[reportReturnType]
