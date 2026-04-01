"""DataFrame[S] is usable where ir.Table is expected."""

import ibis
import ibis.expr.types as ir

from tacit import DataFrame, Schema


class Iris(Schema):
    sepal_length: float
    species: str


def takes_ibis_table(t: ir.Table) -> ir.Table:
    return t


def transparent_as_arg(df: DataFrame[Iris]) -> None:
    takes_ibis_table(df)


def transparent_mutate(df: DataFrame[Iris]) -> ir.Table:
    return df.mutate(x=ibis.literal(1))


def transparent_filter(df: DataFrame[Iris]) -> ir.Table:
    return df.filter(df.sepal_length > 5.0)


def transparent_select(df: DataFrame[Iris]) -> ir.Table:
    return df.select("sepal_length", "species")
