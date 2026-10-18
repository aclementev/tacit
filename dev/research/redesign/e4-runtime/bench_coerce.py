"""Coercion path: string -> typed. usage: uv run python bench_coerce.py 1000000 [10000000]"""
import os, sys, time, json, statistics, warnings, gc
import ibis
from common import *
from ibisval import validate, build_plan
warnings.filterwarnings("ignore")
REPEAT = int(os.environ.get("REPEAT", 3))
plan = build_plan(Customer)

def run(label, fn, con):
    times, cpus, outcome, msg = [], [], "ok", ""
    for i in range(REPEAT + 1):
        log_reset(con); t0 = time.perf_counter(); c0 = time.process_time()
        try: fn()
        except Exception as e: outcome, msg = type(e).__name__, str(e).splitlines()[0][:160]
        w, c = time.perf_counter() - t0, time.process_time() - c0
        if i: times.append(w); cpus.append(c)
        nq = len(log_queries(con))
    r = dict(label=label, queries=nq, min_s=round(min(times), 3), cpu_min_s=round(min(cpus), 3), outcome=outcome, msg=msg)
    print(json.dumps(r), flush=True); return r

out = []
for n in map(int, sys.argv[1:]):
    for source in ("varchar table", "csv view") if n <= 1_000_000 else ("varchar table",):
        for bad in (False, True):
            tag = f"n={n:,} src={source} coercion_errors={bad}"
            con, t = make_con(n, as_varchar=True, name="raw")
            if bad:
                con.raw_sql("UPDATE raw SET qty = 'N/A' WHERE try_cast(id AS BIGINT) % 1000 = 7")
            if source == "csv view":
                path = os.path.abspath(f"data_{n}.csv")
                con.raw_sql(f"COPY raw TO '{path}' (HEADER, DELIMITER ',')")
                t = con.read_csv(path, all_varchar=True, table_name="csv_src")
            target = Customer._ibis_schema()
            cast_map = {c: tt for c, tt in target.items() if t[c].type() != tt}
            out += [
                run(f"{tag} | reference: strict cast + count(every col), 1 query", lambda: (lambda x: x.aggregate(**{c: x[c].count() for c in x.columns}))(t.cast(cast_map)).to_pyarrow(), con),
                run(f"{tag} | tacit Schema.parse (cast + pandera)", lambda: Customer.parse(t), con),
                run(f"{tag} | native validate(coerce=True) (try_cast, 1 query)", lambda: validate(Customer, t, plan, coerce=True), con),
            ]
            if bad:
                try: Customer.parse(t)
                except Exception as e: print("   tacit error:", type(e).__name__, str(e)[:400].replace("\n", " | "))
                r = validate(Customer, t, plan, coerce=True); print("   native report:", r.coercion_failures, r.samples[:3])
            con.disconnect(); del con, t; gc.collect()
            if source == "csv view": os.remove(path)
json.dump(out, open(f"results_coerce_{'_'.join(sys.argv[1:])}.json", "w"), indent=1)
