"""Q1: pandera ibis backend vs one-aggregate-query validator on duckdb.
usage: uv run python bench_parse.py 1000000 [10000000 ...]"""
import gc, statistics, sys, time, json, warnings
import pandera.errors as pe
import tacit.errors as te
from common import *
from ibisval import validate, build_plan

warnings.filterwarnings("ignore")
import os
REPEAT = int(os.environ.get('REPEAT', 3))

def run(label, fn, con):
    times, cpus, nq, outcome = [], [], None, "ok"
    for i in range(REPEAT + 1):          # first = warmup (not counted)
        log_reset(con)
        t0 = time.perf_counter(); c0 = time.process_time()
        try:
            fn()
        except Exception as e:
            outcome = type(e).__name__
        dt_ = time.perf_counter() - t0; dc = time.process_time() - c0
        if i:
            times.append(dt_); cpus.append(dc)
        nq = len(log_queries(con))
    r = dict(label=label, queries=nq, min_s=round(min(times), 3), med_s=round(statistics.median(times), 3), cpu_min_s=round(min(cpus), 3), outcome=outcome)
    print(json.dumps(r), flush=True)
    return r

def scan_all(t):  # reference: one full scan touching every column
    return t.aggregate(**{f"c_{c}": t[c].count() for c in t.columns}).to_pyarrow()

results = []
for n in map(int, sys.argv[1:]):
    for bad in (0.0, 0.001):
        tag = f"n={n:,} bad={bad}"
        print("==", tag, flush=True)
        con, t = make_con(n, bad_rate=bad)
        plan = build_plan(Customer)
        rows = [
            run(f"{tag} | reference: 1 full-scan aggregate", lambda: scan_all(t), con),
            run(f"{tag} | tacit Schema.parse (pandera)", lambda: Customer.parse(t), con),
            run(f"{tag} | pandera lazy=True", lambda: Customer._pandera_schema().validate(t.cast({"created": "timestamp"}), lazy=True), con),
            run(f"{tag} | native 1-query validate", lambda: validate(Customer, t, plan), con),
            run(f"{tag} | native 1-query validate + unique(id)", lambda: validate(Customer, t, build_plan(Customer, ["id"])), con),
        ]
        results += rows
        con.disconnect(); del con, t; gc.collect()
json.dump(results, open(f"results_parse_{'_'.join(sys.argv[1:])}.json", "w"), indent=1)
