"""Q6: ibis polars backend: pandera parse vs native one-aggregate validator. usage: uv run python bench_polars.py 1000000"""
import sys, time, warnings
import ibis, duckdb
from ibis.backends.polars import Backend as PB
from common import *
from ibisval import validate, build_plan
warnings.filterwarnings("ignore")
n = int(sys.argv[1]); bad = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
d = ibis.duckdb.connect(); arrow = d.raw_sql(gen_sql(n, bad)).fetch_arrow_table()
con = ibis.polars.connect(); t = con.create_table("t", arrow)
print("polars table schema created=", t.schema()["created"], "| tacit target:", Customer._ibis_schema()["created"])
cnt = [0]; orig = PB._to_dataframe
def counting(self, *a, **k): cnt[0] += 1; return orig(self, *a, **k)
PB._to_dataframe = counting
def timed(label, fn, rep=3):
    ts = []
    try: fn()
    except Exception: pass
    for _ in range(rep):
        cnt[0] = 0; t0 = time.perf_counter()
        try: fn(); out = "ok"
        except Exception as e: out = f"{type(e).__name__}: {str(e).splitlines()[0][:100]}"
        ts.append(time.perf_counter() - t0)
    print(f"{label:55s} queries={cnt[0]:>3} min={min(ts):7.3f}s  {out}", flush=True)
timed(f"n={n:,} bad={bad} tacit Schema.parse (pandera)", lambda: Customer.parse(t))
timed(f"n={n:,} bad={bad} native 1-query validate", lambda: validate(Customer, t, build_plan(Customer)))
r = validate(Customer, t, build_plan(Customer)); print("native report ok:", r.ok, "failures:", len(r.check_failures))
try:
    r = validate(Customer, t, build_plan(Customer, ["id"])); print("native unique(id) on polars: ok", r.ok)
except Exception as e: print("native unique(id) on polars:", type(e).__name__, str(e)[:100])
