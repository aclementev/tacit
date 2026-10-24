"""Runtime overhead of the tacit pipeline (examples/e2e.py) vs the same pipeline in plain ibis.

    cd dev/research/redesign && uv run --frozen python e15-e2e/tools/bench.py SOURCES_DIR [REPEAT]

Variants (same step bodies as the examples; phases timed separately, min of REPEAT after a warm-up):
  tacit        e2e.py: parse x2 (coerce + checks), typed steps, @step(validate=True), write
  ibis+pandera e2e_plain.py: pandera validate x2 (+1 inside customer_value), plain ibis steps, write
  ibis+pandera, cached   as above, but the CSV reads are materialised first (`.cache()`), like tacit does
  ibis only    e2e_plain.py with every pandera validate replaced by identity (no contracts at all)
Also: pure expression-construction time of the step bodies (no queries: tacit's assume_not_null
check and @step validation disabled), averaged over 50 builds.
Phases: ingest (read + validate), build (construct the step expressions; tacit runs its
assume_not_null and @step(validate=True) queries here), write (parquet + csv).
Queries are counted from DuckDB's QueryLog (DESCRIBE / housekeeping excluded, as in E4).
"""

import json
import statistics
import sys
import time
import warnings
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HERE / "src"), str(HERE / "examples")]
warnings.filterwarnings("ignore")

import ibis  # noqa: E402

import e2e as T  # noqa: E402
import e2e_plain as P  # noqa: E402

SRC = Path(sys.argv[1])
REPEAT = int(sys.argv[2]) if len(sys.argv) > 2 else 5
OUT = HERE / "out" / "bench_tmp"  # scratch outputs (overwritten)


def con_with_log() -> ibis.BaseBackend:
    con = ibis.duckdb.connect()
    con.raw_sql("CALL enable_logging('QueryLog')")
    return con


def queries(con) -> list[str]:
    rows = con.raw_sql("SELECT message FROM duckdb_logs WHERE type = 'QueryLog' ORDER BY timestamp").fetchall()
    skip = ("DESCRIBE", "SELECT CURRENT_", "CALL ", "SELECT message FROM duckdb_logs", "SET ", "PRAGMA")
    return [m.strip() for (m,) in rows if m.strip() and not m.strip().startswith(skip)]


def reset(con) -> None:
    con.raw_sql("CALL truncate_duckdb_logs()")


def tacit_run(con, out: Path) -> dict:
    ph = {}
    t = time.perf_counter(); reset(con)
    events = T.OrderEvents.parse(con.read_csv(SRC / "orders.csv"))
    customers = T.Customers.parse(con.read_csv(SRC / "customers.csv"))
    ph["ingest"] = (time.perf_counter() - t, queries(con))
    t = time.perf_counter(); reset(con)
    orders = T.add_metrics(T.keep_latest(events, key=events.c.order_id, ts=events.c.updated_at))
    facts = T.with_customer(T.delivered(orders), customers)
    monthly = T.monthly_revenue(facts)
    top = T.top_customers(T.customer_value(facts))
    ph["build"] = (time.perf_counter() - t, queries(con))
    t = time.perf_counter(); reset(con)
    monthly.to_parquet(out / "m.parquet")
    top.to_csv(out / "t.csv")
    ph["write"] = (time.perf_counter() - t, queries(con))
    return ph


def plain_run(con, out: Path, validate: bool, cache: bool = False) -> dict:
    ph = {}
    ident = (lambda m: m.validate) if validate else (lambda m: (lambda x: x))
    saved = P.CustomerValue.validate
    if not validate:
        P.CustomerValue.validate = lambda t: t  # type: ignore[method-assign]
    try:
        t = time.perf_counter(); reset(con)
        def rd(f: Path):
            if not cache:
                return P.read(con, f)
            t = con.read_csv(f).cache()  # cache first: a cached cast comes back as timestamp(6) again
            return t.cast({c: "timestamp" for c, d in t.schema().items() if d.is_timestamp()})

        events = ident(P.OrderEvents)(rd(SRC / "orders.csv"))
        customers = ident(P.Customers)(rd(SRC / "customers.csv"))
        ph["ingest"] = (time.perf_counter() - t, queries(con))
        t = time.perf_counter(); reset(con)
        orders = P.add_metrics(P.keep_latest(events, key="order_id", ts="updated_at"))
        facts = P.with_customer(P.delivered(orders), customers)
        monthly = P.monthly_revenue(facts)
        top = P.top_customers(P.customer_value(facts))
        ph["build"] = (time.perf_counter() - t, queries(con))
        t = time.perf_counter(); reset(con)
        monthly.to_parquet(out / "m.parquet")
        top.to_csv(out / "t.csv")
        ph["write"] = (time.perf_counter() - t, queries(con))
    finally:
        P.CustomerValue.validate = saved  # type: ignore[method-assign]
    return ph


def pure_build(n: int = 50) -> None:
    import tacit_t3._df as tdf

    con = con_with_log()
    ev, cu = T.OrderEvents.parse(con.read_csv(SRC / "orders.csv")), T.Customers.parse(con.read_csv(SRC / "customers.csv"))
    pev, pcu = P.read(con, SRC / "orders.csv"), P.read(con, SRC / "customers.csv")
    saved_chk, saved_val = tdf._check_assumptions, P.CustomerValue.validate
    tdf._check_assumptions = lambda *a: None
    P.CustomerValue.validate = lambda t: t  # type: ignore[method-assign]
    cv = T.customer_value.__wrapped__  # bypass @tacit.step(validate=True)

    def t_build() -> None:
        o = T.add_metrics(T.keep_latest(ev, key=ev.c.order_id, ts=ev.c.updated_at))
        f = T.with_customer(T.delivered(o), cu)
        T.monthly_revenue(f), T.top_customers(cv(f))

    def p_build() -> None:
        o = P.add_metrics(P.keep_latest(pev, key="order_id", ts="updated_at"))
        f = P.with_customer(P.delivered(o), pcu)
        P.monthly_revenue(f), P.top_customers(P.customer_value(f))

    try:
        for name, fn in (("tacit", t_build), ("ibis", p_build)):
            fn()
            ts = []
            for _ in range(n):
                t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
            print(f"pure expression build ({name:5}): min {min(ts) * 1e3:.1f} ms, median {statistics.median(ts) * 1e3:.1f} ms")
    finally:
        tdf._check_assumptions, P.CustomerValue.validate = saved_chk, saved_val


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    variants = {"tacit": lambda c: tacit_run(c, OUT), "ibis+pandera": lambda c: plain_run(c, OUT, True),
                "ibis+pandera, cached": lambda c: plain_run(c, OUT, True, cache=True), "ibis only": lambda c: plain_run(c, OUT, False)}
    times: dict[str, dict[str, list[float]]] = {v: {} for v in variants}
    nq: dict[str, dict[str, int]] = {v: {} for v in variants}
    sql: dict[str, dict[str, list[str]]] = {v: {} for v in variants}
    for i in range(REPEAT + 1):
        for name, fn in variants.items():  # interleaved, fresh connection each run
            ph = fn(con_with_log())
            for p, (dt, qs) in ph.items():
                if i:
                    times[name].setdefault(p, []).append(dt)
                nq[name][p], sql[name][p] = len(qs), [q[:160] for q in qs]
    n_orders = sum(1 for _ in open(SRC / "orders.csv")) - 1
    print(f"source: {SRC} ({n_orders} order events); min / median of {REPEAT} runs, seconds; q = data queries")
    print(f"{'variant':22}" + "".join(f"{p:>22}" for p in ("ingest", "build", "write", "total")))
    for name in variants:
        cells, tot_min, tot_q = [], 0.0, 0
        for p in ("ingest", "build", "write"):
            mn, md = min(times[name][p]), statistics.median(times[name][p])
            tot_min += mn
            tot_q += nq[name][p]
            cells.append(f"{mn:.3f}/{md:.3f} q{nq[name][p]}")
        cells.append(f"{tot_min:.3f} q{tot_q}")
        print(f"{name:22}" + "".join(f"{c:>22}" for c in cells))
    pure_build()
    (HERE / "out" / f"bench_queries_{n_orders}.json").write_text(json.dumps(sql, indent=1))


if __name__ == "__main__":
    main()
