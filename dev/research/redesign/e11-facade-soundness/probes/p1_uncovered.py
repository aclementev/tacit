# ruff: noqa
"""Task 1/5: what checkers say when a user calls a method the facade does not type."""
from datetime import datetime
from typing import reveal_type

import tacit_next as tc
from tacit_next import Column


class O(tc.Frame):
    amount: Column[float]
    qty: Column[int]
    note: Column[str]
    ts: Column[datetime]


def f(o: O) -> None:
    reveal_type(o.amount.log())             # L1 unreachable: NumericValue.log
    reveal_type(o.note.split(","))          # L2 unreachable: StringValue.split
    reveal_type(o.amount ** 2)              # L3 unreachable operator __pow__
    reveal_type(o.amount.mean().round(2))   # L4 Scalar.round not on facade
    reveal_type(o.ts.minute())              # L5 TimestampValue.minute
    reveal_type(o.amount.cumsum())          # L6 window fn
    reveal_type(o.amount.lag())             # L7 window fn
    reveal_type(o.amount.coalesce(0.0))     # L8 via ir.Value (inherited)
    reveal_type(o.amount.typeof())          # L9 via ir.Value
    reveal_type(o.note.like("a%"))          # L10 StringValue.like
    reveal_type(o.ts - o.ts)                # L11 timestamp diff -> interval
    reveal_type(o.qty.typo())               # L12 genuine typo (must stay an error)
    reveal_type(o.note.abs())               # L13 wrong method for family (must stay an error)
    reveal_type(tc.as_ibis(o.amount).log()) # L14 escape hatch
    reveal_type(tc.as_column(tc.as_ibis(o.amount).log()))  # L15 escape hatch back
