# ruff: noqa: B015, B018
"""extend(): Out must subclass type(base) (contravariant Into[Self]); additive generic steps."""

from typing import reveal_type

from _schemas import Customers, NetAmount, NetOrders, Orders, Scored, ScoredCustomers, ScoredOrders, Stats

import tacit_next as tc
from tacit_next import Column


def extend(o: Orders, c: Customers) -> None:
    # @feature extend: Out must subclass the base frame and every delta
    reveal_type(NetOrders.extend(o, NetAmount(net_amount=o.amount)))  # R: NetOrders
    NetOrders.extend(c, NetAmount(net_amount=o.amount))  # E: Customers is not a base of NetOrders
    Stats.extend(o, NetAmount(net_amount=o.amount))  # E: Stats does not subclass Orders
    NetOrders.extend(o, Scored(score=o.amount))  # E: Scored is not a base of NetOrders
    NetOrders.extend(o, NetAmount(net_amount=o.status))  # E: str into float (delta constructor)
    NetOrders.extend(o, NetAmount())  # E: delta missing net_amount
    NetOrders.extend(o)  # E: at least one delta is required


def add_score[O: Scored](df: tc.Into[O], amount: Column[float], out: type[O]) -> O:
    """Reusable additive step: the caller names the output (class ScoredOrders(Orders, Scored))."""
    return out.extend(df, Scored(score=amount * 0.1))


def additive(o: Orders, c: Customers) -> None:
    # @feature additive generic step via Into[O]
    reveal_type(add_score(o, o.amount, ScoredOrders))  # R: ScoredOrders
    add_score(o, o.amount, ScoredCustomers)  # E: ScoredCustomers is not an Orders
    add_score(o, o.amount, NetOrders)  # E: NetOrders is not Scored
    add_score(o, o.status, ScoredOrders)  # E: str handle where float expected
