# ruff: noqa: B015, B018
"""Injected bugs, spelling 3 (`df.c["x"]`, generated overloads)."""

from tacit_r import DataFrame

from schemas import Keyed, NetAmount, Order, RawCustomer, RawOrder


def bugs(orders: DataFrame[RawOrder], customers: DataFrame[RawCustomer], o2: DataFrame[Order]) -> None:
    # @feature bug matrix
    orders.filter(orders.c["statuz"] != "cancelled")  # E: B1 typo
    orders.filter(orders.c["status"] > 5)  # E: B2 str compared with int
    orders.filter(customers.c["country"] == "DE")  # E: B3 other frame's column
    NetAmount.build(net_amount=orders.c["amount"] - orders.c["discount"])  # E: B4 nullable into non-null
    x: DataFrame[Order] = orders.mutate(net_amount=orders.c["amount"])  # E: B5 forgot to conform
    o2.group_by(o2.c["status"]).agg(t=o2.c["net_amount"])  # E: B6 agg of a non-reduced column
    orders.join(customers, orders.c["customer_id"] == customers.c["country"])  # E: B7 int key vs str key


def bad_generic[S: Keyed](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(df.c["status"] == "x")  # E: B8 column outside the generic bound
