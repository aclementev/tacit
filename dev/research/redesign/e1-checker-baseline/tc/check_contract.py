"""@contract body is type-checked: wrong return schemas are caught.

Also verifies that @contract(returns=S) relaxes the body return type
while preserving DataFrame[S] at call sites.
"""

import ibis.expr.types as ir

from tacit import DataFrame, Schema, contract


class Input(Schema):
    x: float
    y: float


class Output(Schema):
    x: float
    total: float


# --- positive: explicit cast in body (original pattern) ---


@contract
def correct_body(df: DataFrame[Input]) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y).drop("y"))


@contract(validate=True)
def correct_body_validated(df: DataFrame[Input]) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y).drop("y"))


@contract
def correct_with_extra_param(df: DataFrame[Input], n: int) -> DataFrame[Output]:
    return Output.cast(df.mutate(total=df.x + df.y + n).drop("y"))


# --- positive: @contract(returns=S) relaxes body return type ---


@contract(returns=Output)
def returns_ir_table(df: DataFrame[Input]) -> ir.Table:
    return df.mutate(total=df.x + df.y).drop("y")


@contract(returns=Output)
def returns_dataframe(df: DataFrame[Input]) -> ir.Table:
    return Output.cast(df.mutate(total=df.x + df.y).drop("y"))


@contract(returns=Output, validate=True)
def returns_validated(df: DataFrame[Input]) -> ir.Table:
    return df.mutate(total=df.x + df.y).drop("y")


@contract(returns=Output)
def returns_with_extra_param(df: DataFrame[Input], n: int) -> ir.Table:
    return df.mutate(total=df.x + df.y + n).drop("y")


@contract(returns=Output)
def returns_no_annotation(df: DataFrame[Input]):
    return df.mutate(total=df.x + df.y).drop("y")


# --- call-site types: decorated functions return DataFrame[S] ---


def call_site_explicit_cast(df: DataFrame[Input]) -> DataFrame[Output]:
    return correct_body(df)


def call_site_returns_param(df: DataFrame[Input]) -> DataFrame[Output]:
    return returns_ir_table(df)


def call_site_returns_no_annotation(df: DataFrame[Input]) -> DataFrame[Output]:
    return returns_no_annotation(df)


# --- negative: wrong return type inside body (without returns=) ---


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
