"""Q5 benchmark. usage: uv run python bench_lazy.py 1000000 10000000"""
import os, sys, time, json, gc, warnings
import ibis
from common import *
from ibisval import validate, build_plan
from lazy_proto import guard
warnings.filterwarnings("ignore")
REPEAT = int(os.environ.get("REPEAT", 3))
plan = build_plan(Customer); plan_u = build_plan(Customer, ["id"])

def Q(x):   # a typical downstream query touching 2 of 10 columns
    return x.group_by("status").aggregate(total=x.amount.sum(), n=x.count()).to_pyarrow()

def bench(label, fn):
    ts, cs, out = [], [], "ok"
    for i in range(REPEAT + 1):
        t0 = time.perf_counter(); c0 = time.process_time()
        try: fn()
        except Exception as e: out = f"{type(e).__name__}: {str(e).splitlines()[0][:90]}"
        w, c = time.perf_counter() - t0, time.process_time() - c0
        if i: ts.append(w); cs.append(c)
    r = dict(label=label, min_s=round(min(ts), 3), cpu_min_s=round(min(cs), 3), outcome=out)
    print(json.dumps(r), flush=True); return r

def two_queries_eager(t):
    validate(Customer, t, plan); Q(t); Q(t)
def two_queries_lazy(t):
    g = guard(Customer, t, plan); Q(g); Q(g)

res = []
for n in map(int, sys.argv[1:]):
    con, t = make_con(n)
    tag = f"n={n:,} valid"
    res += [
        bench(f"{tag} | baseline: Q(t) no validation", lambda: Q(t)),
        bench(f"{tag} | eager native: validate(t) then Q(t)", lambda: (validate(Customer, t, plan), Q(t))),
        bench(f"{tag} | eager pandera: Customer.parse(t) then Q", lambda: Q(Customer.parse(t))),
        bench(f"{tag} | LAZY row-guard: Q(guard(t))", lambda: Q(guard(Customer, t, plan))),
        bench(f"{tag} | LAZY row-guard + unique(id) scalar subquery", lambda: Q(guard(Customer, t, plan_u))),
        bench(f"{tag} | 2 queries, eager native (validate once)", lambda: two_queries_eager(t)),
        bench(f"{tag} | 2 queries, lazy guard (validated per query)", lambda: two_queries_lazy(t)),
    ]
    con.disconnect(); del con, t; gc.collect()
    con, t = make_con(n, bad_rate=0.001)
    tag = f"n={n:,} bad=0.1%"
    res += [
        bench(f"{tag} | eager native validate(t) (report)", lambda: validate(Customer, t, plan)),
        bench(f"{tag} | LAZY Q(guard(t)) (fails at first bad row)", lambda: Q(guard(Customer, t, plan))),
    ]
    con.disconnect(); del con, t; gc.collect()

# semantics demos at 1M
con, t = make_con(1_000_000)
con.raw_sql("UPDATE t SET age = -5 WHERE id = 999999")      # one bad row, at the very end
print("\n-- one bad row at the end of 1M rows --")
print("eager report ok?        :", validate(Customer, t, plan).ok)
for name, fn in [("lazy .limit(10)", lambda: guard(Customer, t, plan).limit(10).to_pyarrow().num_rows),
                 ("lazy count()", lambda: guard(Customer, t, plan).count().execute()),
                 ("lazy select(id) (col pruning)", lambda: guard(Customer, t, plan).select("id").count().execute())]:
    try: print(f"{name:32s}:", fn())
    except Exception as e: print(f"{name:32s}: RAISES {type(e).__name__}: {str(e)[:100]}")
# pruning hazard: guard as a *column* (mutate) instead of a filter
bad_t = t.mutate(__g=ibis.cases((t.age < 0, __import__('lazy_proto')._error("boom")), else_=True))
print("mutate-column guard, then select(id).count():", bad_t.select("id").count().execute(), "(guard silently pruned)")
con.raw_sql("UPDATE t SET id = 5 WHERE id = 6")
try: print("lazy unique:", guard(Customer, t, plan_u).count().execute())
except Exception as e: print("lazy unique: RAISES", type(e).__name__, str(e)[:100])
json.dump(res, open("results_lazy_" + "_".join(sys.argv[1:]) + ".json", "w"), indent=1)
