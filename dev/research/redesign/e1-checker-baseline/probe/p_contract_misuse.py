import ibis.expr.types as ir
from tacit import DataFrame, Schema, contract


class Input(Schema):
    x: float


class Output(Schema):
    x: float
    y: float


@contract(returns=Output)
def bad_returns_int(df: DataFrame[Input]) -> int:  # should be flagged: not an ir.Table
    return 1


@contract(returns=int)  # should be flagged: not a Schema
def bad_schema(df: DataFrame[Input]) -> ir.Table:
    return df
