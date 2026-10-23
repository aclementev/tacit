"""Schema module for the `tacit gen` prototype (E14). Schemas only; `gen_schemas.pyi` is generated."""

from datetime import datetime

import tacit_r as tr
from tacit_r import Column


class Orders(tr.Schema):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    status: Column[str]
    amount: Column[float]
    discount: Column[float | None]


class Customers(tr.Schema):
    customer_id: Column[int]
    country: Column[str]


class Net(tr.Schema):
    net_amount: Column[float]


class NetOrders(Orders, Net):
    pass


class HasEventTs(tr.Schema):
    event_ts: Column[datetime]


class Clicks(HasEventTs):
    url: Column[str]
