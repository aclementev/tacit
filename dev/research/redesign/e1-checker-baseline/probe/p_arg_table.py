import ibis.expr.types as ir
from tacit import DataFrame, Schema


class Iris(Schema):
    a: int


def needs(df: DataFrame[Iris]) -> None: ...


def caller(raw: ir.Table, df: DataFrame[Iris]):
    needs(raw)  # L12 should be an error: ir.Table is not DataFrame[Iris]
    needs(Iris.cast(raw))
    needs(df)
