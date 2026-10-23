# ruff: noqa
from typing import reveal_type, Any
import tacit_r as tr
from tacit_r import Column, DataFrame

class Orders(tr.Schema):
    amount: Column[float]

class Customers(tr.Schema):
    country: Column[str]

def f(o: DataFrame[Orders]) -> None:
    o.select(Customers.country)
    o.select(Customers.country, Customers.country)
    o.select(x=Customers.country)
    reveal_type(o.select)
