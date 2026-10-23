"""Runtime feasibility of Frame as an ir.Table subclass (run with PYTHONPATH=e13-thin-frame/src)."""
import pickle

import ibis
import ibis.expr.types as ir

import tacit_thin as tc
from tacit_thin import Column


class Orders(tc.Frame):
    order_id: Column[int]
    status: Column[str]
    amount: Column[float]


t = ibis.memtable({"order_id": [1, 2, 3], "status": ["a", "b", "a"], "amount": [1.0, 2.0, 3.5], "extra": [0, 0, 0]})
o = Orders.conform(t)
print("type/isinstance/columns:", type(o).__name__, isinstance(o, ir.Table), o.columns)
print("instance attr:", type(o.amount).__name__, o.amount.get_name())
print("class attr:", type(Orders.amount).__name__)
m = o.mutate(x=o.amount * 2)
print("mutate ->", type(m).__name__, m.columns)
f = o.filter(o.amount > 1.5)
print("filter ->", type(f).__name__, f.count().execute())
g = o.group_by("status").agg(total=o.amount.sum())
print("group_by.agg ->", type(g).__name__, g.order_by("status").execute().to_dict("list"))
print("order_by.limit ->", type(o.order_by(o.amount.desc()).limit(2)).__name__)
j = o.join(t, o.order_id == t.order_id)
print("join ->", type(j).__name__, j.columns)
print("ibis.union(frame, frame):", ibis.union(o, o).count().execute())
try:
    o.amout
except AttributeError as e:
    print("typo AttributeError:", e)
print("pickle roundtrip:", type(pickle.loads(pickle.dumps(o))).__name__)
p = Orders(order_id=o.order_id, status=o.status.upper(), amount=o.amount + 1)
print("constructor ->", type(p).__name__, p.execute().to_dict("list"))
try:
    class Bad(tc.Frame):
        count: Column[int]
except TypeError as e:
    print("collision TypeError:", e)
print("reserved ibis names:", len(tc.IBIS_TABLE_MEMBERS))
w = o.mutate(rn=ibis.row_number().over(group_by=o.status, order_by=o.amount))
print("window:", w.order_by("order_id").execute().to_dict("list")["rn"])
print("str key:", type(o["status"]).__name__)
print("equals plain:", o.equals(t.select("order_id", "status", "amount")))
con = ibis.duckdb.connect()
con.create_table("orders_copy", o)
print("con.create_table(frame):", con.table("orders_copy").count().execute())
print("to_pandas:", o.to_pandas().shape)
print("cache ->", type(o.cache()).__name__)
