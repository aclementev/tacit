import ibis
import tacit_next as tc
from tacit_next import Column


class A(tc.Frame):
    x: Column[int]


class B(tc.Frame):
    y: Column[str]


def f(a: A) -> int:
    return 1


raw = ibis.table({"x": "int"})
f(raw)          # line 18: raw ir.Table where Frame expected -> expect ERROR
f(5)            # line 19: int -> expect ERROR
f(A.cast(raw))  # line 20: OK
bb = B.cast(ibis.table({"y": "string"}))
f(bb)           # line 22: wrong frame -> expect ERROR
