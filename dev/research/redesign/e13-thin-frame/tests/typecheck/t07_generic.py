# ruff: noqa: B015, B018
"""Generic steps: typed column handles, mixin bounds, optional frames."""

from datetime import datetime
from typing import Any, reveal_type

from _schemas import Clicks, Customers, HasEventTs, NetOrders, Orders

import tacit_thin as tc
from tacit_thin import Column


def dedupe[F: tc.Frame](df: F, key: Column[Any]) -> F:
    return df.distinct(on=key)


def latest_per_key[F: tc.Frame](df: F, key: Column[Any], ts: Column[datetime]) -> F:
    return df.filter(tc.row_number().over(group_by=key, order_by=ts.desc()) == 0)


def recent[F: HasEventTs](df: F, since: datetime) -> F:
    # @feature mixin bounds: typed columns in the generic body
    reveal_type(df.event_ts)  # R: Column[datetime]
    df.event_tss  # E: typo inside the generic body
    return df.filter(df.event_ts >= since)


def maybe(df: Orders | None) -> int:
    return 0 if df is None else 1


def handles(o: Orders, n: NetOrders, c: Customers, k: Clicks) -> None:
    # @feature schema-preserving generic step with typed handles
    reveal_type(dedupe(o, o.order_id))  # R: Orders
    reveal_type(latest_per_key(o, key=o.customer_id, ts=o.order_ts))  # R: Orders
    reveal_type(latest_per_key(n, key=n.customer_id, ts=n.order_ts))  # R: NetOrders
    latest_per_key(o, key=o.customer_id, ts=o.amount)  # E: ts must be a datetime column
    latest_per_key(o, key=o.customer_id, ts=o.discount)  # E: ts nullable float
    # @feature mixin bounds
    reveal_type(recent(k, datetime(2024, 1, 1)))  # R: Clicks
    recent(o, datetime(2024, 1, 1))  # E: Orders has no event_ts mixin
    # @feature optional frame params
    maybe(None)
    maybe(o)
    maybe(c)  # E: Customers is not Orders | None
