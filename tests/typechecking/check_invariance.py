"""DataFrame[A] ≠ DataFrame[B]: the type parameter is invariant."""

from tacit import DataFrame, Schema


class Iris(Schema):
    sepal_length: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


def identity(df: DataFrame[Iris]) -> DataFrame[Iris]:
    return df


def child_not_parent(df: DataFrame[IrisFeatures]) -> DataFrame[Iris]:
    return df  # pyright: ignore[reportReturnType]


def parent_not_child(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    return df  # pyright: ignore[reportReturnType]
