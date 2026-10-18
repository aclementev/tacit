"""Where does validation time go? (1M rows) + fixed per-call overhead on a 1k-row table."""
import time, statistics, warnings
from common import *
from ibisval import *
warnings.filterwarnings("ignore")

def tmin(fn, n=5):
    fn(); xs=[]
    for _ in range(n):
        t0=time.perf_counter(); fn(); xs.append(time.perf_counter()-t0)
    return min(xs)

con, t = make_con(1_000_000)
plan = build_plan(Customer, ["id"])
print("## standalone single-aggregate cost per check (1M rows, min of 5, wall s)")
tot = 0
for it in plan.items:
    x = tmin(lambda: t.aggregate(b=(~it.pred(t)).cast("int64").sum()).to_pyarrow())
    tot += x; print(f"{it.column:8s} {it.name[:55]:55s} {x*1000:7.1f} ms")
x = tmin(lambda: t.aggregate(b=t.id.nunique()).to_pyarrow()); print(f"{'id':8s} {'unique (count distinct)':55s} {x*1000:7.1f} ms")
print(f"sum of standalone check queries: {tot*1000:.0f} ms")

print("\n## fixed overhead on a 1,000-row table (min of 20, wall ms)")
con, t = make_con(1000)
f = lambda: Customer.parse(t)
print("tacit parse (pandera, 16 queries):", round(tmin(f, 20)*1000, 1), "ms")
print("native validate (1 query)        :", round(tmin(lambda: validate(Customer, t, plan), 20)*1000, 1), "ms")
print("native validate, plan rebuilt    :", round(tmin(lambda: validate(Customer, t), 20)*1000, 1), "ms")
print("Customer._pandera_schema() build :", round(tmin(lambda: Customer._pandera_schema(), 20)*1000, 2), "ms")
sch = Customer._pandera_schema()
print("pandera schema.validate only     :", round(tmin(lambda: sch.validate(t.cast({'created':'timestamp'})), 20)*1000, 1), "ms")
