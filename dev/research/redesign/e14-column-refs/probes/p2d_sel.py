# ruff: noqa
from typing import reveal_type
import tacit_r as tr
from tacit_r import Column, DataFrame
class Orders(tr.Schema):
    amount: Column[float]
def f(o: DataFrame[Orders]) -> None:
    o.select(12345)
    o.select(o.c.amout)
    o.drop(123)
