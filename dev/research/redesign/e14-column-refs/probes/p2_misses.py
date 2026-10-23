# ruff: noqa
from typing import reveal_type, Any
from collections.abc import Iterable
import ibis.selectors as s
import ibis.expr.types as ir
from ibis import Deferred
import tacit_r as tr
from tacit_r import Column, DataFrame, Ref

class Orders(tr.Schema):
    customer_id: Column[int]
    amount: Column[float]
    score: Column[float]

class Customers(tr.Schema):
    customer_id: Column[int]
    country: Column[str]
    score: Column[float]

def f(o: DataFrame[Orders], c: DataFrame[Customers]) -> None:
    a: s.Selector = Customers.country  # pyright select miss?
    b: Iterable[Any] = Customers.country
    d: ir.Column = Customers.country.desc()  # pyrefly order_by miss?
    e: Deferred = Customers.country.desc()
    g: Ref[Orders, Any] = Customers.country.desc()
    reveal_type(Customers.country.desc())
    h: Ref[Orders, Any] = Customers.country
    o.order_by(Customers.country)
    reveal_type(Orders.score + Customers.score)  # same value type, unrelated owners
    o.filter(Orders.score + Customers.score > 0)
    k: tuple[Ref[Orders, Any], Ref[Customers, Any]] = (Customers.customer_id, Orders.customer_id)
    l: list[tuple[Ref[Orders, Any], Ref[Customers, Any]]] = [(Customers.customer_id, Orders.customer_id)]
