# ruff: noqa
"""Task 5: at runtime a tacit column IS the ibis column; every ibis method is callable."""
from datetime import datetime

import ibis
import ibis.expr.types as ir
import tacit_next as tc
from tacit_next import Column


class O(tc.Frame):
    amount: Column[float]
    note: Column[str]
    ts: Column[datetime]
    tags: Column[str]


raw = ibis.memtable({"amount": [1.5, 4.0], "note": ["a,b", "c"], "ts": [datetime(2024, 1, 1, 10, 30), datetime(2024, 2, 1)],
                     "tags": ["x", "y"]})
o = O.parse(raw)
print("type(o.amount) =", type(o.amount).__name__, "| is ir.FloatingColumn:", isinstance(o.amount, ir.FloatingColumn))
print("same object as the table column:", o.amount.equals(o.ibis.amount))
missing = []
for name in dir(type(o.amount)):
    if not name.startswith("_") and not hasattr(o.amount, name):
        missing.append(name)
print("ibis public attributes not reachable at runtime:", missing)
con = ibis.duckdb.connect()
print(con.to_pyarrow(o.ibis.select(log=o.amount.log(), parts=o.note.split(","), minute=o.ts.minute(),
                                   cs=o.amount.cumsum(order_by=o.ts), p=o.amount ** 2)).to_pylist())
