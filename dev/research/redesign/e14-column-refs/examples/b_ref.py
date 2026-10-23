# ruff: noqa: B015, B018
"""Injected bugs, spelling 2 (`Schema.x` refs)."""

from tacit_r import DataFrame

from schemas import Keyed, NetAmount, Order, RawCustomer, RawOrder


def bugs(orders: DataFrame[RawOrder], customers: DataFrame[RawCustomer], o2: DataFrame[Order]) -> None:
    # @feature bug matrix
    orders.filter(RawOrder.statuz != "cancelled")  # E: B1 typo
    orders.filter(RawOrder.status > 5)  # E: B2 str compared with int
    orders.filter(RawCustomer.country == "DE")  # E: B3 other frame's column
    NetAmount.build(orders, net_amount=RawOrder.amount - RawOrder.discount)  # E: B4 nullable into non-null
    x: DataFrame[Order] = orders.mutate(net_amount=RawOrder.amount)  # E: B5 forgot to conform
    o2.group_by(Order.status).agg(t=Order.net_amount)  # E: B6 agg of a non-reduced column
    orders.join(customers, [(RawOrder.customer_id, RawCustomer.country)])  # E: B7 int key vs str key


def bad_generic[S: Keyed](df: DataFrame[S]) -> DataFrame[S]:
    return df.filter(RawOrder.status == "x")  # E: B8 column outside the generic bound
