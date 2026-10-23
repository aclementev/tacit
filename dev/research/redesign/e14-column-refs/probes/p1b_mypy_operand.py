# ruff: noqa
from p1_owner_variance import Orders, Big, Customers, Ref
from typing import reveal_type

x = Customers.score
reveal_type(x)
reveal_type(Orders.amount + x)  # want error
y = Orders.amount
reveal_type(Big.extra + y)  # want ok
z = Big.extra
reveal_type(Orders.amount + z)  # class-level owner: error
reveal_type(Orders.amount.__add__(Customers.score))
reveal_type(Orders.amount > Customers.score)
w: Ref[Customers, float] = Customers.score
reveal_type(Orders.amount + w)
