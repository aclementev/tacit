"""Q3: current tacit vs tuned pandera vs hybrid vs native, on E4's Customer benchmark.

usage: REPEAT=5 uv run --frozen python bench_tuned.py 1000000 [10000000]
       (add `csv` as first arg to run the file-backed CSV scenario at 1M instead)
Configs are interleaved per dataset so they see the same machine load; min wall over REPEAT
runs after one warm-up. Query counts come from DuckDB's query log (E4 common.py).
"""
from __future__ import annotations

import copy
import gc
import json
import os
import statistics
import sys
import time
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "e4-runtime"))
warnings.filterwarnings("ignore")

from common import Customer, log_queries, log_reset, make_con  # noqa: E402
from ibisval import build_plan, validate as native_validate  # noqa: E402

import hybrid  # noqa: E402

REPEAT = int(os.environ.get("REPEAT", 3))
NARWHALS = bool(os.environ.get("PANDERA_USE_NARWHALS_BACKEND"))


def run(label, fn, con):
    times, cpus, nq, outcome = [], [], None, "ok"
    for i in range(REPEAT + 1):
        log_reset(con)
        t0, c0 = time.perf_counter(), time.process_time()
        try:
            r = fn()
            if isinstance(r, hybrid.Report) and not r.ok:
                outcome = f"report:{len(r.failures)} failures"
            elif hasattr(r, "ok") and not isinstance(r, hybrid.Report) and not r.ok:
                outcome = "report:failures"
        except Exception as e:  # noqa: BLE001
            outcome = type(e).__name__
        w, c = time.perf_counter() - t0, time.process_time() - c0
        if i:
            times.append(w)
            cpus.append(c)
        nq = len(log_queries(con))
    r = dict(label=label, queries=nq, min_s=round(min(times), 3), med_s=round(statistics.median(times), 3),
             cpu_min_s=round(min(cpus), 3), outcome=outcome)
    print(json.dumps(r), flush=True)
    return r


def tuned_schema(n_failure_cases=5):
    """tacit's pandera schema with every Check bounded to n_failure_cases."""
    s = Customer._pandera_schema()
    for col in s.columns.values():
        new = []
        for ck in col.checks:
            ck = copy.copy(ck)
            ck.n_failure_cases = n_failure_cases
            new.append(ck)
        col.checks = new
    return s


_MAT = [0]


def _materialized(con, t, cast_map, schema):
    """cast once into a table, validate that (the .cache() idea, without ibis' GC-driven drop).

    DuckDB materializes `timestamp` as `timestamp(6)`, which pandera's exact dtype check rejects
    (see raw_surface_native.txt), so the tuned schema adopts the materialized dtypes.
    """
    _MAT[0] += 1
    name = f"mat_{_MAT[0]}"
    con.raw_sql(f"CREATE TABLE {name} AS {con.compile(t.cast(cast_map))}")  # ibis create_table misbehaves here
    m = con.table(name)
    try:
        schema = copy.deepcopy(schema)       # schema.update_column raises NotImplementedError on ibis
        for c, ty in m.schema().items():
            if ty.is_timestamp():
                schema.columns[c].dtype = ty
        return schema.validate(m, lazy=True)
    finally:
        con.raw_sql(f"DROP TABLE IF EXISTS {name}")  # ibis drop_table emits SQL duckdb rejects here


def configs(t, con, tag, coerce=False):
    target = Customer._ibis_schema()
    cast_map = {c: tt for c, tt in target.items() if t[c].type() != tt}
    plain = Customer._pandera_schema()
    tuned = tuned_schema()
    plan = build_plan(Customer)
    out = [
        run(f"{tag} | A0 current tacit Schema.parse", lambda: Customer.parse(t), con),
        run(f"{tag} | A1 pandera lazy=True, n_failure_cases=5", lambda: tuned.validate(t.cast(cast_map), lazy=True), con),
        run(f"{tag} | A2 = A1 + cast once, materialize (temp table)", lambda: _materialized(con, t, cast_map, tuned), con),
        run(f"{tag} | B  hybrid (pandera checks, 1 fused query)", lambda: hybrid.validate(plain, t.cast(cast_map)), con),
    ]
    if not NARWHALS:
        out.append(run(f"{tag} | C  native ibisval", lambda: native_validate(Customer, t, plan, coerce=coerce), con))
    return out


results = []
args = sys.argv[1:]
if args and args[0] == "csv":
    n = int(args[1]) if len(args) > 1 else 1_000_000
    con, t = make_con(n, as_varchar=True, name="raw")
    path = os.path.abspath(f"data_{n}.csv")
    con.raw_sql(f"COPY raw TO '{path}' (HEADER, DELIMITER ',')")
    t = con.read_csv(path, all_varchar=True, table_name="csv_src")
    results += configs(t, con, f"n={n:,} src=csv(all varchar)", coerce=True)
    os.remove(path)
else:
    for n in map(int, args):
        for bad in (0.0, 0.001):
            tag = f"n={n:,} bad={bad}{' narwhals' if NARWHALS else ''}"
            print("==", tag, flush=True)
            con, t = make_con(n, bad_rate=bad)
            results += configs(t, con, tag)
            con.disconnect()
            del con, t
            gc.collect()
suffix = ("_narwhals" if NARWHALS else "") + "_" + "_".join(args) + os.environ.get("TAG", "")
json.dump(results, open(f"results_tuned{suffix}.json", "w"), indent=1)
