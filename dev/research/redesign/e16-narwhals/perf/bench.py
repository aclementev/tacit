"""Q5: expression-building overhead and execution time: native vs narwhals vs ibis (vs tacit_nw).

usage:
  uv run python perf/bench.py gen 1000000 10000000   # writes data/*.parquet (regenerable, gitignored-size)
  uv run python perf/bench.py build                  # build-only overhead (no execution)
  uv run python perf/bench.py exec 1000000           # execution, TPC-H Q1 + ecommerce-like
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT), str(ROOT / "cap"), str(ROOT / "src"), str(ROOT / "examples")]
DATA = ROOT / "data"

import duckdb  # noqa: E402
import ibis  # noqa: E402
import narwhals.stable.v2 as nw  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

import examples_ibis as xi  # noqa: E402
import examples_nw as xn  # noqa: E402


def gen(n: int) -> None:
    DATA.mkdir(exist_ok=True)
    rng = np.random.default_rng(1)
    li = pl.DataFrame({
        "l_orderkey": rng.integers(0, n // 4, n), "l_quantity": rng.integers(1, 51, n).astype(float),
        "l_extendedprice": rng.uniform(900, 100_000, n).round(2), "l_discount": rng.integers(0, 11, n) / 100,
        "l_tax": rng.integers(0, 9, n) / 100, "l_returnflag": np.array(["A", "N", "R"])[rng.integers(0, 3, n)],
        "l_linestatus": np.array(["F", "O"])[rng.integers(0, 2, n)],
        "l_shipdate": pl.date_range(date(1992, 1, 1), date(1998, 12, 1), eager=True).sample(n, with_replacement=True, seed=1),
    })
    li.write_parquet(DATA / f"lineitem_{n}.parquet")
    nc = max(n // 10, 10)
    ts0 = datetime(2024, 1, 1).timestamp()
    orders = pl.DataFrame({
        "order_id": np.arange(n), "customer_id": rng.integers(0, nc, n),
        "order_ts": pl.from_epoch(pl.Series((ts0 + rng.uniform(0, 365 * 86400, n)).astype("int64")), time_unit="s").cast(pl.Datetime("us")),
        "status": np.array(["pending", "shipped", "cancelled"])[rng.integers(0, 3, n)],
        "amount": rng.uniform(0, 500, n).round(2),
        "discount": pl.Series(np.where(rng.random(n) < 0.3, np.nan, rng.uniform(0, 20, n).round(2))).fill_nan(None),
    })
    orders.write_parquet(DATA / f"orders_{n}.parquet")
    pl.DataFrame({"customer_id": np.arange(nc), "name": [f"N{i}" for i in range(nc)], "email": [f"u{i}@x.com" for i in range(nc)],
                  "country": np.array(["DE", "US", "FR", "ES", "IT"])[rng.integers(0, 5, nc)],
                  "signup_date": pl.Series([date(2023, 1, 1)] * nc)}).write_parquet(DATA / f"customers_{n}.parquet")
    print("wrote", n)


# ----------------------------------------------------------------------------- pipelines
def ecom_nw(o: Any, c: Any) -> list[Any]:
    cl = xn.clean_orders(o)
    return [xn.country_month_stats(cl, c), xn.status_summary(cl), xn.latest_per_key(cl)]


def ecom_ibis(o: Any, c: Any) -> list[Any]:
    r = xi.ecommerce(o, c)
    return [r["stats"], r["status"], r["latest"]]


def ecom_polars(o: pl.LazyFrame, c: pl.LazyFrame) -> list[pl.LazyFrame]:
    cl = o.filter(pl.col("status") != "cancelled").with_columns(net_amount=pl.col("amount") - pl.col("discount").fill_null(0))
    stats = cl.join(c, on="customer_id").group_by("country", pl.col("order_ts").dt.truncate("1mo").dt.date().alias("order_month")).agg(
        order_count=pl.col("order_id").count(), total_net=pl.col("net_amount").sum(), avg_net=pl.col("net_amount").mean(),
        distinct_customers=pl.col("customer_id").n_unique())
    by = cl.group_by("status").agg(orders=pl.col("order_id").count(), revenue=pl.col("net_amount").sum())
    status = by.with_columns(share=pl.col("revenue") / pl.col("revenue").sum())
    latest = cl.filter(pl.col("order_ts").rank("ordinal", descending=True).over("customer_id") == 1)
    return [stats, status, latest]


def tpch_polars(li: pl.LazyFrame) -> pl.LazyFrame:
    s = li.filter(pl.col("l_shipdate") <= date(1998, 9, 2))
    d = pl.col("l_extendedprice") * (1 - pl.col("l_discount"))
    return s.group_by("l_returnflag", "l_linestatus").agg(
        sum_qty=pl.col("l_quantity").sum(), sum_base_price=pl.col("l_extendedprice").sum(), sum_disc_price=d.sum(),
        sum_charge=(d * (1 + pl.col("l_tax"))).sum(), avg_qty=pl.col("l_quantity").mean(), avg_price=pl.col("l_extendedprice").mean(),
        avg_disc=pl.col("l_discount").mean(), count_order=pl.col("l_orderkey").count()).sort("l_returnflag", "l_linestatus")


TPCH_SQL = """SELECT l_returnflag, l_linestatus, sum(l_quantity) sum_qty, sum(l_extendedprice) sum_base_price,
 sum(l_extendedprice*(1-l_discount)) sum_disc_price, sum(l_extendedprice*(1-l_discount)*(1+l_tax)) sum_charge,
 avg(l_quantity) avg_qty, avg(l_extendedprice) avg_price, avg(l_discount) avg_disc, count(l_orderkey) count_order
 FROM li WHERE l_shipdate <= DATE '1998-09-02' GROUP BY ALL ORDER BY 1, 2"""
ECOM_SQL = [
    """WITH cl AS (SELECT *, amount - coalesce(discount, 0) net_amount FROM o WHERE status <> 'cancelled')
       SELECT country, CAST(date_trunc('month', order_ts) AS DATE) order_month, count(order_id) order_count, sum(net_amount) total_net,
       avg(net_amount) avg_net, count(DISTINCT customer_id) distinct_customers FROM cl JOIN c USING (customer_id) GROUP BY ALL""",
    """WITH cl AS (SELECT *, amount - coalesce(discount, 0) net_amount FROM o WHERE status <> 'cancelled'),
       bys AS (SELECT status, count(order_id) orders, sum(net_amount) revenue FROM cl GROUP BY ALL)
       SELECT *, revenue / sum(revenue) OVER () AS share FROM bys""",
    """WITH cl AS (SELECT *, amount - coalesce(discount, 0) net_amount FROM o WHERE status <> 'cancelled')
       SELECT * FROM cl QUALIFY row_number() OVER (PARTITION BY customer_id ORDER BY order_ts DESC) = 1""",
]


def timeit(fn: Any, reps: int) -> float:
    fn()
    ts = []
    for _ in range(reps):
        t0 = time.perf_counter()
        fn()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts)


def build_bench() -> dict[str, float]:
    """Median microseconds to BUILD the 3 examples' expressions (TPC-H Q1 + 3 ecommerce outputs), no execution."""
    import t2nw

    li_pl = pl.scan_parquet(DATA / "lineitem_1000000.parquet")
    o_pl, c_pl = pl.scan_parquet(DATA / "orders_1000000.parquet"), pl.scan_parquet(DATA / "customers_1000000.parquet")
    con = duckdb.connect()
    li_dd, o_dd, c_dd = (con.read_parquet(str(DATA / f"{k}_1000000.parquet")) for k in ("lineitem", "orders", "customers"))
    for name, rel in (("li", li_dd), ("o", o_dd), ("c", c_dd)):
        rel.create_view(name)
    ic = ibis.duckdb.connect()
    li_ib, o_ib, c_ib = (ic.read_parquet(DATA / f"{k}_1000000.parquet") for k in ("lineitem", "orders", "customers"))
    nli, no, nc = nw.from_native(li_pl), nw.from_native(o_pl), nw.from_native(c_pl)
    dli, do, dc = nw.from_native(li_dd), nw.from_native(o_dd), nw.from_native(c_dd)
    # tacit_nw: conform (structural, no query) then the T2 pipeline functions
    tli = t2nw.LineItem.conform(li_pl)
    to, tc_ = t2nw.RawOrder.conform(o_pl), t2nw.RawCustomer.conform(c_pl)

    def tacit_nw_polars() -> Any:
        s = tli.filter(tli.c.l_shipdate <= date(1998, 9, 2))
        cl = t2nw.clean_orders(to)
        return [s, t2nw.country_month_stats(cl, tc_), t2nw.status_summary(cl), t2nw.latest_per_key(cl, "customer_id", "order_ts")]

    cases = {
        "native polars (lazy)": lambda: [tpch_polars(li_pl), *ecom_polars(o_pl, c_pl)],
        "narwhals -> polars": lambda: [xn.tpch_q1(nli), *ecom_nw(no, nc)],
        "narwhals -> duckdb": lambda: [xn.tpch_q1(dli), *ecom_nw(do, dc)],
        "native duckdb (relation from SQL)": lambda: [con.sql(TPCH_SQL), *[con.sql(q) for q in ECOM_SQL]],
        "ibis (duckdb)": lambda: [xi.tpch_q1(li_ib), *ecom_ibis(o_ib, c_ib)],
        "ibis (duckdb) + compile to SQL": lambda: [ibis.to_sql(e) for e in [xi.tpch_q1(li_ib), *ecom_ibis(o_ib, c_ib)]],
        "tacit_nw T2 -> polars (incl. checked build/extend/conform)": tacit_nw_polars,
    }
    _ = (li_dd, o_dd, c_dd)
    return {k: round(timeit(f, 30) * 1e6) for k, f in cases.items()}


def exec_bench(n: int) -> dict[str, dict[str, float]]:
    li_p, o_p, c_p = (str(DATA / f"{k}_{n}.parquet") for k in ("lineitem", "orders", "customers"))
    # in-memory inputs, so we time the query not the parquet scan
    li_df, o_df, c_df = pl.read_parquet(li_p), pl.read_parquet(o_p), pl.read_parquet(c_p)
    con = duckdb.connect()
    con.execute("CREATE TABLE li AS SELECT * FROM li_df; CREATE TABLE o AS SELECT * FROM o_df; CREATE TABLE c AS SELECT * FROM c_df")
    ic = ibis.duckdb.connect()
    ic.con.execute("CREATE TABLE li AS SELECT * FROM read_parquet(?)", [li_p])
    ic.con.execute("CREATE TABLE o AS SELECT * FROM read_parquet(?)", [o_p])
    ic.con.execute("CREATE TABLE c AS SELECT * FROM read_parquet(?)", [c_p])
    ip = ibis.polars.connect()
    ip_li = ip.create_table("li", li_df)

    def nw_collect(frames: list[Any]) -> None:
        for f in frames:
            f.collect() if isinstance(f, nw.LazyFrame) else f

    def dd_fetch(rels: list[Any]) -> None:
        for r in rels:
            r.fetch_arrow_table() if hasattr(r, "fetch_arrow_table") else r.arrow()

    tp = {
        "native polars": lambda: tpch_polars(li_df.lazy()).collect(),
        "narwhals -> polars": lambda: xn.tpch_q1(nw.from_native(li_df.lazy())).collect(),
        "native duckdb SQL": lambda: con.sql(TPCH_SQL).arrow(),
        "narwhals -> duckdb": lambda: xn.tpch_q1(nw.from_native(con.table("li"))).collect(),
        "ibis -> duckdb": lambda: xi.tpch_q1(ic.table("li")).to_pyarrow(),
        "ibis -> polars": lambda: xi.tpch_q1(ip_li).to_pyarrow(),
        "narwhals -> ibis -> duckdb": lambda: xn.tpch_q1(nw.from_native(ic.table("li"))).collect(),
    }
    ec = {
        "native polars": lambda: pl.collect_all(ecom_polars(o_df.lazy(), c_df.lazy())),
        "narwhals -> polars": lambda: nw_collect(ecom_nw(nw.from_native(o_df.lazy()), nw.from_native(c_df.lazy()))),
        "native duckdb SQL": lambda: dd_fetch([con.sql(q) for q in ECOM_SQL]),
        "narwhals -> duckdb": lambda: nw_collect(ecom_nw(nw.from_native(con.table("o")), nw.from_native(con.table("c")))),
        "ibis -> duckdb": lambda: [e.to_pyarrow() for e in ecom_ibis(ic.table("o"), ic.table("c"))],
        "narwhals -> ibis -> duckdb": lambda: nw_collect(ecom_nw(nw.from_native(ic.table("o")), nw.from_native(ic.table("c")))),
    }
    reps = 5 if n <= 1_000_000 else 3
    return {"tpch_q1": {k: round(timeit(f, reps), 4) for k, f in tp.items()},
            "ecommerce(3 outputs)": {k: round(timeit(f, reps), 4) for k, f in ec.items()}}


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "gen":
        for n in map(int, sys.argv[2:]):
            gen(n)
    elif mode == "build":
        r = build_bench()
        print(json.dumps(r, indent=1))
        (ROOT / "out" / "perf_build.json").write_text(json.dumps(r, indent=1))
    elif mode == "exec":
        for n in map(int, sys.argv[2:]):
            r = exec_bench(n)
            print(n, json.dumps(r, indent=1))
            (ROOT / "out" / f"perf_exec_{n}.json").write_text(json.dumps(r, indent=1))
