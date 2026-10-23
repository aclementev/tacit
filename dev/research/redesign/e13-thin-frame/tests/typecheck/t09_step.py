# ruff: noqa: B015, B018
"""@tc.step keeps the decorated signature (bare and with arguments, generic, optional)."""

from typing import reveal_type

from _schemas import Customers, HasEventTs, NetAmount, NetOrders, Orders

import tacit_thin as tc


@tc.step
def clean(o: Orders) -> NetOrders:
    return NetOrders.extend(o, NetAmount(net_amount=o.amount))


@tc.step(validate=True)
def checked(o: Orders, c: Customers | None = None) -> Orders:
    return o


@tc.step(name="keep-recent")
def generic[F: HasEventTs](df: F) -> F:
    return df


def use(o: Orders, c: Customers) -> None:
    # @feature @step preserves signatures
    reveal_type(clean(o))  # R: NetOrders
    reveal_type(checked(o, None))  # R: Orders
    clean(c)  # E: wrong frame into a decorated step
    checked(o, o)  # E: Orders is not Customers | None
    generic(o)  # E: Orders is not HasEventTs
