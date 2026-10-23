# ruff: noqa: B015, B018
"""Construction: the dataclass_transform constructor as a checked projection / aggregation."""

from typing import reveal_type

from _schemas import NetAmount, Orders, Stats

import tacit_thin as tc
from tacit_thin import Column


class Proj(tc.Frame):
    order_id: Column[int]
    amount: Column[float]
    label: Column[str]


def projection(o: Orders) -> None:
    # @feature constructor: missing / extra / wrong-type columns
    reveal_type(Proj(order_id=o.order_id, amount=o.amount, label=o.status))  # R: Proj
    Proj(order_id=o.order_id, amount=o.amount)  # E: missing label
    Proj(order_id=o.order_id, amount=o.amount, label=o.status, bogus=o.amount)  # E: extra column
    Proj(order_id=o.order_id, amount=o.status, label=o.status)  # E: str into float
    Proj(order_id=o.amount, amount=o.amount, label=o.status)  # E: float into int
    Proj(order_id=o.order_id, amount=o.order_id, label=o.status)  # ok: int widens to float
    Proj(order_id=o.order_id, amount=o.amount, label="web")  # ok: literal broadcast
    Proj(order_id=o.order_id, amount=o.amount, label=3)  # E: int literal into str
    Proj(order_id=o.order_id, amount=o.amount, label=o.status.upper())  # ok
    Proj(o.order_id, o.amount, o.status)  # E: positional arguments
    NetAmount(net_amount=o.amount * (1 - o.discount.fill_null(0)))  # ok


def aggregation(o: Orders) -> None:
    # @feature implicit GROUP BY via reductions
    reveal_type(Stats(status=o.status, n=o.order_id.count(), total=o.amount.sum()))  # R: Stats
    Stats(status=o.status, n=o.amount.sum(), total=o.amount.sum())  # E: float sum into int
    Stats(status=o.status, n=o.order_id.count(), total=o.status.max())  # E: str max into float
    Stats(status=o.status, n=o.order_id.count(), total=o.amount.mean())  # ok
    # @feature explicit aggregate_by([...])
    by_status = Stats.aggregate_by([o.status])
    reveal_type(by_status(status=o.status, n=o.order_id.count(), total=o.amount.sum()))  # R: Stats
    by_status(status=o.status, n=o.order_id.count())  # E: missing total
    by_status(status=o.status, n=o.amount.sum(), total=o.amount.sum())  # E: float into int
    Stats.aggregate_by(o.status)  # E: by must be a sequence
