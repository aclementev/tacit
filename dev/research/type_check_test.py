"""
Static typing test: verify pyright treats DataFrame[S] as distinct from ibis.Table.

Run with: uv run pyright research/type_check_test.py
Expected: errors on lines marked # ERROR, no errors on lines marked # OK
"""
from __future__ import annotations

import ibis.expr.types as ir
from typing import Generic, TypeVar

S = TypeVar("S")


class DataFrame(ir.Table, Generic[S]):
    __slots__ = ("_tacit_schema",)

    @classmethod
    def _from_table(cls, table: ir.Table, schema_type: type | None = None) -> DataFrame[S]:
        df = cls(table.op())
        object.__setattr__(df, "_tacit_schema", schema_type)
        return df


class Schema:
    @classmethod
    def parse(cls, table: ir.Table) -> DataFrame:
        return DataFrame._from_table(table, schema_type=cls)

    @classmethod
    def cast(cls, table: ir.Table) -> DataFrame:
        return DataFrame._from_table(table, schema_type=cls)


class Iris(Schema):
    sepal_length: float
    sepal_width: float
    species: str


class IrisFeatures(Iris):
    sepal_ratio: float


# ─── Test cases ──────────────────────────────────────────────

# GOAL 3: Returning ibis.Table where DataFrame[S] is expected should be an error

def good_function(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    """This should be OK — goes through cast()."""
    result = df.mutate(sepal_ratio=df.sepal_length / df.sepal_width)
    return IrisFeatures.cast(result)  # OK


def bad_function(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    """This should be an ERROR — returns raw ibis.Table."""
    result = df.mutate(sepal_ratio=df.sepal_length / df.sepal_width)
    return result  # ERROR: Table is not DataFrame[IrisFeatures]


def also_bad(df: DataFrame[Iris]) -> DataFrame[IrisFeatures]:
    """This should also be an ERROR — wrong schema type."""
    return df  # ERROR: DataFrame[Iris] is not DataFrame[IrisFeatures]


# GOAL 2: DataFrame[S] should be usable wherever ibis.Table is expected

def accepts_ibis_table(table: ir.Table) -> ir.Table:
    return table.mutate(x=1)


def test_transparent(df: DataFrame[Iris]) -> None:
    """DataFrame[S] should pass where ir.Table is expected."""
    result = accepts_ibis_table(df)  # OK: DataFrame is a subclass of Table
    _ = df.sepal_length  # OK: column access
    _ = df.mutate(x=1)  # OK: ibis operations


# GOAL 1: Type annotations should carry schema info through

def pipeline(raw: ir.Table) -> DataFrame[IrisFeatures]:
    iris: DataFrame[Iris] = Iris.parse(raw)  # OK
    transformed = iris.mutate(sepal_ratio=iris.sepal_length / iris.sepal_width)
    features: DataFrame[IrisFeatures] = IrisFeatures.cast(transformed)  # OK
    return features  # OK
