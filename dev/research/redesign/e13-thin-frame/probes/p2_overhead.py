"""Micro-benchmark: E8 wrapper (W) vs E13 thin subclass (T) vs plain ibis. Expression building only."""
import timeit

import ibis

import tacit_next as W
import tacit_thin as T


class OW(W.Frame):
    order_id: W.Column[int]
    status: W.Column[str]
    amount: W.Column[float]


class OT(T.Frame):
    order_id: T.Column[int]
    status: T.Column[str]
    amount: T.Column[float]


t = ibis.table({"order_id": "int64", "status": "string", "amount": "float64"}, name="t")
w, th = OW.cast(t), OT.conform(t)
cases = {
    "column access": (lambda: t.amount, lambda: w.amount, lambda: th.amount),
    "filter (schema-preserving)": (lambda: t.filter(t.amount > 1), lambda: w.filter(w.amount > 1), lambda: th.filter(th.amount > 1)),
    "mutate (ibis op)": (lambda: t.mutate(x=t.amount * 2), lambda: w.ibis.mutate(x=w.amount * 2), lambda: th.mutate(x=th.amount * 2)),
    "cast/conform (memoised)": (lambda: t, lambda: OW.cast(t), lambda: OT.conform(t)),
    "constructor projection": (lambda: t.select(order_id=t.order_id), None, None),
}
n = 2000
print(f"{'operation':28} {'plain ibis':>12} {'W (E8)':>12} {'T (E13)':>12}   (us per call)")
for name, fns in cases.items():
    row = [f"{timeit.timeit(f, number=n) / n * 1e6:10.1f}" if f else "         -" for f in fns]
    print(f"{name:28} {row[0]:>12} {row[1]:>12} {row[2]:>12}")
