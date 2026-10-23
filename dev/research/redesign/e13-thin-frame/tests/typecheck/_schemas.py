"""Shared frames for the typecheck cases (no expected errors in this file)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

import tacit_thin as tc
from tacit_thin import Column


class Orders(tc.Frame):
    order_id: Column[int]
    customer_id: Column[int]
    order_ts: Column[datetime]
    day: Column[date]
    status: Column[str]
    amount: Column[float] = tc.field(ge=0, description="gross amount")
    discount: Column[float | None]
    price: Column[Decimal] = tc.field(dtype="decimal(12, 2)")
    flag: Column[bool]
    note: Column[str | None]


class AnnOrders(tc.Frame):
    """Same constraints, Annotated spelling."""

    order_id: Annotated[Column[int], tc.unique()]
    amount: Annotated[Column[float], tc.ge(0), tc.dtype("float32")]
    discount: Annotated[Column[float | None], tc.ge(0)]


class Customers(tc.Frame):
    customer_id: Column[int]
    name: Column[str]
    country: Column[str] = tc.field(length=2)


class NetAmount(tc.Frame):
    net_amount: Column[float]


class NetOrders(Orders, NetAmount):
    pass


class Scored(tc.Frame):
    score: Column[float]


class ScoredOrders(Orders, Scored):
    pass


class ScoredCustomers(Customers, Scored):
    pass


class HasEventTs(tc.Frame):
    event_ts: Column[datetime]


class Clicks(HasEventTs):
    user_id: Column[int]
    url: Column[str]


class Stats(tc.Frame):
    status: Column[str]
    n: Column[int]
    total: Column[float]


class OrderWithCountry(tc.Frame):
    order_id: Column[int]
    country: Column[str]
    amount: Column[float]


class Proj2(tc.Frame):
    label: Column[str]
    amount: Column[float]
