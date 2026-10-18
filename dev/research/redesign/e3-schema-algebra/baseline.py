from typing import reveal_type

import ibis.expr.types as ir
from tacit import DataFrame, Schema


class Orders(Schema):
    id: int
    amount: float


class Customers(Schema):
    id: int
    name: str


class BigOrders(Orders):
    flag: bool


def f(df: DataFrame[Orders]) -> None:
    reveal_type(df)  # case: df
    reveal_type(df.id)  # case: df.id
    reveal_type(df.nonexistent)  # case: df.nonexistent (no name checking)
    reveal_type(df.filter(df.id.notnull()))  # case: df.filter(...) drops S
    reveal_type(Orders.cast(df))  # case: Orders.cast(df)


def forgot_cast(t: ir.Table) -> DataFrame[Orders]:
    return t  # case: ir.Table -> DataFrame[Orders] expect: err


def wrong_schema(df: DataFrame[Customers]) -> DataFrame[Orders]:
    return df  # case: DataFrame[Customers] -> DataFrame[Orders] expect: err


def child_to_parent(df: DataFrame[BigOrders]) -> DataFrame[Orders]:
    return df  # case: DataFrame[BigOrders] -> DataFrame[Orders] (invariant) expect: err


def not_a_frame(df: DataFrame[Orders]) -> int:
    return df  # case: DataFrame[Orders] -> int expect: err
