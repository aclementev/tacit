"""@contract body is type-checked: wrong return schemas are caught."""

import ibis.expr.types as ir

from tacit import DataFrame, Schema, contract


class Input(Schema):
    x: float
    y: float


class Output(Schema):
    x: float
    total: float


# --- positive: correctly typed contract bodies ---


@contract
def correct_body(df: DataFrame[Input]) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y).drop("y"))


@contract(validate=True)
def correct_body_validated(df: DataFrame[Input]) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y).drop("y"))


@contract
def correct_with_extra_param(df: DataFrame[Input], n: int) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y + n).drop("y"))


# --- negative: wrong return type inside body ---


@contract
def forgot_cast_in_body(df: DataFrame[Input]) -> DataFrame[Output]:
    return df.mutate(total=df.x + df.y).drop("y")  # pyright: ignore[reportReturnType]


@contract
def wrong_schema_in_body(df: DataFrame[Input]) -> DataFrame[Output]:
    return Input.cast(df)  # pyright: ignore[reportReturnType]


@contract
def raw_table_in_body(df: DataFrame[Input]) -> DataFrame[Output]:
    t: ir.Table = df
    return t  # pyright: ignore[reportReturnType]
