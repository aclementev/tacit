import ibis
import ibis.expr.types as ir
from typing import reveal_type

import tacit
from tacit import DataFrame, Schema, contract


class Iris(Schema):
    sepal_length: float
    sepal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


def f(df: DataFrame[Iris], raw: ir.Table):
    reveal_type(df)  # L13
    reveal_type(df.sepal_length)  # L14 attribute column
    reveal_type(df.sepal_lenght)  # L15 typo
    reveal_type(df["sepal_length"])  # L16
    reveal_type(df.sepal_length / df.sepal_width)  # L17
    reveal_type(df.sepal_length + df.sepal_width)  # L18
    reveal_type(df.sepal_length > 5)  # L19
    reveal_type(df.sepal_length * 2.0)  # L20
    reveal_type(df.mutate(x=df.sepal_length))  # L21
    reveal_type(df.filter(df.sepal_length > 5))  # L22
    reveal_type(df.species.upper())  # L23
    reveal_type(df.sepal_length.sum())  # L24
    reveal_type(Iris.cast(raw))  # L25
    reveal_type(Iris.parse(raw))  # L26
    reveal_type(IrisFeatures.cast(raw))  # L27
    reveal_type(raw)  # L28
    reveal_type(raw.sepal_length)  # L29


@contract
def bare(df: DataFrame[Iris], n: int = 1) -> DataFrame[IrisFeatures]:
    return IrisFeatures.cast(df)


@contract(validate=True)
def bare_validate(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    return IrisFeatures.cast(df)


@contract(returns=IrisFeatures)
def with_returns(df: DataFrame[Iris], n: int = 1) -> ir.Table:
    return df


@contract(returns=IrisFeatures, validate=True)
def with_returns_validate(df: DataFrame[Iris]) -> ir.Table:
    return df


reveal_type(bare)  # L51
reveal_type(bare_validate)
reveal_type(with_returns)
reveal_type(with_returns_validate)
reveal_type(contract)
reveal_type(Iris)
reveal_type(DataFrame)
reveal_type(ir.Table)


def g(df: DataFrame[Iris]):
    reveal_type(bare(df))
    reveal_type(with_returns(df))
    reveal_type(with_returns(df, n=2))
    bare("not a df")  # arg-type error expected
    bare(df, n="x")  # arg-type error expected
    with_returns(df, n="x")  # arg-type error expected
    with_returns(42)  # arg-type error expected
