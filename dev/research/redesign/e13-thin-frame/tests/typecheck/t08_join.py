# ruff: noqa: B015, B018
"""Typed join scope: tc.join(left, right, on=...) -> Join[L, R] with typed views."""

from typing import reveal_type

from _schemas import Customers, OrderWithCountry, Orders

import tacit_thin as tc


def joins(o: Orders, c: Customers) -> None:
    # @feature join scope: typed views and lambda inference
    j = tc.join(o, c, on=lambda lo, rc: lo.customer_id == rc.customer_id)
    reveal_type(j)  # R: Join[Orders, Customers]
    reveal_type(j.left)  # R: Orders
    reveal_type(j.right.country)  # R: Column[str]
    tc.join(o, c, on=lambda lo, rc: lo.customer_id == rc.custmer_id)  # E: typo in the predicate
    tc.join(o, c, on=lambda lo, rc: lo.customer_id + rc.customer_id)  # E: non-boolean predicate
    tc.join(o, c, on=[(o.customer_id, c.customer_id)])  # ok: pairs form
    # @feature join output built by the constructor (no collisions possible)
    reveal_type(OrderWithCountry(order_id=j.left.order_id, country=j.right.country, amount=j.left.amount))  # R: OrderWithCountry
    OrderWithCountry(order_id=j.left.order_id, country=j.left.country, amount=j.left.amount)  # E: country is on the right side
    OrderWithCountry(order_id=j.left.order_id, country=j.right.name, amount=j.right.customer_id)  # ok: int widens to float
    OrderWithCountry(order_id=j.left.order_id, country=j.right.customer_id, amount=j.left.amount)  # E: int into str
